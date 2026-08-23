"""Bounded Phase 4 reference-fitter, receipt, validity, and disagreement behavior."""

from __future__ import annotations

from copy import deepcopy

import pytest

from readin.events import create_cartographic_query_planned
from readin.fitters import (
    FitterRuntimeError,
    canonical_sha256,
    create_reference_fitter_registration,
    evaluate_reference_admissibility,
    execute_reference_fitter_group,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase3_events, phase4_events

ASSET_ID = "11111111-1111-4111-8111-111111111111"
SURFACE_ID = "37373737-3737-4373-8373-373737373737"
PHASE3_QUERY_ID = "39393939-3939-4393-8393-393939393939"
BAYESIAN_FITTER_ID = "61616161-6161-4616-8161-616161616161"
GRAPH_FITTER_ID = "62626262-6262-4626-8262-626262626262"
TEMPORAL_FITTER_ID = "63636363-6363-4636-8363-636363636363"
RUN_GROUP_ID = "65656565-6565-4656-8565-656565656565"


def test_phase4_runs_heterogeneous_fitters_without_forcing_consensus() -> None:
    events = phase4_events()
    projection = ReadinProjection.replay(events)

    view = projection.multi_fitter_run_view(RUN_GROUP_ID)

    assert len(events) == 31
    assert view["outcome_counts"] == {"FIT": 2, "ABSTAINED": 0, "INVALID": 1}
    assert view["disagreement"] == {
        "primary_status": "MODEL_INVALIDITY_PRESENT",
        "signals": ["MODEL_INVALIDITY_PRESENT", "OUTPUTS_INCOMMENSURATE"],
        "target_metrics": [
            "DEPENDENCY_AWARE_CLAIM_SUPPORT",
            "RELATION_TOPOLOGY",
        ],
        "comparison_state": "NOT_COMPARABLE",
    }
    assert view["consensus"] == {
        "state": "NOT_COMPUTED",
        "averaging_performed": False,
        "privileged_fitter_id": None,
    }
    assert view["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert view["prediction_state"] == "NOT_REQUESTED"
    assert view["residual_readback_state"] == "NOT_PERFORMED"
    assert view["authority_state"] == "NO_AUTHORITY"
    assert len(projection.asset_view(ASSET_ID)["multi_fitter_runs"]) == 1
    assert projection.catalog_view()[0]["fit_result_count"] == 2


def test_reference_fit_results_retain_method_specific_semantics() -> None:
    projection = ReadinProjection.replay(phase4_events())
    view = projection.multi_fitter_run_view(RUN_GROUP_ID)
    runs_by_class = {item["descriptor"]["fitter_class"]: item["run"] for item in view["runs"]}

    bayesian = runs_by_class["BAYESIAN"]["fit_result"]
    assert bayesian is not None
    assert bayesian["estimate"] == {
        "kind": "DEPENDENCY_AWARE_CLAIM_SUPPORT",
        "posterior_mean": 2 / 3,
        "alpha": 2.0,
        "beta": 1.0,
        "support_units": 1,
        "challenge_units": 0,
        "conflicted_unit_count": 0,
        "dependent_source_count": 2,
        "independence_status": "DEPENDENT_EVIDENCE_PRESENT",
    }
    assert bayesian["distribution"]["interpretation"] == ("DIAGNOSTIC_INDEX_NOT_TRUTH_PROBABILITY")

    graph = runs_by_class["GRAPH"]["fit_result"]
    assert graph is not None
    assert graph["estimate"] == {
        "kind": "RELATION_TOPOLOGY",
        "directed_density": 0.5,
        "entity_count": 2,
        "relation_count": 1,
        "asset_out_degree": 1,
        "dependency_edge_count": 2,
    }
    assert graph["distribution"] is None

    temporal = runs_by_class["TEMPORAL"]
    assert temporal["outcome"] == "INVALID"
    assert temporal["fit_result"] is None
    assert temporal["admissibility"]["status"] == "INVALID"
    assert temporal["admissibility"]["reasons"] == ["hindsight query lens is allowed by the fitter"]


def test_execution_receipts_bind_input_output_and_non_authority() -> None:
    projection = ReadinProjection.replay(phase4_events())
    view = projection.multi_fitter_run_view(RUN_GROUP_ID)
    input_digests = {
        item["run"]["execution_receipt"]["input_snapshot_sha256"] for item in view["runs"]
    }
    state_versions = {
        item["run"]["execution_receipt"]["asset_state_version"] for item in view["runs"]
    }

    assert len(input_digests) == 1
    assert state_versions == {"36363636-3636-4363-8363-363636363635"}
    for item in view["runs"]:
        run = item["run"]
        receipt = run["execution_receipt"]
        assert receipt["outcome_sha256"] == canonical_sha256(
            {
                "outcome": run["outcome"],
                "admissibility": run["admissibility"],
                "fit_result": run["fit_result"],
            }
        )
        assert receipt["network_access"] is False
        assert receipt["consensus_policy"] == "PRESERVE_DISAGREEMENT"
        assert receipt["prediction_state"] == "NOT_REQUESTED"
        assert receipt["authority_state"] == "NO_AUTHORITY"


def test_phase4_replay_and_reference_ids_are_deterministic() -> None:
    first_events = phase4_events()
    second_events = phase4_events()

    assert first_events == second_events
    assert ReadinProjection.replay(first_events).multi_fitter_run_view(
        RUN_GROUP_ID
    ) == ReadinProjection.replay(second_events).multi_fitter_run_view(RUN_GROUP_ID)


def test_interrupted_append_preserves_partial_group_and_missing_fitters() -> None:
    projection = ReadinProjection.replay(phase4_events()[:29])

    view = projection.multi_fitter_run_view(RUN_GROUP_ID)

    assert view["completion_state"] == "PARTIAL"
    assert view["completed_fitter_ids"] == [BAYESIAN_FITTER_ID]
    assert view["missing_fitter_ids"] == [GRAPH_FITTER_ID, TEMPORAL_FITTER_ID]
    assert view["requested_fitter_ids"] == [
        BAYESIAN_FITTER_ID,
        GRAPH_FITTER_ID,
        TEMPORAL_FITTER_ID,
    ]


def test_registration_rejects_non_reference_implementation_digest() -> None:
    events = phase4_events()
    registration = deepcopy(events[25])
    registration["payload"]["fitter_descriptor"]["implementation_sha256"] = "0" * 64

    with pytest.raises(ProjectionError, match="does not match the reference implementation"):
        ReadinProjection.replay([*events[:25], registration])


def test_projection_recomputes_estimate_even_when_attacker_rehashes_output() -> None:
    events = phase4_events()
    run_event = deepcopy(events[28])
    run = run_event["payload"]["fitter_run"]
    run["fit_result"]["estimate"]["posterior_mean"] = 0.99
    run["execution_receipt"]["outcome_sha256"] = canonical_sha256(
        {
            "outcome": run["outcome"],
            "admissibility": run["admissibility"],
            "fit_result": run["fit_result"],
        }
    )

    with pytest.raises(ProjectionError, match="estimate does not match"):
        ReadinProjection.replay([*events[:28], run_event])


def test_projection_rejects_input_snapshot_digest_mismatch() -> None:
    events = phase4_events()
    run_event = deepcopy(events[28])
    run_event["payload"]["fitter_run"]["execution_receipt"]["input_snapshot_sha256"] = "0" * 64

    with pytest.raises(ProjectionError, match="input snapshot digest mismatch"):
        ReadinProjection.replay([*events[:28], run_event])


def test_graph_fitter_abstains_when_query_excludes_relations() -> None:
    projection = ReadinProjection.replay(phase3_events())
    projection.apply(
        create_reference_fitter_registration(
            "GRAPH",
            fitter_id=GRAPH_FITTER_ID,
            event_id="66666666-6666-4666-8666-666666666661",
            occurred_at="2026-08-21T12:00:25Z",
        )
    )
    query_id = "67676767-6767-4676-8767-676767676767"
    projection.apply(
        create_cartographic_query_planned(
            ASSET_ID,
            [SURFACE_ID],
            reconstruction_mode="AS_RECONSTRUCTED_NOW",
            max_relation_hops=0,
            include_relations=False,
            query_id=query_id,
            event_id="68686868-6868-4686-8868-686868686868",
            occurred_at="2026-08-21T12:00:26Z",
        )
    )
    event = execute_reference_fitter_group(
        projection,
        query_id,
        [GRAPH_FITTER_ID],
        run_group_id="69696969-6969-4696-8969-696969696969",
        occurred_at="2026-08-21T12:00:27Z",
        deterministic_ids=True,
    )[0]
    projection.apply(event)

    run = event["payload"]["fitter_run"]
    assert run["outcome"] == "ABSTAINED"
    assert run["admissibility"]["status"] == "INADMISSIBLE"
    assert run["fit_result"] is None


def test_temporal_fitter_executes_when_query_lens_has_no_hindsight() -> None:
    projection = ReadinProjection.replay(phase3_events())
    projection.apply(
        create_reference_fitter_registration(
            "TEMPORAL",
            fitter_id=TEMPORAL_FITTER_ID,
            event_id="70707070-7070-4707-8070-707070707070",
            occurred_at="2026-08-21T12:00:25Z",
        )
    )
    query_id = "71717171-7171-4717-8171-717171717171"
    projection.apply(
        create_cartographic_query_planned(
            ASSET_ID,
            [SURFACE_ID],
            reconstruction_mode="AS_RECONSTRUCTED_NOW",
            max_relation_hops=1,
            include_relations=True,
            query_id=query_id,
            event_id="72727272-7272-4727-8272-727272727272",
            occurred_at="2026-08-21T12:00:26Z",
        )
    )
    event = execute_reference_fitter_group(
        projection,
        query_id,
        [TEMPORAL_FITTER_ID],
        run_group_id="73737373-7373-4737-8373-737373737373",
        occurred_at="2026-08-21T12:00:27Z",
        deterministic_ids=True,
    )[0]
    projection.apply(event)

    result = event["payload"]["fitter_run"]["fit_result"]
    assert result is not None
    assert result["estimate"] == {
        "kind": "OBSERVATION_CADENCE",
        "observation_count": 3,
        "distinct_timestamp_count": 3,
        "span_seconds": 20.0,
        "median_gap_seconds": 10.0,
    }
    assert result["residuals"] == {"status": "NOT_AVAILABLE", "values": {}}
    assert result["uncertainty"] == {"status": "NOT_CALIBRATED", "interval": None}
    assert result["validity"]["status"] == "NOT_ESTABLISHED"


def test_runtime_rejects_duplicate_fitter_within_group() -> None:
    projection = ReadinProjection.replay(phase4_events()[:28])

    with pytest.raises(FitterRuntimeError, match="only once"):
        execute_reference_fitter_group(
            projection,
            PHASE3_QUERY_ID,
            [BAYESIAN_FITTER_ID, BAYESIAN_FITTER_ID],
        )


def test_bayesian_fitter_abstains_on_multi_claim_or_ungrouped_input() -> None:
    projection = ReadinProjection.replay(phase4_events()[:28])
    descriptor = projection.fitters[BAYESIAN_FITTER_ID]
    query_result = projection.execute_cartographic_query(PHASE3_QUERY_ID)

    multiple_claims = deepcopy(query_result)
    multiple_claims["claims"].append(deepcopy(multiple_claims["claims"][0]))
    multi_claim_result = evaluate_reference_admissibility(descriptor, multiple_claims)
    assert multi_claim_result["status"] == "INADMISSIBLE"
    assert "claim_count is within the fitter maximum when declared" in multi_claim_result["reasons"]

    ungrouped = deepcopy(query_result)
    ungrouped["claims"][0]["evidence_links"][0]["dependency_group"] = None
    ungrouped_result = evaluate_reference_admissibility(descriptor, ungrouped)
    assert ungrouped_result["status"] == "INADMISSIBLE"
    assert "all claim evidence links have declared dependency groups" in ungrouped_result["reasons"]
