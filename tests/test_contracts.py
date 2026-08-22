from __future__ import annotations

from copy import deepcopy

import pytest

from readin.contracts import ContractViolation, validate_event
from readin.events import create_entity_created
from readin.synthetic import phase0_events, phase1_events, phase2_events


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
