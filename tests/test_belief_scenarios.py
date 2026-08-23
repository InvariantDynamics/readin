"""Bounded Phase 5 belief propagation and non-predictive scenario behavior."""

from __future__ import annotations

from copy import deepcopy

import pytest

from readin.belief import BeliefRuntimeError, execute_belief_revision
from readin.events import create_belief_edge_created
from readin.fitters import canonical_sha256
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase5_events

ASSET_ID = "11111111-1111-4111-8111-111111111111"
UPSTREAM_HYPOTHESIS_ID = "81818181-8181-4181-8181-818181818181"
DOWNSTREAM_HYPOTHESIS_ID = "82828282-8282-4282-8282-828282828282"
BELIEF_REVISION_ID = "84848484-8484-4484-8484-848484848481"
SCENARIO_ID = "85858585-8585-4585-8585-858585858585"
SCENARIO_RUN_ID = "89898989-8989-4989-8989-898989898981"


def test_phase5_replays_belief_and_scenario_state_without_prediction() -> None:
    events = phase5_events()
    projection = ReadinProjection.replay(events)
    asset = projection.asset_view(ASSET_ID)

    assert len(events) == 37
    assert asset["tracked_asset"]["active_hypotheses"] == [
        UPSTREAM_HYPOTHESIS_ID,
        DOWNSTREAM_HYPOTHESIS_ID,
    ]
    assert asset["tracked_asset"]["active_scenarios"] == [SCENARIO_ID]
    assert len(asset["belief_revisions"]) == 1
    assert len(asset["scenarios"]) == 1
    assert projection.catalog_view()[0]["scenario_run_count"] == 1
    assert all(event["authority_state"] == "NO_AUTHORITY" for event in events)


def test_belief_revision_deduplicates_ancestry_and_propagates_categorical_state() -> None:
    projection = ReadinProjection.replay(phase5_events())
    revision = projection.belief_revision_view(BELIEF_REVISION_ID)["revision"]
    results = {item["hypothesis_id"]: item for item in revision["node_results"]}

    upstream = results[UPSTREAM_HYPOTHESIS_ID]
    assert upstream["direct_support_unit_count"] == 1
    assert upstream["dependency_group_ids"] == ["dddddddd-dddd-4ddd-8ddd-dddddddddddd"]
    assert upstream["state"] == "SUPPORT_LEADING"
    assert upstream["interpretation"] == ("DIAGNOSTIC_SIGNAL_BALANCE_NOT_TRUTH_PROBABILITY")

    downstream = results[DOWNSTREAM_HYPOTHESIS_ID]
    assert downstream["direct_support_unit_count"] == 0
    assert downstream["conditional_support_unit_count"] == 1
    assert downstream["state"] == "SUPPORT_LEADING"
    assert downstream["incoming_edge_evaluations"][0]["disposition"] == "APPLIED_SUPPORT"
    assert revision["probability_state"] == "NOT_COMPUTED"
    assert revision["uncertainty_state"] == "NOT_CALIBRATED"
    assert revision["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert revision["prediction_state"] == "NOT_REQUESTED"


def test_belief_receipt_binds_complete_graph_and_non_authority() -> None:
    projection = ReadinProjection.replay(phase5_events())
    revision = projection.belief_revisions[BELIEF_REVISION_ID]
    receipt = revision["execution_receipt"]

    assert receipt["hypothesis_ids"] == [
        UPSTREAM_HYPOTHESIS_ID,
        DOWNSTREAM_HYPOTHESIS_ID,
    ]
    assert receipt["belief_edge_ids"] == ["83838383-8383-4383-8383-838383838383"]
    assert len(receipt["evidence_link_ids"]) == 3
    assert len(receipt["dependency_ids"]) == 2
    assert receipt["network_access"] is False
    assert receipt["probability_state"] == "NOT_COMPUTED"
    assert receipt["prediction_state"] == "NOT_REQUESTED"
    assert receipt["authority_state"] == "NO_AUTHORITY"


def test_scenario_retains_unknown_branch_without_likelihood_or_trajectory() -> None:
    projection = ReadinProjection.replay(phase5_events())
    view = projection.scenario_run_view(SCENARIO_RUN_ID)
    run = view["run"]
    states = {item["antecedent_state"] for item in run["branch_results"]}

    assert states == {
        "CONDITION_MATCHED",
        "CONDITION_NOT_MATCHED",
        "UNMODELED_REGION_RETAINED",
    }
    assert run["summary"] == {
        "conditional_branch_count": 2,
        "matched_branch_count": 1,
        "unresolved_branch_count": 0,
        "unknown_branch_visible": True,
    }
    assert run["fitter_execution_state"] == "NOT_RUN_NO_FORECAST_CAPABLE_FITTER"
    assert run["likelihood_state"] == "NOT_COMPUTED"
    assert run["trajectory_state"] == "NOT_SIMULATED"
    assert run["prediction_state"] == "NOT_REQUESTED"
    assert run["empirical_validity_state"] == "NOT_ESTABLISHED"
    unknown = next(
        item for item in run["branch_results"] if item["branch_kind"] == "UNKNOWN_UNMODELED"
    )
    assert unknown["trajectory_state"] == "UNMODELED_NOT_SIMULATED"
    assert view["authority_state"] == "NO_AUTHORITY"


def test_phase5_fixture_and_receipts_are_deterministic() -> None:
    first = phase5_events()
    second = phase5_events()

    assert first == second
    assert ReadinProjection.replay(first).scenario_run_view(
        SCENARIO_RUN_ID
    ) == ReadinProjection.replay(second).scenario_run_view(SCENARIO_RUN_ID)


def test_belief_graph_rejects_cycle() -> None:
    projection = ReadinProjection.replay(phase5_events())
    reverse_edge = create_belief_edge_created(
        DOWNSTREAM_HYPOTHESIS_ID,
        UPSTREAM_HYPOTHESIS_ID,
        "SUPPORTS_IF_SOURCE_SUPPORT_LEADING",
        "Invalid reverse edge",
        edge_id="90909090-9090-4090-8090-909090909091",
        event_id="90909090-9090-4090-8090-909090909092",
        occurred_at="2026-08-21T12:00:35Z",
    )

    with pytest.raises(ProjectionError, match="create a cycle"):
        projection.apply(reverse_edge)


def test_belief_revision_rejects_incomplete_upstream_selection() -> None:
    projection = ReadinProjection.replay(phase5_events()[:34])

    with pytest.raises(BeliefRuntimeError, match="omits upstream"):
        execute_belief_revision(
            projection,
            ASSET_ID,
            [DOWNSTREAM_HYPOTHESIS_ID],
        )


def test_projection_recomputes_tampered_belief_result() -> None:
    events = phase5_events()
    revision_event = deepcopy(events[34])
    revision = revision_event["payload"]["belief_revision"]
    revision["node_results"][0]["direct_support_unit_count"] = 99
    components = {
        key: revision[key]
        for key in (
            "graph",
            "node_results",
            "probability_state",
            "uncertainty_state",
            "empirical_validity_state",
            "prediction_state",
        )
    }
    revision["execution_receipt"]["outcome_sha256"] = canonical_sha256(components)

    with pytest.raises(ProjectionError, match="node_results does not match"):
        ReadinProjection.replay([*events[:34], revision_event])


def test_projection_rejects_belief_input_digest_tampering() -> None:
    events = phase5_events()
    revision_event = deepcopy(events[34])
    revision_event["payload"]["belief_revision"]["execution_receipt"]["input_snapshot_sha256"] = (
        "0" * 64
    )

    with pytest.raises(ProjectionError, match="input snapshot digest mismatch"):
        ReadinProjection.replay([*events[:34], revision_event])


def test_scenario_requires_visible_unknown_branch() -> None:
    events = phase5_events()
    scenario_event = deepcopy(events[35])
    scenario = scenario_event["payload"]["scenario"]
    scenario["branches"] = [
        item for item in scenario["branches"] if item["kind"] != "UNKNOWN_UNMODELED"
    ]

    with pytest.raises(ProjectionError, match="exactly one unknown"):
        ReadinProjection.replay([*events[:35], scenario_event])


def test_projection_recomputes_tampered_scenario_result() -> None:
    events = phase5_events()
    run_event = deepcopy(events[36])
    run = run_event["payload"]["scenario_run"]
    run["branch_results"][0]["antecedent_state"] = "CONDITION_NOT_MATCHED"
    components = {
        key: run[key]
        for key in (
            "branch_results",
            "summary",
            "fitter_execution_state",
            "likelihood_state",
            "trajectory_state",
            "prediction_state",
            "empirical_validity_state",
        )
    }
    run["execution_receipt"]["outcome_sha256"] = canonical_sha256(components)

    with pytest.raises(ProjectionError, match="scenario receipt binding mismatch"):
        ReadinProjection.replay([*events[:36], run_event])
