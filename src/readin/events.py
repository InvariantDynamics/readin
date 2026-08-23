"""Typed event factories for the READIN Phase 0 through Phase 3 contracts."""

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


def create_evidence_dependency_declared(
    dependency_group_id: str | UUID,
    ancestor_evidence_id: str | UUID,
    descendant_evidence_id: str | UUID,
    relationship: str,
    *,
    verification_status: str = "ASSERTED_NOT_VERIFIED",
    basis_method: str = "USER_ASSERTED",
    basis_notes: str = "Dependency asserted by the recording user",
    dependency_id: str | UUID | None = None,
    declared_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    dependency = {
        "id": _uuid(dependency_id),
        "dependency_group_id": _uuid(dependency_group_id),
        "ancestor_evidence_id": _uuid(ancestor_evidence_id),
        "descendant_evidence_id": _uuid(descendant_evidence_id),
        "relationship": relationship,
        "verification_status": verification_status,
        "basis": {"method": basis_method, "notes": basis_notes},
        "declared_at": _timestamp(declared_at or event_time),
        "independence_disposition": "DEPENDENT",
    }
    return _event(
        "evidence.dependency_declared",
        {"dependency": dependency},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_claim_created(
    subject: str | UUID,
    predicate: str,
    claim_object: Mapping[str, Any],
    derived_from: Iterable[str | UUID],
    *,
    modality: str = "asserted",
    valid_from: str | datetime | None = None,
    valid_until: str | datetime | None = None,
    invalidation_conditions: Iterable[str] = (),
    claim_id: str | UUID | None = None,
    created_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    claim = {
        "id": _uuid(claim_id),
        "subject": _uuid(subject),
        "predicate": predicate,
        "object": dict(claim_object),
        "temporal_scope": {
            "valid_from": _timestamp(valid_from) if valid_from else None,
            "valid_until": _timestamp(valid_until) if valid_until else None,
        },
        "spatial_scope": None,
        "derived_from": [_uuid(item) for item in derived_from],
        "modality": modality,
        "epistemic_status": "unresolved",
        "invalidation_conditions": list(invalidation_conditions),
        "created_at": _timestamp(created_at or event_time),
    }
    return _event(
        "claim.created",
        {"claim": claim},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_evidence_linked(
    evidence_id: str | UUID,
    claim_id: str | UUID,
    role: str,
    *,
    dependency_group: str | UUID | None = None,
    warrant_statement: str | None = None,
    warrant_basis: str | None = None,
    appraisal_status: str = "NOT_APPRAISED",
    appraisal_method: str | None = None,
    appraisal_notes: str | None = None,
    strength_status: str = "UNASSESSED",
    strength_ordinal: str | None = None,
    link_id: str | UUID | None = None,
    created_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    evidence_link = {
        "id": _uuid(link_id),
        "evidence_id": _uuid(evidence_id),
        "claim_id": _uuid(claim_id),
        "role": role,
        "dependency_group": _uuid(dependency_group) if dependency_group else None,
        "warrant": {
            "status": "PROVIDED" if warrant_statement is not None else "NOT_PROVIDED",
            "statement": warrant_statement,
            "basis": warrant_basis,
        },
        "appraisal": {
            "status": appraisal_status,
            "method": appraisal_method,
            "notes": appraisal_notes,
        },
        "strength": {
            "status": strength_status,
            "ordinal": strength_ordinal,
        },
        "created_at": _timestamp(created_at or event_time),
    }
    return _event(
        "evidence.linked",
        {"evidence_link": evidence_link},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_relation_created(
    source_entity: str | UUID,
    relation_type: str,
    target_entity: str | UUID,
    claims: Iterable[str | UUID],
    *,
    relation_semantics: str = "DESCRIPTIVE",
    valid_from: str | datetime | None = None,
    valid_until: str | datetime | None = None,
    relation_id: str | UUID | None = None,
    created_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    relation = {
        "id": _uuid(relation_id),
        "source_entity": _uuid(source_entity),
        "relation_type": relation_type,
        "relation_semantics": relation_semantics,
        "target_entity": _uuid(target_entity),
        "valid_from": _timestamp(valid_from) if valid_from else None,
        "valid_until": _timestamp(valid_until) if valid_until else None,
        "claims": [_uuid(item) for item in claims],
        "confidence_state": {"status": "UNASSESSED", "rationale": None},
        "created_at": _timestamp(created_at or event_time),
    }
    return _event(
        "relation.created",
        {"relation": relation},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_resolution_candidate_recorded(
    left_entity_id: str | UUID,
    right_entity_id: str | UUID,
    signals: Iterable[Mapping[str, Any]],
    *,
    candidate_id: str | UUID | None = None,
    recorded_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    candidate = {
        "id": _uuid(candidate_id),
        "left_entity_id": _uuid(left_entity_id),
        "right_entity_id": _uuid(right_entity_id),
        "candidate_relation": "POSSIBLE_SAME_ENTITY",
        "signals": [dict(item) for item in signals],
        "status": "PENDING_REVIEW",
        "automatic_merge": False,
        "merge_state": "NOT_MERGED",
        "recorded_at": _timestamp(recorded_at or event_time),
    }
    return _event(
        "entity.resolution_candidate_recorded",
        {"resolution_candidate": candidate},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_resolution_candidate_assessed(
    candidate_id: str | UUID,
    disposition: str,
    rationale: str,
    *,
    reviewer_label: str = "local-user",
    supersedes_assessment_id: str | UUID | None = None,
    assessment_id: str | UUID | None = None,
    assessed_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    assessment = {
        "id": _uuid(assessment_id),
        "candidate_id": _uuid(candidate_id),
        "disposition": disposition,
        "rationale": rationale,
        "reviewer": {"mode": "MANUAL", "label": reviewer_label},
        "supersedes_assessment_id": (
            _uuid(supersedes_assessment_id) if supersedes_assessment_id else None
        ),
        "automatic_merge": False,
        "merge_state": "NOT_MERGED",
        "assessed_at": _timestamp(assessed_at or event_time),
    }
    return _event(
        "entity.resolution_candidate_assessed",
        {"resolution_assessment": assessment},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_cartographic_surface_registered(
    name: str,
    description: str,
    observer_frame_ids: Iterable[str | UUID],
    *,
    blind_region_state: str = "NOT_CHARACTERIZED",
    blind_regions: Iterable[str] = (),
    validity_conditions: Iterable[str] = (),
    surface_id: str | UUID | None = None,
    registered_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    surface = {
        "id": _uuid(surface_id),
        "name": name,
        "description": description,
        "surface_kind": "OBSERVER_FRAME_COMPOSITE",
        "observer_frame_ids": [_uuid(item) for item in observer_frame_ids],
        "blind_region_state": blind_region_state,
        "blind_regions": list(blind_regions),
        "validity_conditions": list(validity_conditions),
        "coverage_state": "NOT_ESTABLISHED",
        "registered_at": _timestamp(registered_at or event_time),
    }
    return _event(
        "cartography.surface_registered",
        {"cartographic_surface": surface},
        event_id=event_id,
        occurred_at=event_time,
    )


def create_cartographic_query_planned(
    asset_entity_id: str | UUID,
    surface_ids: Iterable[str | UUID],
    *,
    reconstruction_mode: str = "AS_KNOWN_THEN",
    epistemic_cutoff: str | datetime | None = None,
    max_relation_hops: int = 1,
    include_relations: bool = True,
    query_id: str | UUID | None = None,
    created_at: str | datetime | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    event_time = _timestamp(occurred_at)
    query_plan = {
        "id": _uuid(query_id),
        "asset_entity_id": _uuid(asset_entity_id),
        "direction": "BACKWARD",
        "surface_ids": [_uuid(item) for item in surface_ids],
        "reconstruction": {
            "mode": reconstruction_mode,
            "epistemic_cutoff": _timestamp(epistemic_cutoff) if epistemic_cutoff else None,
        },
        "traversal": {
            "max_relation_hops": max_relation_hops,
            "include_observations": True,
            "include_claims": True,
            "include_evidence": True,
            "include_dependencies": True,
            "include_relations": include_relations,
        },
        "missingness_policy": "PRESERVE",
        "conflict_policy": "PRESERVE",
        "prediction_state": "NOT_REQUESTED",
        "execution_state": "PLANNED_READ_ONLY",
        "created_at": _timestamp(created_at or event_time),
    }
    return _event(
        "cartography.query_planned",
        {"cartographic_query_plan": query_plan},
        event_id=event_id,
        occurred_at=event_time,
    )
