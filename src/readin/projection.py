"""Fail-closed deterministic replay for the READIN Phase 0 through Phase 2 ledger."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from readin.contracts import validate_event


class ProjectionError(ValueError):
    """Raised when a valid event violates ledger semantics."""


class ReadinProjection:
    """In-memory projection of the READIN ledger and its inspectable state history."""

    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}
        self.assets: dict[str, dict[str, Any]] = {}
        self.frames: dict[str, dict[str, Any]] = {}
        self.evidence: dict[str, dict[str, Any]] = {}
        self.observations: dict[str, dict[str, Any]] = {}
        self.dependencies: dict[str, dict[str, Any]] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.evidence_links: dict[str, dict[str, Any]] = {}
        self.relations: dict[str, dict[str, Any]] = {}
        self.resolution_candidates: dict[str, dict[str, Any]] = {}
        self.resolution_assessments: dict[str, dict[str, Any]] = {}
        self.asset_versions: dict[str, list[dict[str, Any]]] = {}
        self.event_ids: set[str] = set()
        self._evidence_digests: dict[str, str] = {}
        self._dependency_groups: dict[str, set[str]] = {}
        self._dependency_graph: dict[str, set[str]] = {}
        self._candidate_pairs: dict[tuple[str, str], str] = {}
        self._latest_resolution_assessment: dict[str, str] = {}
        self._events: list[dict[str, Any]] = []

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
        if self._events and self._parse_timestamp(event["occurred_at"]) < self._parse_timestamp(
            self._events[-1]["occurred_at"]
        ):
            raise ProjectionError("event occurred_at precedes the prior ledger event")

        handler_name = event["event_type"].replace(".", "_")
        handler = getattr(self, f"_apply_{handler_name}", None)
        if handler is None:
            raise ProjectionError(f"unsupported event type: {event['event_type']}")
        handler(event)
        self.event_ids.add(event_id)
        self._events.append(deepcopy(event))

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
        self.asset_versions[entity_id] = []
        self._advance_asset(entity_id, event)

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
        self._validate_observation_dependency_groups(observation)

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
            self._advance_asset(entity_id, event)

    def _apply_evidence_dependency_declared(self, event: dict[str, Any]) -> None:
        dependency = deepcopy(event["payload"]["dependency"])
        dependency_id = dependency["id"]
        if dependency_id in self.dependencies:
            raise ProjectionError(f"duplicate evidence dependency id: {dependency_id}")

        ancestor_id = dependency["ancestor_evidence_id"]
        descendant_id = dependency["descendant_evidence_id"]
        missing = sorted({ancestor_id, descendant_id} - self.evidence.keys())
        if missing:
            raise ProjectionError(f"dependency references unknown evidence: {missing}")
        if ancestor_id == descendant_id:
            raise ProjectionError("evidence dependency cannot be self-referential")
        if descendant_id in self._dependency_graph.get(ancestor_id, set()):
            raise ProjectionError("duplicate evidence dependency edge")
        if self._dependency_path_exists(descendant_id, ancestor_id):
            raise ProjectionError("evidence dependency would create a cycle")

        if dependency["verification_status"] == "VERIFIED_FROM_MANIFEST":
            if dependency["relationship"] not in {
                "DERIVED_FROM",
                "SUMMARIZES",
                "REPRODUCES",
                "TRANSFORMS",
            }:
                raise ProjectionError(
                    "manifest verification is incompatible with the dependency relationship"
                )
            inputs = {
                input_id
                for transformation in self.evidence[descendant_id]["transformations"]
                for input_id in transformation["input_artifact_ids"]
            }
            if ancestor_id not in inputs:
                raise ProjectionError("verified dependency is not bound by the descendant manifest")
            if dependency["basis"]["method"] != "MANIFEST_TRANSFORMATION":
                raise ProjectionError("verified dependency requires MANIFEST_TRANSFORMATION basis")
        elif dependency["basis"]["method"] == "MANIFEST_TRANSFORMATION":
            raise ProjectionError(
                "MANIFEST_TRANSFORMATION basis requires VERIFIED_FROM_MANIFEST status"
            )

        self.dependencies[dependency_id] = dependency
        self._dependency_graph.setdefault(ancestor_id, set()).add(descendant_id)
        group_id = dependency["dependency_group_id"]
        self._dependency_groups.setdefault(group_id, set()).update({ancestor_id, descendant_id})
        for entity_id in self._assets_for_evidence({ancestor_id, descendant_id}):
            self._advance_asset(entity_id, event)

    def _apply_claim_created(self, event: dict[str, Any]) -> None:
        claim = deepcopy(event["payload"]["claim"])
        claim_id = claim["id"]
        if claim_id in self.claims:
            raise ProjectionError(f"duplicate claim id: {claim_id}")

        subject = claim["subject"]
        if subject not in self.assets:
            raise ProjectionError(f"claim references untracked subject: {subject}")
        if claim["object"]["kind"] == "ENTITY":
            object_entity = claim["object"]["entity_id"]
            if object_entity not in self.entities:
                raise ProjectionError(f"claim references unknown object entity: {object_entity}")

        missing_observations = sorted(set(claim["derived_from"]) - self.observations.keys())
        if missing_observations:
            raise ProjectionError(f"claim references unknown observations: {missing_observations}")
        if not any(
            subject in self.observations[observation_id]["subject_entities"]
            for observation_id in claim["derived_from"]
        ):
            raise ProjectionError("claim derivation has no observation of its subject")
        self._validate_interval(claim["temporal_scope"], "claim temporal_scope")

        self.claims[claim_id] = claim
        self._advance_asset(subject, event)

    def _apply_evidence_linked(self, event: dict[str, Any]) -> None:
        link = deepcopy(event["payload"]["evidence_link"])
        link_id = link["id"]
        if link_id in self.evidence_links:
            raise ProjectionError(f"duplicate evidence link id: {link_id}")
        if link["evidence_id"] not in self.evidence:
            raise ProjectionError(
                f"evidence link references unknown evidence: {link['evidence_id']}"
            )
        if link["claim_id"] not in self.claims:
            raise ProjectionError(f"evidence link references unknown claim: {link['claim_id']}")
        if any(
            existing["evidence_id"] == link["evidence_id"]
            and existing["claim_id"] == link["claim_id"]
            and existing["role"] == link["role"]
            for existing in self.evidence_links.values()
        ):
            raise ProjectionError("duplicate evidence/claim/role link")

        group_id = link["dependency_group"]
        if group_id is not None:
            if group_id not in self._dependency_groups:
                raise ProjectionError(
                    f"evidence link references unknown dependency group: {group_id}"
                )
            if link["evidence_id"] not in self._dependency_groups[group_id]:
                raise ProjectionError("linked evidence is not a member of its dependency group")

        if link["role"] == "derives":
            claim = self.claims[link["claim_id"]]
            derived_artifacts = {
                self.observations[observation_id]["source_artifact_id"]
                for observation_id in claim["derived_from"]
            }
            if link["evidence_id"] not in derived_artifacts:
                raise ProjectionError(
                    "derives link evidence is not an artifact of a claim derivation observation"
                )

        self._validate_evidence_link_axes(link)
        self.evidence_links[link_id] = link
        self._advance_asset(self.claims[link["claim_id"]]["subject"], event)

    def _apply_relation_created(self, event: dict[str, Any]) -> None:
        relation = deepcopy(event["payload"]["relation"])
        relation_id = relation["id"]
        if relation_id in self.relations:
            raise ProjectionError(f"duplicate relation id: {relation_id}")
        source = relation["source_entity"]
        target = relation["target_entity"]
        missing_entities = sorted({source, target} - self.entities.keys())
        if missing_entities:
            raise ProjectionError(f"relation references unknown entities: {missing_entities}")
        if source == target:
            raise ProjectionError("relation source and target must differ")

        missing_claims = sorted(set(relation["claims"]) - self.claims.keys())
        if missing_claims:
            raise ProjectionError(f"relation references unknown claims: {missing_claims}")
        unconnected_claims = sorted(
            item
            for item in relation["claims"]
            if not self._claim_connects_entities(self.claims[item], source, target)
        )
        if unconnected_claims:
            raise ProjectionError(
                f"relation cites claims that do not connect its source and target: "
                f"{unconnected_claims}"
            )
        self._validate_interval(relation, "relation validity")

        relation_type = relation["relation_type"]
        semantics = relation["relation_semantics"]
        if relation_type == "CAUSES":
            raise ProjectionError("causal relations must remain explicitly provisional as CAUSES?")
        if (relation_type == "CAUSES?") != (semantics == "CAUSAL_HYPOTHESIS"):
            raise ProjectionError("CAUSES? and CAUSAL_HYPOTHESIS must be declared together")

        self.relations[relation_id] = relation
        for entity_id in {source, target}.intersection(self.assets):
            self._advance_asset(entity_id, event)

    def _apply_entity_resolution_candidate_recorded(self, event: dict[str, Any]) -> None:
        candidate = deepcopy(event["payload"]["resolution_candidate"])
        candidate_id = candidate["id"]
        if candidate_id in self.resolution_candidates:
            raise ProjectionError(f"duplicate resolution candidate id: {candidate_id}")

        left_entity_id = candidate["left_entity_id"]
        right_entity_id = candidate["right_entity_id"]
        missing_entities = sorted({left_entity_id, right_entity_id} - self.entities.keys())
        if missing_entities:
            raise ProjectionError(
                f"resolution candidate references unknown entities: {missing_entities}"
            )
        if left_entity_id == right_entity_id:
            raise ProjectionError("resolution candidate entities must differ")
        if not {left_entity_id, right_entity_id}.intersection(self.assets):
            raise ProjectionError("resolution candidate must involve at least one tracked entity")

        pair = tuple(sorted((left_entity_id, right_entity_id)))
        if pair in self._candidate_pairs:
            raise ProjectionError(
                f"resolution candidate already exists for entity pair: "
                f"{self._candidate_pairs[pair]}"
            )

        for signal in candidate["signals"]:
            self._validate_resolution_signal(signal, {left_entity_id, right_entity_id})

        self.resolution_candidates[candidate_id] = candidate
        self._candidate_pairs[pair] = candidate_id
        for entity_id in {left_entity_id, right_entity_id}.intersection(self.assets):
            self._advance_asset(entity_id, event)

    def _apply_entity_resolution_candidate_assessed(self, event: dict[str, Any]) -> None:
        assessment = deepcopy(event["payload"]["resolution_assessment"])
        assessment_id = assessment["id"]
        if assessment_id in self.resolution_assessments:
            raise ProjectionError(f"duplicate resolution assessment id: {assessment_id}")

        candidate_id = assessment["candidate_id"]
        if candidate_id not in self.resolution_candidates:
            raise ProjectionError(
                f"resolution assessment references unknown candidate: {candidate_id}"
            )

        current_assessment_id = self._latest_resolution_assessment.get(candidate_id)
        supersedes_id = assessment["supersedes_assessment_id"]
        if current_assessment_id is None and supersedes_id is not None:
            raise ProjectionError("first resolution assessment cannot supersede another assessment")
        if current_assessment_id is not None and supersedes_id != current_assessment_id:
            raise ProjectionError(
                "resolution reassessment must supersede the candidate's latest assessment"
            )
        if current_assessment_id is not None:
            current_assessed_at = self.resolution_assessments[current_assessment_id]["assessed_at"]
            if self._parse_timestamp(assessment["assessed_at"]) < self._parse_timestamp(
                current_assessed_at
            ):
                raise ProjectionError(
                    "resolution reassessment assessed_at precedes the latest assessment"
                )

        self.resolution_assessments[assessment_id] = assessment
        self._latest_resolution_assessment[candidate_id] = assessment_id
        candidate = self.resolution_candidates[candidate_id]
        for entity_id in {
            candidate["left_entity_id"],
            candidate["right_entity_id"],
        }.intersection(self.assets):
            self._advance_asset(entity_id, event)

    def _validate_temporal_scope(self, observation: dict[str, Any]) -> None:
        self._validate_interval(observation, "observation validity")

    def _validate_interval(self, record: dict[str, Any], label: str) -> None:
        valid_from = record["valid_from"]
        valid_until = record["valid_until"]
        if (
            valid_from
            and valid_until
            and datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
            > datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        ):
            raise ProjectionError(f"{label} valid_from is after valid_until")

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

    def _validate_observation_dependency_groups(self, observation: dict[str, Any]) -> None:
        artifact_id = observation["source_artifact_id"]
        for group_id in observation["epistemic"]["dependency_group_ids"]:
            if group_id not in self._dependency_groups:
                raise ProjectionError(
                    f"observation references unknown dependency group: {group_id}"
                )
            if artifact_id not in self._dependency_groups[group_id]:
                raise ProjectionError(
                    "observation artifact is not a member of its declared dependency group"
                )

    def _validate_resolution_signal(
        self,
        signal: dict[str, Any],
        candidate_entities: set[str],
    ) -> None:
        if signal["kind"] == "CONTRADICTION" and signal["polarity"] != "CHALLENGES_CANDIDACY":
            raise ProjectionError("CONTRADICTION signal must challenge candidacy")
        verification_status = signal["verification_status"]
        if signal["kind"] == "OBSERVATION_REFERENCE":
            if verification_status != "REFERENCE_VALIDATED":
                raise ProjectionError(
                    "OBSERVATION_REFERENCE signal requires REFERENCE_VALIDATED status"
                )
            self._validate_resolution_observation_reference(signal, candidate_entities)
            return
        if verification_status == "REFERENCE_VALIDATED":
            raise ProjectionError(
                "REFERENCE_VALIDATED status is limited to OBSERVATION_REFERENCE signals"
            )
        if verification_status == "ENTITY_RECORD_VALIDATED":
            self._validate_entity_record_resolution_signal(signal, candidate_entities)

    def _validate_resolution_observation_reference(
        self,
        signal: dict[str, Any],
        candidate_entities: set[str],
    ) -> None:
        observation_id = signal["observation_id"]
        if observation_id not in self.observations:
            raise ProjectionError(
                f"resolution signal references unknown observation: {observation_id}"
            )
        subjects = set(self.observations[observation_id]["subject_entities"])
        if not subjects.intersection(candidate_entities):
            raise ProjectionError("resolution signal observation concerns neither candidate entity")

    def _validate_entity_record_resolution_signal(
        self,
        signal: dict[str, Any],
        candidate_entities: set[str],
    ) -> None:
        if signal["kind"] not in {"SHARED_ALIAS", "SHARED_EXTERNAL_ID"}:
            raise ProjectionError(
                "ENTITY_RECORD_VALIDATED status is limited to exact shared entity-record fields"
            )
        left_entity_id, right_entity_id = sorted(candidate_entities)
        left = self.entities[left_entity_id]
        right = self.entities[right_entity_id]
        if signal["kind"] == "SHARED_ALIAS":
            left_names = {left["canonical_name"], *left["aliases"]}
            right_names = {right["canonical_name"], *right["aliases"]}
            if not left_names.intersection(right_names):
                raise ProjectionError(
                    "validated shared-alias signal has no exact entity-record match"
                )
            return

        left_ids = {(item["scheme"], item["value"]) for item in left["external_ids"]}
        right_ids = {(item["scheme"], item["value"]) for item in right["external_ids"]}
        if not left_ids.intersection(right_ids):
            raise ProjectionError(
                "validated shared-external-id signal has no exact entity-record match"
            )

    def _validate_evidence_link_axes(self, link: dict[str, Any]) -> None:
        warrant = link["warrant"]
        if warrant["status"] == "NOT_PROVIDED" and (
            warrant["statement"] is not None or warrant["basis"] is not None
        ):
            raise ProjectionError("NOT_PROVIDED warrant cannot contain a statement or basis")
        if warrant["status"] == "PROVIDED" and (
            warrant["statement"] is None or warrant["basis"] is None
        ):
            raise ProjectionError("PROVIDED warrant requires a statement and basis")

        appraisal = link["appraisal"]
        strength = link["strength"]
        if appraisal["status"] == "NOT_APPRAISED" and (
            appraisal["method"] is not None or appraisal["notes"] is not None
        ):
            raise ProjectionError("NOT_APPRAISED link cannot contain appraisal details")
        if appraisal["status"] == "APPRAISED" and appraisal["method"] is None:
            raise ProjectionError("APPRAISED link requires an appraisal method")
        if strength["status"] == "UNASSESSED" and strength["ordinal"] is not None:
            raise ProjectionError("UNASSESSED strength cannot contain an ordinal")
        if strength["status"] == "ASSESSED" and (
            strength["ordinal"] is None or appraisal["status"] != "APPRAISED"
        ):
            raise ProjectionError("ASSESSED strength requires an ordinal and completed appraisal")

    def _dependency_path_exists(self, start: str, target: str) -> bool:
        pending = [start]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(self._dependency_graph.get(current, set()) - visited)
        return False

    def _assets_for_evidence(self, evidence_ids: set[str]) -> set[str]:
        return {
            entity_id
            for observation in self.observations.values()
            if observation["source_artifact_id"] in evidence_ids
            for entity_id in observation["subject_entities"]
            if entity_id in self.assets
        }

    def _advance_asset(self, entity_id: str, event: dict[str, Any]) -> None:
        if entity_id not in self.assets:
            return
        self.assets[entity_id]["epistemic_state_version"] = event["event_id"]
        self.asset_versions.setdefault(entity_id, []).append(
            {
                "state_version": event["event_id"],
                "event_type": event["event_type"],
                "recorded_at": event["occurred_at"],
            }
        )

    def _claim_connects_entities(self, claim: dict[str, Any], source: str, target: str) -> bool:
        return (
            claim["subject"] == source
            and claim["object"]["kind"] == "ENTITY"
            and claim["object"]["entity_id"] == target
        )

    def asset_view(self, entity_id: str) -> dict[str, Any]:
        if entity_id not in self.assets:
            raise ProjectionError(f"unknown tracked asset: {entity_id}")

        observations = [
            deepcopy(observation)
            for observation in self.observations.values()
            if entity_id in observation["subject_entities"]
        ]
        observations.sort(key=lambda item: (item["observed_at"], item["id"]))
        claims = [
            self.claim_view(item)
            for item in self.claims
            if self.claims[item]["subject"] == entity_id
        ]
        relations = [
            deepcopy(relation)
            for relation in self.relations.values()
            if entity_id in {relation["source_entity"], relation["target_entity"]}
        ]
        relations.sort(key=lambda item: (item["created_at"], item["id"]))
        resolution_candidates = [
            self.resolution_candidate_view(candidate_id)
            for candidate_id, candidate in self.resolution_candidates.items()
            if entity_id in {candidate["left_entity_id"], candidate["right_entity_id"]}
        ]
        resolution_candidates.sort(
            key=lambda item: (
                item["candidate"]["recorded_at"],
                item["candidate"]["id"],
            )
        )
        claim_ids = {item["claim"]["id"] for item in claims}
        links = [
            deepcopy(link) for link in self.evidence_links.values() if link["claim_id"] in claim_ids
        ]
        frame_ids = sorted({item["observer_frame_id"] for item in observations})
        artifact_ids = sorted(
            {item["source_artifact_id"] for item in observations}
            | {item["evidence_id"] for item in links}
        )
        dependency_group_ids = {
            item["dependency_group"] for item in links if item["dependency_group"]
        }
        dependencies = [
            deepcopy(dependency)
            for dependency in self.dependencies.values()
            if dependency["dependency_group_id"] in dependency_group_ids
        ]
        dependencies.sort(key=lambda item: (item["declared_at"], item["id"]))
        return {
            "entity": deepcopy(self.entities[entity_id]),
            "tracked_asset": deepcopy(self.assets[entity_id]),
            "observations": observations,
            "claims": claims,
            "relations": relations,
            "resolution_candidates": resolution_candidates,
            "evidence_dependencies": dependencies,
            "observer_frames": [deepcopy(self.frames[item]) for item in frame_ids],
            "evidence_manifests": [deepcopy(self.evidence[item]) for item in artifact_ids],
            "state_history": deepcopy(self.asset_versions[entity_id]),
            "authority_state": "NO_AUTHORITY",
        }

    def resolution_candidate_view(self, candidate_id: str) -> dict[str, Any]:
        if candidate_id not in self.resolution_candidates:
            raise ProjectionError(f"unknown resolution candidate: {candidate_id}")
        candidate = deepcopy(self.resolution_candidates[candidate_id])
        current_assessment_id = self._latest_resolution_assessment.get(candidate_id)
        assessment_lineage: list[dict[str, Any]] = []
        lineage_id = current_assessment_id
        while lineage_id is not None:
            assessment = self.resolution_assessments[lineage_id]
            assessment_lineage.append(deepcopy(assessment))
            lineage_id = assessment["supersedes_assessment_id"]
        assessments = list(reversed(assessment_lineage))
        current_assessment = (
            deepcopy(self.resolution_assessments[current_assessment_id])
            if current_assessment_id
            else None
        )
        return {
            "candidate": candidate,
            "assessments": assessments,
            "current_disposition": (
                current_assessment["disposition"] if current_assessment else "PENDING_REVIEW"
            ),
            "current_assessment": current_assessment,
            "reversible": True,
            "automatic_merge": False,
            "merge_state": "NOT_MERGED",
            "authority_state": "NO_AUTHORITY",
        }

    def claim_view(self, claim_id: str) -> dict[str, Any]:
        if claim_id not in self.claims:
            raise ProjectionError(f"unknown claim: {claim_id}")
        claim = deepcopy(self.claims[claim_id])
        links = [
            deepcopy(link) for link in self.evidence_links.values() if link["claim_id"] == claim_id
        ]
        links.sort(key=lambda item: (item["created_at"], item["id"]))
        role_counts: dict[str, int] = {}
        for link in links:
            role_counts[link["role"]] = role_counts.get(link["role"], 0) + 1
        dependency_groups = sorted(
            {link["dependency_group"] for link in links if link["dependency_group"] is not None}
        )
        return {
            "claim": claim,
            "evidence_links": links,
            "evidence_role_counts": role_counts,
            "dependency_groups": dependency_groups,
            "ungrouped_evidence_link_count": sum(
                link["dependency_group"] is None for link in links
            ),
            "independence_status": (
                "DEPENDENT_EVIDENCE_PRESENT"
                if dependency_groups
                else "INDEPENDENCE_NOT_ESTABLISHED"
            ),
            "epistemic_status": claim["epistemic_status"],
            "authority_state": "NO_AUTHORITY",
        }

    def timeline_view(
        self,
        entity_id: str,
        *,
        epistemic_cutoff: str | None = None,
        mode: str = "AS_KNOWN_THEN",
    ) -> dict[str, Any]:
        if entity_id not in self.assets:
            raise ProjectionError(f"unknown tracked asset: {entity_id}")
        if mode not in {"AS_KNOWN_THEN", "AS_RECONSTRUCTED_NOW"}:
            raise ProjectionError(f"unsupported reconstruction mode: {mode}")
        cutoff = self._parse_timestamp(epistemic_cutoff) if epistemic_cutoff else None

        entries: list[dict[str, Any]] = []
        versions = {item["state_version"] for item in self.asset_versions[entity_id]}
        for index, event in enumerate(self._events):
            if entity_id not in self._event_entities(event):
                continue
            recorded_at = self._parse_timestamp(event["occurred_at"])
            if cutoff and mode == "AS_KNOWN_THEN" and recorded_at > cutoff:
                continue
            entries.append(
                {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "recorded_at": event["occurred_at"],
                    "effective_at": self._effective_time(event),
                    "state_version": event["event_id"] if event["event_id"] in versions else None,
                    "hindsight": bool(cutoff and recorded_at > cutoff),
                    "ledger_order": index,
                    "authority_state": "NO_AUTHORITY",
                }
            )
        entries.sort(key=lambda item: (item["effective_at"], item["ledger_order"]))
        return {
            "entity_id": entity_id,
            "mode": mode,
            "epistemic_cutoff": epistemic_cutoff,
            "entries": entries,
            "hindsight_included": any(item["hindsight"] for item in entries),
            "authority_state": "NO_AUTHORITY",
        }

    def asset_view_at(
        self,
        entity_id: str,
        *,
        epistemic_cutoff: str | None = None,
        mode: str = "AS_KNOWN_THEN",
    ) -> dict[str, Any]:
        if mode not in {"AS_KNOWN_THEN", "AS_RECONSTRUCTED_NOW"}:
            raise ProjectionError(f"unsupported reconstruction mode: {mode}")
        if mode == "AS_KNOWN_THEN" and epistemic_cutoff:
            cutoff = self._parse_timestamp(epistemic_cutoff)
            events = [
                event
                for event in self._events
                if self._parse_timestamp(event["occurred_at"]) <= cutoff
            ]
            bounded = ReadinProjection.replay(events)
            view = bounded.asset_view(entity_id)
            timeline = bounded.timeline_view(
                entity_id, mode=mode, epistemic_cutoff=epistemic_cutoff
            )
        else:
            view = self.asset_view(entity_id)
            timeline = self.timeline_view(entity_id, mode=mode, epistemic_cutoff=epistemic_cutoff)
        view["reconstruction"] = {
            "mode": mode,
            "epistemic_cutoff": epistemic_cutoff,
            "hindsight_included": timeline["hindsight_included"],
        }
        view["timeline"] = timeline["entries"]
        return view

    def _event_entities(self, event: dict[str, Any]) -> set[str]:
        event_type = event["event_type"]
        payload = event["payload"]
        if event_type == "entity.created":
            return {payload["entity"]["id"]}
        if event_type == "asset.tracking_started":
            return {payload["tracked_asset"]["entity_id"]}
        if event_type == "observation.admitted":
            return set(payload["observation"]["subject_entities"])
        if event_type == "claim.created":
            return {payload["claim"]["subject"]}
        if event_type == "relation.created":
            relation = payload["relation"]
            return {relation["source_entity"], relation["target_entity"]}
        if event_type == "entity.resolution_candidate_recorded":
            candidate = payload["resolution_candidate"]
            return {candidate["left_entity_id"], candidate["right_entity_id"]}
        if event_type == "entity.resolution_candidate_assessed":
            candidate_id = payload["resolution_assessment"]["candidate_id"]
            if candidate_id not in self.resolution_candidates:
                return set()
            candidate = self.resolution_candidates[candidate_id]
            return {candidate["left_entity_id"], candidate["right_entity_id"]}
        if event_type == "evidence.linked":
            claim_id = payload["evidence_link"]["claim_id"]
            return {self.claims[claim_id]["subject"]} if claim_id in self.claims else set()
        if event_type == "evidence.dependency_declared":
            dependency = payload["dependency"]
            return self._assets_for_evidence(
                {dependency["ancestor_evidence_id"], dependency["descendant_evidence_id"]}
            )
        return set()

    def _effective_time(self, event: dict[str, Any]) -> str:
        event_type = event["event_type"]
        if event_type == "observation.admitted":
            return event["payload"]["observation"]["observed_at"]
        if event_type == "claim.created":
            claim = event["payload"]["claim"]
            return claim["temporal_scope"]["valid_from"] or claim["created_at"]
        if event_type == "relation.created":
            relation = event["payload"]["relation"]
            return relation["valid_from"] or relation["created_at"]
        if event_type == "evidence.dependency_declared":
            return event["payload"]["dependency"]["declared_at"]
        if event_type == "evidence.linked":
            return event["payload"]["evidence_link"]["created_at"]
        if event_type == "entity.resolution_candidate_recorded":
            return event["payload"]["resolution_candidate"]["recorded_at"]
        if event_type == "entity.resolution_candidate_assessed":
            return event["payload"]["resolution_assessment"]["assessed_at"]
        return event["occurred_at"]

    def _parse_timestamp(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def catalog_view(self) -> list[dict[str, Any]]:
        return [
            {
                "entity": deepcopy(self.entities[entity_id]),
                "tracked_asset": deepcopy(asset),
                "observation_count": sum(
                    entity_id in observation["subject_entities"]
                    for observation in self.observations.values()
                ),
                "claim_count": sum(entity_id == claim["subject"] for claim in self.claims.values()),
                "relation_count": sum(
                    entity_id in {relation["source_entity"], relation["target_entity"]}
                    for relation in self.relations.values()
                ),
                "resolution_candidate_count": sum(
                    entity_id in {candidate["left_entity_id"], candidate["right_entity_id"]}
                    for candidate in self.resolution_candidates.values()
                ),
                "authority_state": "NO_AUTHORITY",
            }
            for entity_id, asset in sorted(self.assets.items())
        ]
