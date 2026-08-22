from __future__ import annotations

from copy import deepcopy

import pytest

from readin.contracts import ContractViolation, validate_event
from readin.events import create_entity_created
from readin.synthetic import phase0_events


def test_synthetic_phase0_events_conform() -> None:
    events = phase0_events()
    assert len(events) == 5
    for event in events:
        validate_event(event)
        assert event["authority_state"] == "NO_AUTHORITY"


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
