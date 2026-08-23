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
