"""Closed synthetic events for validation and the local demonstration."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from readin.events import (
    create_claim_created,
    create_entity_created,
    create_evidence_dependency_declared,
    create_evidence_linked,
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
    create_relation_created,
    create_resolution_candidate_assessed,
    create_resolution_candidate_recorded,
    create_tracking_started,
)


def phase0_events() -> list[dict[str, Any]]:
    """Return one deterministic, synthetic Phase 0 event loop."""

    entity_id = "11111111-1111-4111-8111-111111111111"
    frame_id = "22222222-2222-4222-8222-222222222222"
    artifact_id = "33333333-3333-4333-8333-333333333333"
    event_time = "2026-08-21T12:00:00Z"
    payload = {
        "reported_program": "Synthetic compute research initiative",
        "reported_status": "announced",
    }
    artifact_bytes = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    source_uri = "urn:readin:synthetic:public-record-001"

    return [
        create_entity_created(
            "Example Research Cooperative",
            "Organization",
            aliases=["ERC Synthetic"],
            entity_id=entity_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
            occurred_at=event_time,
        ),
        create_tracking_started(
            entity_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
            occurred_at="2026-08-21T12:00:01Z",
        ),
        create_observer_frame_registered(
            "Synthetic public record",
            "public_record",
            access_description="Closed synthetic public-record fixture",
            known_blind_regions=["No independent operational verification"],
            validity_conditions=["Valid only for the bundled synthetic fixture"],
            frame_id=frame_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
            occurred_at="2026-08-21T12:00:02Z",
        ),
        create_evidence_manifested(
            hashlib.sha256(artifact_bytes).hexdigest(),
            "application/json",
            len(artifact_bytes),
            "Bundled synthetic public record",
            source_uri=source_uri,
            license_name="Apache-2.0",
            artifact_id=artifact_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
            occurred_at="2026-08-21T12:00:03Z",
        ),
        create_observation_admitted(
            [entity_id],
            frame_id,
            artifact_id,
            "public_record.program_reported",
            payload,
            "2026-08-21T11:59:00Z",
            source_uri=source_uri,
            uncertainty={"disposition": "NOT_EVALUATED"},
            observation_id="44444444-4444-4444-8444-444444444444",
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5",
            occurred_at="2026-08-21T12:00:04Z",
        ),
    ]


def phase1_events() -> list[dict[str, Any]]:
    """Return a deterministic Array slice with dependent evidence and an unresolved claim."""

    events = phase0_events()
    entity_id = "11111111-1111-4111-8111-111111111111"
    frame_id = "22222222-2222-4222-8222-222222222222"
    root_artifact_id = "33333333-3333-4333-8333-333333333333"
    root_observation_id = "44444444-4444-4444-8444-444444444444"
    program_entity_id = "55555555-5555-4555-8555-555555555555"
    summary_artifact_a = "66666666-6666-4666-8666-666666666666"
    summary_artifact_b = "77777777-7777-4777-8777-777777777777"
    summary_observation_a = "88888888-8888-4888-8888-888888888888"
    summary_observation_b = "99999999-9999-4999-8999-999999999999"
    dependency_group_id = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
    claim_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

    summary_payload_a = {
        "reported_program": "Synthetic compute research initiative",
        "reported_status": "announced",
        "summary_source": "synthetic outlet a",
    }
    summary_payload_b = {
        "reported_program": "Synthetic compute research initiative",
        "reported_status": "announced",
        "summary_source": "synthetic outlet b",
    }
    summary_bytes_a = json.dumps(
        summary_payload_a, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    summary_bytes_b = json.dumps(
        summary_payload_b, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    transformation = {
        "name": "synthetic_summary",
        "version": "1.0.0",
        "input_artifact_ids": [root_artifact_id],
        "loss_assessment": "LOSSY",
    }
    source_uri_a = "urn:readin:synthetic:summary-a-001"
    source_uri_b = "urn:readin:synthetic:summary-b-001"

    events.extend(
        [
            create_entity_created(
                "Synthetic Compute Research Initiative",
                "Program",
                entity_id=program_entity_id,
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1",
                occurred_at="2026-08-21T12:00:05Z",
            ),
            create_evidence_manifested(
                hashlib.sha256(summary_bytes_a).hexdigest(),
                "application/json",
                len(summary_bytes_a),
                "Synthetic outlet A summary",
                source_uri=source_uri_a,
                license_name="Apache-2.0",
                transformations=[transformation],
                artifact_id=summary_artifact_a,
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2",
                occurred_at="2026-08-21T12:00:06Z",
            ),
            create_evidence_manifested(
                hashlib.sha256(summary_bytes_b).hexdigest(),
                "application/json",
                len(summary_bytes_b),
                "Synthetic outlet B summary",
                source_uri=source_uri_b,
                license_name="Apache-2.0",
                transformations=[transformation],
                artifact_id=summary_artifact_b,
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb3",
                occurred_at="2026-08-21T12:00:07Z",
            ),
            create_observation_admitted(
                [entity_id],
                frame_id,
                summary_artifact_a,
                "public_record.program_reported",
                summary_payload_a,
                "2026-08-21T11:59:10Z",
                source_uri=source_uri_a,
                uncertainty={"disposition": "NOT_EVALUATED"},
                observation_id=summary_observation_a,
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb4",
                occurred_at="2026-08-21T12:00:08Z",
            ),
            create_observation_admitted(
                [entity_id],
                frame_id,
                summary_artifact_b,
                "public_record.program_reported",
                summary_payload_b,
                "2026-08-21T11:59:20Z",
                source_uri=source_uri_b,
                uncertainty={"disposition": "NOT_EVALUATED"},
                observation_id=summary_observation_b,
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb5",
                occurred_at="2026-08-21T12:00:09Z",
            ),
            create_evidence_dependency_declared(
                dependency_group_id,
                root_artifact_id,
                summary_artifact_a,
                "SUMMARIZES",
                verification_status="VERIFIED_FROM_MANIFEST",
                basis_method="MANIFEST_TRANSFORMATION",
                basis_notes="Synthetic summary A manifest binds the root artifact",
                dependency_id="d1111111-1111-4111-8111-111111111111",
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb6",
                occurred_at="2026-08-21T12:00:10Z",
            ),
            create_evidence_dependency_declared(
                dependency_group_id,
                root_artifact_id,
                summary_artifact_b,
                "SUMMARIZES",
                verification_status="VERIFIED_FROM_MANIFEST",
                basis_method="MANIFEST_TRANSFORMATION",
                basis_notes="Synthetic summary B manifest binds the root artifact",
                dependency_id="d2222222-2222-4222-8222-222222222222",
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb7",
                occurred_at="2026-08-21T12:00:11Z",
            ),
            create_claim_created(
                entity_id,
                "operates_program",
                {"kind": "ENTITY", "entity_id": program_entity_id},
                [root_observation_id, summary_observation_a, summary_observation_b],
                valid_from="2026-08-21T11:59:00Z",
                invalidation_conditions=["Source record is retracted or superseded"],
                claim_id=claim_id,
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb8",
                occurred_at="2026-08-21T12:00:12Z",
            ),
            create_evidence_linked(
                root_artifact_id,
                claim_id,
                "supports",
                dependency_group=dependency_group_id,
                warrant_statement="The root record reports the program announcement",
                warrant_basis="DIRECT_SOURCE_REPORT",
                link_id="e1111111-1111-4111-8111-111111111111",
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb9",
                occurred_at="2026-08-21T12:00:13Z",
            ),
            create_evidence_linked(
                summary_artifact_a,
                claim_id,
                "supports",
                dependency_group=dependency_group_id,
                warrant_statement="Summary A repeats the root report",
                warrant_basis="DIRECT_SOURCE_REPORT",
                link_id="e2222222-2222-4222-8222-222222222222",
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbba0",
                occurred_at="2026-08-21T12:00:14Z",
            ),
            create_evidence_linked(
                summary_artifact_b,
                claim_id,
                "supports",
                dependency_group=dependency_group_id,
                warrant_statement="Summary B repeats the root report",
                warrant_basis="DIRECT_SOURCE_REPORT",
                link_id="e3333333-3333-4333-8333-333333333333",
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbba1",
                occurred_at="2026-08-21T12:00:15Z",
            ),
            create_relation_created(
                entity_id,
                "OPERATES",
                program_entity_id,
                [claim_id],
                relation_id="f1111111-1111-4111-8111-111111111111",
                event_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbba2",
                occurred_at="2026-08-21T12:00:16Z",
            ),
        ]
    )
    return events


def phase2_events() -> list[dict[str, Any]]:
    """Return a reversible manual resolution candidate without merging entity identity."""

    events = phase1_events()
    tracked_entity_id = "11111111-1111-4111-8111-111111111111"
    candidate_entity_id = "26262626-2626-4262-8262-262626262626"
    candidate_id = "27272727-2727-4272-8272-272727272727"
    observation_id = "44444444-4444-4444-8444-444444444444"

    events.extend(
        [
            create_entity_created(
                "ERC Research Cooperative LLC",
                "Organization",
                aliases=["ERC Synthetic"],
                attributes={"fixture_disposition": "identity_not_established"},
                entity_id=candidate_entity_id,
                event_id="29292929-2929-4292-8292-292929292929",
                occurred_at="2026-08-21T12:00:17Z",
            ),
            create_resolution_candidate_recorded(
                tracked_entity_id,
                candidate_entity_id,
                [
                    {
                        "kind": "SHARED_ALIAS",
                        "polarity": "SUPPORTS_CANDIDACY",
                        "verification_status": "ENTITY_RECORD_VALIDATED",
                        "statement": "Both synthetic entities declare the alias ERC Synthetic",
                        "observation_id": None,
                    },
                    {
                        "kind": "OBSERVATION_REFERENCE",
                        "polarity": "CHALLENGES_CANDIDACY",
                        "verification_status": "REFERENCE_VALIDATED",
                        "statement": (
                            "The cited observation concerns only the tracked entity and does not "
                            "identify the candidate entity"
                        ),
                        "observation_id": observation_id,
                    },
                    {
                        "kind": "ATTRIBUTE_SIMILARITY",
                        "polarity": "CHALLENGES_CANDIDACY",
                        "verification_status": "ASSERTED_NOT_VERIFIED",
                        "statement": "No attribute-level identity equivalence has been established",
                        "observation_id": None,
                    },
                ],
                candidate_id=candidate_id,
                event_id="30303030-3030-4303-8303-303030303030",
                occurred_at="2026-08-21T12:00:18Z",
            ),
            create_resolution_candidate_assessed(
                candidate_id,
                "POSSIBLE_MATCH",
                (
                    "Shared naming warrants retaining the candidate, but identity remains "
                    "unestablished"
                ),
                reviewer_label="synthetic-manual-reviewer",
                assessment_id="28282828-2828-4282-8282-282828282828",
                event_id="31313131-3131-4313-8313-313131313131",
                occurred_at="2026-08-21T12:00:19Z",
            ),
        ]
    )
    return events
