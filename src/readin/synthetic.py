"""Closed synthetic events for validation and the local demonstration."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from readin.belief import execute_belief_revision
from readin.discrimination import (
    create_bounded_discrimination_plan,
    execute_discrimination_plan,
)
from readin.events import (
    create_belief_edge_created,
    create_cartographic_query_planned,
    create_cartographic_surface_registered,
    create_claim_created,
    create_entity_created,
    create_evidence_dependency_declared,
    create_evidence_linked,
    create_evidence_manifested,
    create_hypothesis_created,
    create_observation_admitted,
    create_observer_frame_registered,
    create_relation_created,
    create_resolution_candidate_assessed,
    create_resolution_candidate_recorded,
    create_tracking_started,
)
from readin.fitters import (
    create_reference_fitter_registration,
    execute_reference_fitter_group,
)
from readin.forecast_fitters import register_forecast_fitter_specification
from readin.forecast_residuals import execute_forecast_residual
from readin.forecast_validity import execute_forecast_validity_assessment
from readin.forecasting import (
    create_forecast_evaluation_design,
    execute_frozen_forecast_baseline,
)
from readin.projection import ReadinProjection
from readin.readback_selection import (
    create_readback_selection_plan,
    execute_readback_selection,
)
from readin.residuals import execute_residual_readback
from readin.scenarios import create_bounded_scenario, execute_scenario


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


def phase3_events() -> list[dict[str, Any]]:
    """Return a bounded backward cartographic plan over two distinguishable frames."""

    events = phase2_events()
    entity_id = "11111111-1111-4111-8111-111111111111"
    public_record_frame_id = "22222222-2222-4222-8222-222222222222"
    analyst_frame_id = "32323232-3232-4323-8323-323232323232"
    analyst_artifact_id = "34343434-3434-4343-8343-343434343434"
    analyst_observation_id = "35353535-3535-4353-8353-353535353535"
    surface_id = "37373737-3737-4373-8373-373737373737"
    query_id = "39393939-3939-4393-8393-393939393939"
    analyst_payload = {
        "note": "Synthetic analyst interpretation outside the public-record surface",
        "disposition": "fixture_only",
    }
    analyst_bytes = json.dumps(
        analyst_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    analyst_uri = "urn:readin:synthetic:analyst-note-001"

    events.extend(
        [
            create_observer_frame_registered(
                "Synthetic analyst note",
                "analyst_note",
                access_description="Closed synthetic analyst-note fixture",
                interpretation_name="bounded_analyst_interpretation",
                interpretation_description=(
                    "A fixture-only interpretation that is not promoted to a fact"
                ),
                known_blind_regions=["Single-observer interpretation"],
                validity_conditions=["Valid only for the bundled synthetic fixture"],
                frame_id=analyst_frame_id,
                event_id="36363636-3636-4363-8363-363636363631",
                occurred_at="2026-08-21T12:00:20Z",
            ),
            create_evidence_manifested(
                hashlib.sha256(analyst_bytes).hexdigest(),
                "application/json",
                len(analyst_bytes),
                "Bundled synthetic analyst note",
                source_uri=analyst_uri,
                license_name="Apache-2.0",
                artifact_id=analyst_artifact_id,
                event_id="36363636-3636-4363-8363-363636363632",
                occurred_at="2026-08-21T12:00:21Z",
            ),
            create_observation_admitted(
                [entity_id],
                analyst_frame_id,
                analyst_artifact_id,
                "analyst_note.interpretation",
                analyst_payload,
                "2026-08-21T12:00:20Z",
                source_uri=analyst_uri,
                uncertainty={"disposition": "NOT_EVALUATED"},
                observation_id=analyst_observation_id,
                event_id="36363636-3636-4363-8363-363636363633",
                occurred_at="2026-08-21T12:00:22Z",
            ),
            create_cartographic_surface_registered(
                "Synthetic public-record surface",
                "The bundled public-record observer frame only",
                [public_record_frame_id],
                blind_region_state="DECLARED",
                blind_regions=["No independent operational verification"],
                validity_conditions=["Closed synthetic ledger only"],
                surface_id=surface_id,
                event_id="36363636-3636-4363-8363-363636363634",
                occurred_at="2026-08-21T12:00:23Z",
            ),
            create_cartographic_query_planned(
                entity_id,
                [surface_id],
                reconstruction_mode="AS_KNOWN_THEN",
                epistemic_cutoff="2026-08-21T12:00:22Z",
                max_relation_hops=1,
                include_relations=True,
                query_id=query_id,
                event_id="36363636-3636-4363-8363-363636363635",
                occurred_at="2026-08-21T12:00:24Z",
            ),
        ]
    )
    return events


def phase4_events() -> list[dict[str, Any]]:
    """Return three heterogeneous reference-fitter runs over one bounded query."""

    events = phase3_events()
    fitter_ids = [
        "61616161-6161-4616-8161-616161616161",
        "62626262-6262-4626-8262-626262626262",
        "63636363-6363-4636-8363-636363636363",
    ]
    for fitter_class, fitter_id, event_id, occurred_at in zip(
        ("BAYESIAN", "GRAPH", "TEMPORAL"),
        fitter_ids,
        (
            "64646464-6464-4646-8464-646464646461",
            "64646464-6464-4646-8464-646464646462",
            "64646464-6464-4646-8464-646464646463",
        ),
        (
            "2026-08-21T12:00:25Z",
            "2026-08-21T12:00:26Z",
            "2026-08-21T12:00:27Z",
        ),
        strict=True,
    ):
        events.append(
            create_reference_fitter_registration(
                fitter_class,
                fitter_id=fitter_id,
                event_id=event_id,
                occurred_at=occurred_at,
            )
        )

    projection = ReadinProjection.replay(events)
    run_events = execute_reference_fitter_group(
        projection,
        "39393939-3939-4393-8393-393939393939",
        fitter_ids,
        run_group_id="65656565-6565-4656-8565-656565656565",
        occurred_at="2026-08-21T12:00:28Z",
        deterministic_ids=True,
    )
    events.extend(run_events)
    return events


def phase5_events() -> list[dict[str, Any]]:
    """Return a bounded belief revision and non-predictive conditional scenario tree."""

    events = phase4_events()
    asset_id = "11111111-1111-4111-8111-111111111111"
    claim_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    upstream_hypothesis_id = "81818181-8181-4181-8181-818181818181"
    downstream_hypothesis_id = "82828282-8282-4282-8282-828282828282"
    belief_revision_id = "84848484-8484-4484-8484-848484848481"
    scenario_id = "85858585-8585-4585-8585-858585858585"
    assumption_id = "86868686-8686-4686-8686-868686868681"
    intervention_id = "86868686-8686-4686-8686-868686868682"

    hypothesis_events = [
        create_hypothesis_created(
            asset_id,
            "Program relationship remains observable",
            "The synthetic program relationship remains observable during the scenario horizon",
            [{"claim_id": claim_id, "polarity": "SUPPORTS_HYPOTHESIS"}],
            hypothesis_id=upstream_hypothesis_id,
            event_id="81818181-8181-4181-8181-818181818182",
            occurred_at="2026-08-21T12:00:29Z",
        ),
        create_hypothesis_created(
            asset_id,
            "Program activity remains conditionally relevant",
            "Program activity remains relevant if the reported relationship is support-leading",
            [],
            hypothesis_id=downstream_hypothesis_id,
            event_id="82828282-8282-4282-8282-828282828283",
            occurred_at="2026-08-21T12:00:30Z",
        ),
        create_belief_edge_created(
            upstream_hypothesis_id,
            downstream_hypothesis_id,
            "SUPPORTS_IF_SOURCE_SUPPORT_LEADING",
            "The fixture treats continued observability as a conditional relevance signal",
            edge_id="83838383-8383-4383-8383-838383838383",
            event_id="83838383-8383-4383-8383-838383838384",
            occurred_at="2026-08-21T12:00:31Z",
        ),
    ]
    projection = ReadinProjection.replay(events)
    for event in hypothesis_events:
        projection.apply(event)
        events.append(event)

    revision_event = execute_belief_revision(
        projection,
        asset_id,
        [upstream_hypothesis_id, downstream_hypothesis_id],
        revision_id=belief_revision_id,
        receipt_id="84848484-8484-4484-8484-848484848482",
        event_id="84848484-8484-4484-8484-848484848483",
        occurred_at="2026-08-21T12:00:32Z",
    )
    projection.apply(revision_event)
    events.append(revision_event)

    scenario_event = create_bounded_scenario(
        projection,
        asset_id,
        "Synthetic conditional program horizon",
        belief_revision_id,
        [asset_id],
        [
            {
                "id": assumption_id,
                "statement": "No unmodeled source changes are introduced into the fixture",
            }
        ],
        [
            {
                "id": intervention_id,
                "target_entity_id": asset_id,
                "description": "Assume the reported program relationship remains observable",
            }
        ],
        [
            {
                "id": "87878787-8787-4787-8787-878787878781",
                "name": "Conditional continuation branch",
                "outcome_statement": "Program activity remains conditionally relevant",
                "condition": {
                    "hypothesis_id": downstream_hypothesis_id,
                    "expected_state": "SUPPORT_LEADING",
                },
                "assumption_ids": [assumption_id],
                "intervention_ids": [intervention_id],
            },
            {
                "id": "87878787-8787-4787-8787-878787878782",
                "name": "Conditional challenge branch",
                "outcome_statement": "Program activity is not treated as conditionally relevant",
                "condition": {
                    "hypothesis_id": downstream_hypothesis_id,
                    "expected_state": "CHALLENGE_LEADING",
                },
                "assumption_ids": [assumption_id],
                "intervention_ids": [intervention_id],
            },
        ],
        start_time="2026-08-22T00:00:00Z",
        horizon_days=30,
        scenario_id=scenario_id,
        event_id="88888888-8888-4888-8888-888888888881",
        occurred_at="2026-08-21T12:00:33Z",
    )
    projection.apply(scenario_event)
    events.append(scenario_event)

    run_event = execute_scenario(
        projection,
        scenario_id,
        run_id="89898989-8989-4989-8989-898989898981",
        receipt_id="89898989-8989-4989-8989-898989898982",
        event_id="89898989-8989-4989-8989-898989898983",
        occurred_at="2026-08-21T12:00:34Z",
    )
    events.append(run_event)
    return events


def phase7_events() -> list[dict[str, Any]]:
    """Return a local discriminating-observation ranking without collection."""

    events = phase5_events()
    asset_id = "11111111-1111-4111-8111-111111111111"
    upstream_hypothesis_id = "81818181-8181-4181-8181-818181818181"
    downstream_hypothesis_id = "82828282-8282-4282-8282-828282828282"
    independent_frame_id = "91919191-9191-4191-8191-919191919191"

    frame_event = create_observer_frame_registered(
        "Synthetic independent technical verification",
        "independent_technical_record",
        access_description="Closed synthetic independent-verification fixture",
        measurement_name="manual_verification_recording",
        measurement_description="A user could record an authorized verification artifact",
        known_blind_regions=["No direct internal telemetry"],
        validity_conditions=["Valid only for the bundled synthetic planning fixture"],
        frame_id=independent_frame_id,
        event_id="91919191-9191-4191-8191-919191919192",
        occurred_at="2026-08-21T12:00:35Z",
    )
    events.append(frame_event)
    projection = ReadinProjection.replay(events)

    plan_event = create_bounded_discrimination_plan(
        projection,
        asset_id,
        "Resolve relationship versus activity ambiguity",
        (
            "The public relationship can remain observable while independent program "
            "activity is absent or no longer relevant"
        ),
        "84848484-8484-4484-8484-848484848481",
        "39393939-3939-4393-8393-393939393939",
        [upstream_hypothesis_id, downstream_hypothesis_id],
        [
            {
                "id": "93939393-9393-4393-8393-939393939391",
                "name": "Independent activity verification",
                "observer_frame_id": independent_frame_id,
                "observation_type": "independent_record.program_activity",
                "question": (
                    "Does an authorized independent artifact show current program activity?"
                ),
                "declared_blind_region_targets": ["No independent operational verification"],
                "expected_outcomes": [
                    {
                        "label": "Independent activity artifact observed",
                        "hypothesis_effects": [
                            {
                                "hypothesis_id": upstream_hypothesis_id,
                                "effect": "NO_EFFECT",
                            },
                            {
                                "hypothesis_id": downstream_hypothesis_id,
                                "effect": "SUPPORTS_HYPOTHESIS",
                            },
                        ],
                    },
                    {
                        "label": "Independent activity artifact absent",
                        "hypothesis_effects": [
                            {
                                "hypothesis_id": upstream_hypothesis_id,
                                "effect": "NO_EFFECT",
                            },
                            {
                                "hypothesis_id": downstream_hypothesis_id,
                                "effect": "CHALLENGES_HYPOTHESIS",
                            },
                        ],
                    },
                ],
                "effort": "MEDIUM",
            },
            {
                "id": "93939393-9393-4393-8393-939393939392",
                "name": "Public relationship follow-up",
                "observer_frame_id": "22222222-2222-4222-8222-222222222222",
                "observation_type": "public_record.relationship_follow_up",
                "question": "Does the public record still repeat the reported relationship?",
                "expected_outcomes": [
                    {
                        "label": "Relationship reiterated",
                        "hypothesis_effects": [
                            {
                                "hypothesis_id": upstream_hypothesis_id,
                                "effect": "SUPPORTS_HYPOTHESIS",
                            },
                            {
                                "hypothesis_id": downstream_hypothesis_id,
                                "effect": "SUPPORTS_HYPOTHESIS",
                            },
                        ],
                    },
                    {
                        "label": "Relationship withdrawn",
                        "hypothesis_effects": [
                            {
                                "hypothesis_id": upstream_hypothesis_id,
                                "effect": "CHALLENGES_HYPOTHESIS",
                            },
                            {
                                "hypothesis_id": downstream_hypothesis_id,
                                "effect": "CHALLENGES_HYPOTHESIS",
                            },
                        ],
                    },
                ],
                "effort": "LOW",
            },
        ],
        plan_id="92929292-9292-4292-8292-929292929291",
        event_id="92929292-9292-4292-8292-929292929292",
        occurred_at="2026-08-21T12:00:36Z",
    )
    projection.apply(plan_event)
    events.append(plan_event)

    events.append(
        execute_discrimination_plan(
            projection,
            "92929292-9292-4292-8292-929292929291",
            run_id="94949494-9494-4494-8494-949494949491",
            receipt_id="94949494-9494-4494-8494-949494949492",
            event_id="94949494-9494-4494-8494-949494949493",
            occurred_at="2026-08-21T12:00:37Z",
        )
    )
    return events


def phase8_events() -> list[dict[str, Any]]:
    """Return a predeclared target and later readback without a forecast baseline."""

    events = phase7_events()
    asset_id = "11111111-1111-4111-8111-111111111111"
    frame_id = "91919191-9191-4191-8191-919191919191"
    artifact_id = "a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a1"
    observation_id = "a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"
    payload = {
        "reported_program": "Synthetic compute research initiative",
        "readback_status": "follow_up_observed",
        "activity_score": 1.0,
        "fixture_boundary": "manual_synthetic_only",
    }
    artifact_bytes = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    source_uri = "urn:readin:synthetic:later-readback-001"

    projection = ReadinProjection.replay(events)
    events.append(
        create_forecast_evaluation_design(
            projection,
            "85858585-8585-4585-8585-858585858585",
            "Synthetic program-activity forecast evaluation",
            "independent_record.program_activity_follow_up",
            ["activity_score"],
            "synthetic_activity_index",
            training_cutoff="2026-08-21T12:00:37Z",
            design_id="a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0",
            event_id="a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a2",
            occurred_at="2026-08-21T12:00:38Z",
        )
    )

    events.append(
        create_evidence_manifested(
            hashlib.sha256(artifact_bytes).hexdigest(),
            "application/json",
            len(artifact_bytes),
            "Bundled synthetic later readback",
            source_uri=source_uri,
            license_name="Apache-2.0",
            artifact_id=artifact_id,
            event_id="a1a1a1a1-a1a1-41a1-81a1-a1a1a1a1a1a2",
            occurred_at="2026-09-22T12:00:00Z",
        )
    )
    events.append(
        create_observation_admitted(
            [asset_id],
            frame_id,
            artifact_id,
            "independent_record.program_activity_follow_up",
            payload,
            "2026-09-22T11:59:00Z",
            source_uri=source_uri,
            uncertainty={"disposition": "NOT_EVALUATED"},
            observation_id=observation_id,
            event_id="a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a3",
            occurred_at="2026-09-22T12:00:01Z",
        )
    )

    projection = ReadinProjection.replay(events)
    events.append(
        execute_residual_readback(
            projection,
            "89898989-8989-4989-8989-898989898981",
            [observation_id],
            readback_id="b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1",
            receipt_id="b2b2b2b2-b2b2-42b2-82b2-b2b2b2b2b2b2",
            event_id="b3b3b3b3-b3b3-43b3-83b3-b3b3b3b3b3b3",
            occurred_at="2026-09-22T12:00:02Z",
        )
    )
    return events


def phase8c_events() -> list[dict[str, Any]]:
    """Return a frozen pre-origin baseline plus a later observation without scoring."""

    phase8 = phase8_events()
    events = list(phase8[:41])
    projection = ReadinProjection.replay(events)
    events.append(
        execute_frozen_forecast_baseline(
            projection,
            "a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0",
            0.75,
            baseline_id="c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0",
            receipt_id="c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c1",
            event_id="c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c2",
            occurred_at="2026-08-21T12:00:39Z",
        )
    )
    events.extend(phase8[41:43])
    return events


def phase8d_events() -> list[dict[str, Any]]:
    """Return one preregistered exactly-one readback selection without scoring."""

    phase8c = phase8c_events()
    events = list(phase8c[:42])
    projection = ReadinProjection.replay(events)
    events.append(
        create_readback_selection_plan(
            projection,
            "c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0",
            ["91919191-9191-4191-8191-919191919191"],
            name="Synthetic program-activity readback aperture",
            observed_window_end="2026-09-23T00:00:00Z",
            ledger_admission_cutoff="2026-09-23T12:00:00Z",
            plan_id="d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0",
            event_id="d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d1",
            occurred_at="2026-08-21T12:00:40Z",
        )
    )
    events.extend(phase8c[42:44])
    projection = ReadinProjection.replay(events)
    events.append(
        execute_readback_selection(
            projection,
            "d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0",
            run_id="d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d0",
            receipt_id="d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d1",
            event_id="d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d2",
            occurred_at="2026-09-23T12:00:01Z",
        )
    )
    return events


def phase8e_events() -> list[dict[str, Any]]:
    """Return one descriptive residual for a uniquely selected reference readback."""

    events = phase8d_events()
    projection = ReadinProjection.replay(events)
    events.append(
        execute_forecast_residual(
            projection,
            "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d0",
            forecast_residual_id="e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0",
            receipt_id="e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e1",
            event_id="e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e2",
            occurred_at="2026-09-23T12:00:02Z",
        )
    )
    return events


def phase8f_events() -> list[dict[str, Any]]:
    """Return one fail-closed validity-update assessment for the reference residual."""

    events = phase8e_events()
    projection = ReadinProjection.replay(events)
    events.append(
        execute_forecast_validity_assessment(
            projection,
            "e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0",
            assessment_id="f0f0f0f0-f0f0-40f0-80f0-f0f0f0f0f0f0",
            receipt_id="f1f1f1f1-f1f1-41f1-81f1-f1f1f1f1f1f1",
            event_id="f2f2f2f2-f2f2-42f2-82f2-f2f2f2f2f2f2",
            occurred_at="2026-09-23T12:00:03Z",
        )
    )
    return events


def phase8g_events() -> list[dict[str, Any]]:
    """Return one prospective fitter specification after the historical abstention."""

    events = phase8f_events()
    projection = ReadinProjection.replay(events)
    events.append(
        register_forecast_fitter_specification(
            projection,
            "11111111-1111-4111-8111-111111111111",
            "Synthetic activity linear forecast candidate",
            "LINEAR_REGRESSION",
            "independent_record.program_activity_follow_up",
            ["activity_score"],
            "synthetic_activity_index",
            [
                {
                    "name": "prior_activity_score",
                    "observation_type": "independent_record.program_activity_follow_up",
                    "structured_field_path": ["activity_score"],
                    "unit": "synthetic_activity_index",
                }
            ],
            specification_id="f3f3f3f3-f3f3-43f3-83f3-f3f3f3f3f3f3",
            event_id="f4f4f4f4-f4f4-44f4-84f4-f4f4f4f4f4f4",
            occurred_at="2026-09-23T12:00:04Z",
        )
    )
    return events
