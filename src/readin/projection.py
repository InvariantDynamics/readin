"""Fail-closed deterministic replay for the READIN Phase 0 event ledger."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from readin.contracts import validate_event


class ProjectionError(ValueError):
    """Raised when a valid event violates ledger semantics."""


class ReadinProjection:
    """In-memory projection of the Phase 0 READIN ledger."""

    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}
        self.assets: dict[str, dict[str, Any]] = {}
        self.frames: dict[str, dict[str, Any]] = {}
        self.evidence: dict[str, dict[str, Any]] = {}
        self.observations: dict[str, dict[str, Any]] = {}
        self.event_ids: set[str] = set()
        self._evidence_digests: dict[str, str] = {}

    @classmethod
    def replay(cls, events: list[dict[str, Any]]) -> ReadinProjection:
        projection = cls()
        for event in events:
            projection.apply(event)
        return projection

    def apply(self, event: dict[str, Any]) -> None:
        validate_event(event)
        event_id = event["event_id"]
        if event_id in self.event_ids:
            raise ProjectionError(f"duplicate event id: {event_id}")

        handler_name = event["event_type"].replace(".", "_")
        handler = getattr(self, f"_apply_{handler_name}", None)
        if handler is None:
            raise ProjectionError(f"unsupported event type: {event['event_type']}")
        handler(event)
        self.event_ids.add(event_id)

    def _apply_entity_created(self, event: dict[str, Any]) -> None:
        entity = deepcopy(event["payload"]["entity"])
        entity_id = entity["id"]
        if entity_id in self.entities:
            raise ProjectionError(f"duplicate entity id: {entity_id}")
        self.entities[entity_id] = entity

    def _apply_asset_tracking_started(self, event: dict[str, Any]) -> None:
        asset = deepcopy(event["payload"]["tracked_asset"])
        entity_id = asset["entity_id"]
        if entity_id not in self.entities:
            raise ProjectionError(f"tracking references unknown entity: {entity_id}")
        if entity_id in self.assets:
            raise ProjectionError(f"entity is already tracked: {entity_id}")
        self.assets[entity_id] = asset

    def _apply_observer_frame_registered(self, event: dict[str, Any]) -> None:
        frame = deepcopy(event["payload"]["observer_frame"])
        frame_id = frame["id"]
        if frame_id in self.frames:
            raise ProjectionError(f"duplicate observer frame id: {frame_id}")
        self.frames[frame_id] = frame

    def _apply_evidence_manifested(self, event: dict[str, Any]) -> None:
        manifest = deepcopy(event["payload"]["evidence_manifest"])
        artifact_id = manifest["id"]
        digest = manifest["sha256"]
        if artifact_id in self.evidence:
            raise ProjectionError(f"duplicate evidence artifact id: {artifact_id}")
        if digest in self._evidence_digests:
            existing = self._evidence_digests[digest]
            raise ProjectionError(f"evidence digest already manifested as {existing}: {digest}")

        referenced = set(manifest["derivative_refs"])
        for transformation in manifest["transformations"]:
            referenced.update(transformation["input_artifact_ids"])
        missing = sorted(referenced - self.evidence.keys())
        if missing:
            raise ProjectionError(f"evidence manifest references unknown artifacts: {missing}")

        self.evidence[artifact_id] = manifest
        self._evidence_digests[digest] = artifact_id

    def _apply_observation_admitted(self, event: dict[str, Any]) -> None:
        observation = deepcopy(event["payload"]["observation"])
        observation_id = observation["id"]
        if observation_id in self.observations:
            raise ProjectionError(f"duplicate observation id: {observation_id}")

        unknown_subjects = sorted(set(observation["subject_entities"]) - self.assets.keys())
        if unknown_subjects:
            raise ProjectionError(f"observation references untracked entities: {unknown_subjects}")

        frame_id = observation["observer_frame_id"]
        if frame_id not in self.frames:
            raise ProjectionError(f"observation references unknown frame: {frame_id}")

        artifact_id = observation["source_artifact_id"]
        if artifact_id not in self.evidence:
            raise ProjectionError(f"observation references unknown evidence: {artifact_id}")

        superseded_id = observation["supersedes_observation_id"]
        if superseded_id is not None:
            if superseded_id not in self.observations:
                raise ProjectionError(
                    f"observation supersedes unknown observation: {superseded_id}"
                )
            prior_subjects = set(self.observations[superseded_id]["subject_entities"])
            if not prior_subjects.intersection(observation["subject_entities"]):
                raise ProjectionError("superseding observation does not share a subject")

        self._validate_temporal_scope(observation)
        self._validate_source_alignment(observation)

        self.observations[observation_id] = observation
        for entity_id in observation["subject_entities"]:
            self.assets[entity_id]["epistemic_state_version"] = event["event_id"]

    def _validate_temporal_scope(self, observation: dict[str, Any]) -> None:
        valid_from = observation["valid_from"]
        valid_until = observation["valid_until"]
        if (
            valid_from
            and valid_until
            and datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
            > datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        ):
            raise ProjectionError("observation valid_from is after valid_until")

    def _validate_source_alignment(self, observation: dict[str, Any]) -> None:
        manifest = self.evidence[observation["source_artifact_id"]]
        frame = self.frames[observation["observer_frame_id"]]
        source_policy = observation["provenance"]["source_policy"]
        if source_policy != manifest["access_policy"]:
            raise ProjectionError("observation source policy does not match evidence manifest")
        if source_policy != frame["access_projection"]["scope"]:
            raise ProjectionError("observation source policy does not match observer frame")

        observation_uri = observation["provenance"]["source_uri"]
        manifest_uri = manifest["source"]["uri"]
        if observation_uri != manifest_uri:
            raise ProjectionError("observation source URI does not match evidence manifest")

    def asset_view(self, entity_id: str) -> dict[str, Any]:
        if entity_id not in self.assets:
            raise ProjectionError(f"unknown tracked asset: {entity_id}")

        observations = [
            deepcopy(observation)
            for observation in self.observations.values()
            if entity_id in observation["subject_entities"]
        ]
        observations.sort(key=lambda item: (item["observed_at"], item["id"]))
        frame_ids = sorted({item["observer_frame_id"] for item in observations})
        artifact_ids = sorted({item["source_artifact_id"] for item in observations})
        return {
            "entity": deepcopy(self.entities[entity_id]),
            "tracked_asset": deepcopy(self.assets[entity_id]),
            "observations": observations,
            "observer_frames": [deepcopy(self.frames[item]) for item in frame_ids],
            "evidence_manifests": [deepcopy(self.evidence[item]) for item in artifact_ids],
            "authority_state": "NO_AUTHORITY",
        }

    def catalog_view(self) -> list[dict[str, Any]]:
        return [
            {
                "entity": deepcopy(self.entities[entity_id]),
                "tracked_asset": deepcopy(asset),
                "observation_count": sum(
                    entity_id in observation["subject_entities"]
                    for observation in self.observations.values()
                ),
                "authority_state": "NO_AUTHORITY",
            }
            for entity_id, asset in sorted(self.assets.items())
        ]
