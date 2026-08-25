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
    phase8_events,
    phase8c_events,
    phase8d_events,
    phase8e_events,
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


def test_synthetic_phase8_events_conform_without_residual_or_learning_promotion() -> None:
    events = phase8_events()
    assert len(events) == 44
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    design = events[40]["payload"]["forecast_evaluation_design"]
    assert design["preregistration_state"] == "RECORDED_BEFORE_FORECAST_ORIGIN"
    assert design["fitter_selection_state"] == "NOT_SELECTED"
    assert design["forecast_execution_state"] == "NOT_STARTED"
    assert design["prediction_state"] == "NOT_PRODUCED"

    readback = events[43]["payload"]["residual_readback"]
    assert readback["baseline_eligibility_state"] == "INELIGIBLE_NO_FORECAST_BASELINE"
    assert readback["residual_state"] == "NOT_COMPUTED"
    assert readback["validity_update_state"] == "NOT_APPLIED"
    assert readback["learning_state"] == "NOT_STARTED"
    assert readback["execution_receipt"]["network_access"] is False


def test_phase8_contract_rejects_residual_and_validity_promotion() -> None:
    forecast_event = deepcopy(phase8_events()[40])
    forecast_event["payload"]["forecast_evaluation_design"]["prediction_state"] = "PRODUCED"
    with pytest.raises(ContractViolation, match="NOT_PRODUCED"):
        validate_event(forecast_event)

    leakage_event = deepcopy(phase8_events()[40])
    leakage_event["payload"]["forecast_evaluation_design"]["timing"]["post_cutoff_input_policy"] = (
        "INCLUDE"
    )
    with pytest.raises(ContractViolation, match="EXCLUDE"):
        validate_event(leakage_event)

    residual_event = deepcopy(phase8_events()[43])
    residual_event["payload"]["residual_readback"]["residual_state"] = "COMPUTED"
    with pytest.raises(ContractViolation, match="NOT_COMPUTED"):
        validate_event(residual_event)

    validity_event = deepcopy(phase8_events()[43])
    validity_event["payload"]["residual_readback"]["validity_update_state"] = "APPLIED"
    with pytest.raises(ContractViolation, match="NOT_APPLIED"):
        validate_event(validity_event)


def test_synthetic_phase8c_baseline_conforms_without_scoring_or_learning() -> None:
    events = phase8c_events()
    assert len(events) == 44
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    baseline = events[41]["payload"]["forecast_baseline"]
    assert baseline["prediction"]["prediction_state"] == ("PRODUCED_UNCALIBRATED_BASELINE")
    assert baseline["input_boundary"]["selected_input_observation_ids"] == []
    assert baseline["calibration_state"] == "NOT_ESTABLISHED"
    assert baseline["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert baseline["residual_scoring_state"] == "NOT_ENABLED"
    assert baseline["validity_update_state"] == "NOT_APPLIED"
    assert baseline["learning_state"] == "NOT_STARTED"
    assert baseline["execution_receipt"]["network_access"] is False


def test_phase8c_contract_rejects_input_scoring_and_authority_promotion() -> None:
    selected_input = deepcopy(phase8c_events()[41])
    selected_input["payload"]["forecast_baseline"]["input_boundary"][
        "selected_input_observation_ids"
    ] = ["44444444-4444-4444-8444-444444444444"]
    with pytest.raises(ContractViolation):
        validate_event(selected_input)

    scoring = deepcopy(phase8c_events()[41])
    scoring["payload"]["forecast_baseline"]["residual_scoring_state"] = "ENABLED"
    with pytest.raises(ContractViolation, match="NOT_ENABLED"):
        validate_event(scoring)

    calibrated = deepcopy(phase8c_events()[41])
    calibrated["payload"]["forecast_baseline"]["calibration_state"] = "ESTABLISHED"
    with pytest.raises(ContractViolation, match="NOT_ESTABLISHED"):
        validate_event(calibrated)

    networked = deepcopy(phase8c_events()[41])
    networked["payload"]["forecast_baseline"]["execution_receipt"]["network_access"] = True
    with pytest.raises(ContractViolation, match="False was expected"):
        validate_event(networked)


def test_synthetic_phase8d_readback_selection_conforms_without_scoring() -> None:
    events = phase8d_events()
    assert len(events) == 46
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    plan = events[42]["payload"]["readback_selection_plan"]
    run = events[45]["payload"]["readback_selection_run"]
    assert plan["selection_policy"]["cardinality"] == "EXACTLY_ONE"
    assert plan["selection_policy"]["aggregation_policy"] == "PROHIBITED"
    assert plan["selection_policy"]["post_hoc_selection_policy"] == "PROHIBITED"
    assert run["selection_state"] == "UNIQUE_MATCH_SELECTED"
    assert run["residual_state"] == "NOT_COMPUTED"
    assert run["residual_scoring_state"] == "NOT_ENABLED"
    assert run["calibration_state"] == "NOT_ESTABLISHED"
    assert run["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert run["validity_update_state"] == "NOT_APPLIED"
    assert run["execution_receipt"]["network_access"] is False


def test_phase8d_contract_rejects_aggregation_scoring_and_network_promotion() -> None:
    aggregation = deepcopy(phase8d_events()[42])
    aggregation["payload"]["readback_selection_plan"]["selection_policy"]["aggregation_policy"] = (
        "AVERAGE"
    )
    with pytest.raises(ContractViolation, match="PROHIBITED"):
        validate_event(aggregation)

    scoring = deepcopy(phase8d_events()[45])
    scoring["payload"]["readback_selection_run"]["residual_state"] = "COMPUTED"
    with pytest.raises(ContractViolation, match="NOT_COMPUTED"):
        validate_event(scoring)

    networked = deepcopy(phase8d_events()[45])
    networked["payload"]["readback_selection_run"]["execution_receipt"]["network_access"] = True
    with pytest.raises(ContractViolation, match="False was expected"):
        validate_event(networked)


def test_synthetic_phase8e_descriptive_residual_conforms_without_validity() -> None:
    events = phase8e_events()
    assert len(events) == 47
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"

    residual = events[46]["payload"]["forecast_residual"]
    assert residual["selection_eligibility_state"] == "UNIQUE_MATCH_CONFIRMED"
    assert residual["sample_count"] == 1
    assert residual["score"]["signed_residual"] == 0.25
    assert residual["score"]["absolute_error"] == 0.25
    assert residual["residual_state"] == "COMPUTED_DESCRIPTIVE_REFERENCE_ONLY"
    assert residual["uncertainty_state"] == "NOT_ESTIMATED_SINGLE_READBACK"
    assert residual["calibration_state"] == "NOT_ESTABLISHED"
    assert residual["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert residual["validity_update_state"] == "NOT_APPLIED"
    assert residual["learning_state"] == "NOT_STARTED"
    assert residual["execution_receipt"]["network_access"] is False


def test_phase8e_contract_rejects_validity_unit_and_network_promotion() -> None:
    calibrated = deepcopy(phase8e_events()[46])
    calibrated["payload"]["forecast_residual"]["calibration_state"] = "ESTABLISHED"
    with pytest.raises(ContractViolation, match="NOT_ESTABLISHED"):
        validate_event(calibrated)

    validity = deepcopy(phase8e_events()[46])
    validity["payload"]["forecast_residual"]["validity_update_state"] = "APPLIED"
    with pytest.raises(ContractViolation, match="NOT_APPLIED"):
        validate_event(validity)

    unit_verified = deepcopy(phase8e_events()[46])
    unit_verified["payload"]["forecast_residual"]["score"]["unit_match_state"] = "VERIFIED"
    with pytest.raises(ContractViolation, match="USER_DECLARED_NOT_VERIFIED"):
        validate_event(unit_verified)

    networked = deepcopy(phase8e_events()[46])
    networked["payload"]["forecast_residual"]["execution_receipt"]["network_access"] = True
    with pytest.raises(ContractViolation, match="False was expected"):
        validate_event(networked)


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
