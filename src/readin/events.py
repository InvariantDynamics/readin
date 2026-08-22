"""Typed event factories for the READIN Phase 0 contract."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from readin.contracts import validate_event

JsonObject = dict[str, Any]


def _uuid(value: str | UUID | None = None) -> str:
    return str(value or uuid4())


def _timestamp(value: str | datetime | None = None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _event(
    event_type: str,
    payload: JsonObject,
    *,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event = {
        "schema_version": "readin.event.v0.1",
        "event_id": _uuid(event_id),
        "event_type": event_type,
        "occurred_at": _timestamp(occurred_at),
        "authority_state": "NO_AUTHORITY",
        "payload": payload,
    }
    validate_event(event)
    return event


def create_entity_created(
    canonical_name: str,
    entity_type: str,
    *,
    aliases: Iterable[str] = (),
    external_ids: Iterable[Mapping[str, str]] = (),
    attributes: Mapping[str, Any] | None = None,
    entity_id: str | UUID | None = None,
    created_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    entity = {
        "id": _uuid(entity_id),
        "type": entity_type,
        "canonical_name": canonical_name,
        "aliases": list(aliases),
        "external_ids": [dict(item) for item in external_ids],
        "attributes": dict(attributes or {}),
        "created_at": _timestamp(created_at or event_time),
        "status": "active",
    }
    return _event(
        "entity.created",
        {"entity": entity},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_tracking_started(
    entity_id: str | UUID,
    *,
    priority: float = 0.5,
    collection_profile: str = "manual",
    update_policy: str = "manual",
    scopes: Iterable[str] = ("observer_frame", "temporal"),
    epistemic_state_version: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    selected_event_id = _uuid(event_id)
    tracked_asset = {
        "entity_id": _uuid(entity_id),
        "tracking": {
            "enabled": True,
            "priority": priority,
            "collection_profile": collection_profile,
            "update_policy": update_policy,
        },
        "scopes": list(scopes),
        "active_hypotheses": [],
        "active_scenarios": [],
        "active_watches": [],
        "epistemic_state_version": _uuid(epistemic_state_version or selected_event_id),
    }
    return _event(
        "asset.tracking_started",
        {"tracked_asset": tracked_asset},
        event_id=selected_event_id,
        occurred_at=occurred_at,
    )


def create_observer_frame_registered(
    name: str,
    frame_class: str,
    *,
    access_scope: str = "PUBLIC",
    access_description: str = "Publicly accessible source",
    measurement_name: str = "manual_recording",
    measurement_description: str = "A user records a source observation without inference",
    granularity_name: str = "artifact_level",
    granularity_description: str = "One source artifact or bounded source record",
    interpretation_name: str = "verbatim_structured_capture",
    interpretation_description: str = "Capture source-reported content without truth promotion",
    latency_class: str = "UNKNOWN",
    valid_time_available: bool = True,
    dependency_ancestry_required: bool = True,
    known_blind_regions: Iterable[str] = (),
    validity_conditions: Iterable[str] = (),
    frame_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    frame = {
        "id": _uuid(frame_id),
        "name": name,
        "class": frame_class,
        "access_projection": {
            "scope": access_scope,
            "description": access_description,
        },
        "measurement_model": {
            "name": measurement_name,
            "description": measurement_description,
        },
        "granularity": {
            "name": granularity_name,
            "description": granularity_description,
        },
        "interpretation_model": {
            "name": interpretation_name,
            "description": interpretation_description,
        },
        "temporal_characteristics": {
            "latency_class": latency_class,
            "valid_time_available": valid_time_available,
        },
        "provenance_constraints": {
            "source_identity_required": True,
            "dependency_ancestry_required": dependency_ancestry_required,
        },
        "known_blind_regions": list(known_blind_regions),
        "validity_conditions": list(validity_conditions),
    }
    return _event(
        "observer_frame.registered",
        {"observer_frame": frame},
        event_id=event_id,
        occurred_at=occurred_at,
    )


def create_evidence_manifested(
    sha256: str,
    media_type: str,
    size: int,
    source_label: str,
    *,
    source_uri: str | None = None,
    license_name: str | None = None,
    access_policy: str = "PUBLIC",
    transformations: Iterable[Mapping[str, Any]] = (),
    derivative_refs: Iterable[str | UUID] = (),
    artifact_id: str | UUID | None = None,
    acquired_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    manifest = {
        "id": _uuid(artifact_id),
        "sha256": sha256,
        "media_type": media_type,
        "size": size,
        "acquired_at": _timestamp(acquired_at or event_time),
        "source": {"label": source_label, "uri": source_uri},
        "license": license_name,
        "access_policy": access_policy,
        "transformations": [dict(item) for item in transformations],
        "derivative_refs": [_uuid(item) for item in derivative_refs],
    }
    return _event(
        "evidence.manifested",
        {"evidence_manifest": manifest},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_observation_admitted(
    subject_entities: Iterable[str | UUID],
    observer_frame_id: str | UUID,
    source_artifact_id: str | UUID,
    observation_type: str,
    structured_payload: Mapping[str, Any],
    observed_at: str | datetime,
    *,
    source_uri: str | None = None,
    source_policy: str = "PUBLIC",
    collector: str = "readin-cli",
    adapter: str = "manual",
    adapter_version: str = "0.1.0",
    acquisition_time: str | datetime | None = None,
    valid_from: str | datetime | None = None,
    valid_until: str | datetime | None = None,
    resolution: float | None = None,
    uncertainty: Mapping[str, Any] | None = None,
    missingness_state: str = "OBSERVED",
    dependency_group_ids: Iterable[str | UUID] = (),
    supersedes_observation_id: str | UUID | None = None,
    observation_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    observation = {
        "id": _uuid(observation_id),
        "subject_entities": [_uuid(item) for item in subject_entities],
        "observer_frame_id": _uuid(observer_frame_id),
        "source_artifact_id": _uuid(source_artifact_id),
        "supersedes_observation_id": (
            _uuid(supersedes_observation_id) if supersedes_observation_id else None
        ),
        "observed_at": _timestamp(observed_at),
        "valid_from": _timestamp(valid_from) if valid_from else None,
        "valid_until": _timestamp(valid_until) if valid_until else None,
        "observation_type": observation_type,
        "content": {"structured_payload": dict(structured_payload)},
        "provenance": {
            "collector": collector,
            "adapter": adapter,
            "adapter_version": adapter_version,
            "source_uri": source_uri,
            "source_policy": source_policy,
            "acquisition_time": _timestamp(acquisition_time or event_time),
        },
        "epistemic": {
            "resolution": resolution,
            "uncertainty": dict(uncertainty or {}),
            "access_scope": source_policy,
            "missingness_state": missingness_state,
            "dependency_group_ids": [_uuid(item) for item in dependency_group_ids],
        },
        "immutable": True,
    }
    return _event(
        "observation.admitted",
        {"observation": observation},
        event_id=event_id,
        occurred_at=event_time,
    )
