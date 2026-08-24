from __future__ import annotations

from copy import deepcopy

import pytest

from readin.contracts import ContractViolation, validate_event
from readin.events import create_entity_created
from readin.synthetic import (
    phase0_events,
    phase1_events,
    phase2_events,
    phase3_events,
    phase4_events,
    phase5_events,
    phase7_events,
)


def test_synthetic_phase0_events_conform() -> None:
    events = phase0_events()
    assert len(events) == 5
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"


def test_synthetic_phase1_events_conform() -> None:
    events = phase1_events()
    assert len(events) == 17
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"


def test_synthetic_phase2_events_conform_without_merge_authority() -> None:
    events = phase2_events()
    assert len(events) == 20
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    candidate = events[18]["payload"]["resolution_candidate"]
    assessment = events[19]["payload"]["resolution_assessment"]
    assert candidate["automatic_merge"] is False
    assert candidate["merge_state"] == "NOT_MERGED"
    assert assessment["automatic_merge"] is False
    assert assessment["merge_state"] == "NOT_MERGED"


def test_resolution_candidate_contract_rejects_merge_promotion() -> None:
    event = deepcopy(phase2_events()[18])
    event["payload"]["resolution_candidate"]["merge_state"] = "MERGED"
    with pytest.raises(ContractViolation, match="NOT_MERGED"):
        validate_event(event)


def test_synthetic_phase3_events_conform_without_execution_authority() -> None:
    events = phase3_events()
    assert len(events) == 25
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    surface = events[23]["payload"]["cartographic_surface"]
    query = events[24]["payload"]["cartographic_query_plan"]
    assert surface["coverage_state"] == "NOT_ESTABLISHED"
    assert query["direction"] == "BACKWARD"
    assert query["prediction_state"] == "NOT_REQUESTED"
    assert query["execution_state"] == "PLANNED_READ_ONLY"


def test_synthetic_phase4_events_conform_without_consensus_or_model_authority() -> None:
    events = phase4_events()
    assert len(events) == 31
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    descriptors = [event["payload"]["fitter_descriptor"] for event in events[25:28]]
    runs = [event["payload"]["fitter_run"] for event in events[28:31]]
    assert {item["fitter_class"] for item in descriptors} == {
        "BAYESIAN",
        "GRAPH",
        "TEMPORAL",
    }
    assert all(item["network_access"] is False for item in descriptors)
    assert [item["outcome"] for item in runs] == ["FIT", "FIT", "INVALID"]
    assert all(
        item["execution_receipt"]["consensus_policy"] == "PRESERVE_DISAGREEMENT" for item in runs
    )
    assert all(item["execution_receipt"]["prediction_state"] == "NOT_REQUESTED" for item in runs)


def test_synthetic_phase5_events_conform_without_probability_or_forecast_authority() -> None:
    events = phase5_events()
    assert len(events) == 37
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    revision = events[34]["payload"]["belief_revision"]
    scenario = events[35]["payload"]["scenario"]
    run = events[36]["payload"]["scenario_run"]
    assert revision["probability_state"] == "NOT_COMPUTED"
    assert revision["prediction_state"] == "NOT_REQUESTED"
    assert scenario["likelihood_state"] == "NOT_COMPUTED"
    assert any(item["kind"] == "UNKNOWN_UNMODELED" for item in scenario["branches"])
    assert run["trajectory_state"] == "NOT_SIMULATED"
    assert run["fitter_execution_state"] == "NOT_RUN_NO_FORECAST_CAPABLE_FITTER"


def test_phase5_contract_rejects_probability_and_prediction_promotion() -> None:
    revision_event = deepcopy(phase5_events()[34])
    revision_event["payload"]["belief_revision"]["probability_state"] = "COMPUTED"
    with pytest.raises(ContractViolation, match="NOT_COMPUTED"):
        validate_event(revision_event)

    scenario_event = deepcopy(phase5_events()[35])
    scenario_event["payload"]["scenario"]["prediction_state"] = "FORECAST"
    with pytest.raises(ContractViolation, match="NOT_REQUESTED"):
        validate_event(scenario_event)


def test_synthetic_phase7_events_conform_without_collection_authority() -> None:
    events = phase7_events()
    assert len(events) == 40
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    plan = events[38]["payload"]["discrimination_plan"]
    run = events[39]["payload"]["discrimination_run"]
    assert plan["collection_state"] == "NOT_STARTED"
    assert plan["policy_context"]["collection_authority"] == "NOT_GRANTED"
    assert run["acquisition_state"] == "NOT_ATTEMPTED"
    assert run["expected_information_gain_state"] == "NOT_COMPUTED"
    assert run["execution_receipt"]["network_access"] is False


def test_phase7_contract_rejects_collection_and_probability_promotion() -> None:
    plan_event = deepcopy(phase7_events()[38])
    plan_event["payload"]["discrimination_plan"]["collection_state"] = "STARTED"
    with pytest.raises(ContractViolation, match="NOT_STARTED"):
        validate_event(plan_event)

    run_event = deepcopy(phase7_events()[39])
    run_event["payload"]["discrimination_run"]["probability_state"] = "COMPUTED"
    with pytest.raises(ContractViolation, match="NOT_COMPUTED"):
        validate_event(run_event)


def test_closed_event_rejects_unknown_field() -> None:
    event = deepcopy(phase0_events()[0])
    event["unexpected"] = "not allowed"
    with pytest.raises(ContractViolation, match="Additional properties"):
        validate_event(event)


def test_authority_cannot_be_promoted() -> None:
    event = deepcopy(phase0_events()[0])
    event["authority_state"] = "EXECUTE_ACTION"
    with pytest.raises(ContractViolation, match="NO_AUTHORITY"):
        validate_event(event)


def test_naive_timestamp_is_rejected_by_factory() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        create_entity_created(
            "Example",
            "Organization",
            occurred_at="2026-08-21T12:00:00",
        )
