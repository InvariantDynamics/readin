from __future__ import annotations

from copy import deepcopy

import pytest

from readin.events import (
    create_resolution_candidate_assessed,
    create_resolution_candidate_recorded,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase1_events, phase2_events


def _user_signal(statement: str = "Manual candidate signal") -> dict[str, object]:
    return {
        "kind": "USER_ASSERTION",
        "polarity": "SUPPORTS_CANDIDACY",
        "verification_status": "ASSERTED_NOT_VERIFIED",
        "statement": statement,
        "observation_id": None,
    }


def test_phase2_candidate_remains_reversible_and_unmerged() -> None:
    events = phase2_events()
    projection = ReadinProjection.replay(events)
    candidate_id = events[18]["payload"]["resolution_candidate"]["id"]

    view = projection.resolution_candidate_view(candidate_id)

    assert len(events) == 20
    assert len(projection.entities) == 3
    assert view["current_disposition"] == "POSSIBLE_MATCH"
    assert len(view["assessments"]) == 1
    assert view["reversible"] is True
    assert view["automatic_merge"] is False
    assert view["merge_state"] == "NOT_MERGED"
    assert view["authority_state"] == "NO_AUTHORITY"


def test_resolution_candidate_entities_must_differ() -> None:
    events = phase1_events()
    candidate = create_resolution_candidate_recorded(
        "11111111-1111-4111-8111-111111111111",
        "11111111-1111-4111-8111-111111111111",
        [_user_signal()],
        event_id="32323232-3232-4323-8323-323232323232",
        occurred_at="2026-08-21T12:00:17Z",
    )

    with pytest.raises(ProjectionError, match="must differ"):
        ReadinProjection.replay([*events, candidate])


def test_resolution_candidate_must_involve_a_tracked_entity() -> None:
    events = phase2_events()
    candidate = create_resolution_candidate_recorded(
        "55555555-5555-4555-8555-555555555555",
        "26262626-2626-4262-8262-262626262626",
        [_user_signal()],
        event_id="33333333-3333-4333-8333-333333333339",
        occurred_at="2026-08-21T12:00:18Z",
    )

    with pytest.raises(ProjectionError, match="at least one tracked entity"):
        ReadinProjection.replay([*events[:18], candidate])


def test_resolution_candidate_pair_is_unique_regardless_of_order() -> None:
    events = phase2_events()
    duplicate = create_resolution_candidate_recorded(
        "26262626-2626-4262-8262-262626262626",
        "11111111-1111-4111-8111-111111111111",
        [_user_signal("Reversed duplicate pair")],
        event_id="34343434-3434-4343-8343-343434343434",
        occurred_at="2026-08-21T12:00:19Z",
    )

    with pytest.raises(ProjectionError, match="already exists"):
        ReadinProjection.replay([*events[:19], duplicate])


def test_observation_resolution_signal_must_reference_known_observation() -> None:
    events = phase2_events()
    changed = deepcopy(events[18])
    changed["payload"]["resolution_candidate"]["signals"][1]["observation_id"] = (
        "35353535-3535-4353-8353-353535353535"
    )

    with pytest.raises(ProjectionError, match="unknown observation"):
        ReadinProjection.replay([*events[:18], changed])


def test_observation_signal_requires_reference_validated_status() -> None:
    events = phase2_events()
    changed = deepcopy(events[18])
    changed["payload"]["resolution_candidate"]["signals"][1]["verification_status"] = (
        "ASSERTED_NOT_VERIFIED"
    )

    with pytest.raises(ProjectionError, match="requires REFERENCE_VALIDATED"):
        ReadinProjection.replay([*events[:18], changed])


def test_validated_shared_alias_requires_exact_entity_record_match() -> None:
    events = phase2_events()
    changed_entity = deepcopy(events[17])
    changed_entity["payload"]["entity"]["aliases"] = ["Different synthetic alias"]

    with pytest.raises(ProjectionError, match="no exact entity-record match"):
        ReadinProjection.replay([*events[:17], changed_entity, events[18]])


def test_contradiction_signal_must_challenge_candidacy() -> None:
    events = phase2_events()
    changed = deepcopy(events[18])
    changed["payload"]["resolution_candidate"]["signals"][0]["kind"] = "CONTRADICTION"

    with pytest.raises(ProjectionError, match="must challenge"):
        ReadinProjection.replay([*events[:18], changed])


def test_reassessment_must_supersede_latest_and_remains_non_merging() -> None:
    events = phase2_events()
    reassessment = create_resolution_candidate_assessed(
        "27272727-2727-4272-8272-272727272727",
        "RETAIN_SEPARATE",
        "The later manual review does not establish identity equivalence",
        reviewer_label="second-synthetic-reviewer",
        supersedes_assessment_id="28282828-2828-4282-8282-282828282828",
        assessment_id="36363636-3636-4363-8363-363636363636",
        event_id="37373737-3737-4373-8373-373737373737",
        occurred_at="2026-08-21T12:00:20Z",
    )

    projection = ReadinProjection.replay([*events, reassessment])
    view = projection.resolution_candidate_view("27272727-2727-4272-8272-272727272727")

    assert len(view["assessments"]) == 2
    assert [item["disposition"] for item in view["assessments"]] == [
        "POSSIBLE_MATCH",
        "RETAIN_SEPARATE",
    ]
    assert view["current_disposition"] == "RETAIN_SEPARATE"
    assert view["merge_state"] == "NOT_MERGED"


def test_reassessment_without_latest_supersession_is_rejected() -> None:
    events = phase2_events()
    reassessment = create_resolution_candidate_assessed(
        "27272727-2727-4272-8272-272727272727",
        "CONFIRMED_MATCH_NOT_MERGED",
        "Synthetic reassessment intentionally omits its predecessor",
        assessment_id="38383838-3838-4383-8383-383838383838",
        event_id="39393939-3939-4393-8393-393939393939",
        occurred_at="2026-08-21T12:00:20Z",
    )

    with pytest.raises(ProjectionError, match="must supersede"):
        ReadinProjection.replay([*events, reassessment])


def test_reassessment_effective_time_cannot_precede_latest_assessment() -> None:
    events = phase2_events()
    reassessment = create_resolution_candidate_assessed(
        "27272727-2727-4272-8272-272727272727",
        "RETAIN_SEPARATE",
        "Synthetic reassessment intentionally backdates its effective review time",
        supersedes_assessment_id="28282828-2828-4282-8282-282828282828",
        assessment_id="41414141-4141-4414-8414-414141414141",
        assessed_at="2026-08-21T12:00:18Z",
        event_id="42424242-4242-4424-8424-424242424242",
        occurred_at="2026-08-21T12:00:20Z",
    )

    with pytest.raises(ProjectionError, match="assessed_at precedes"):
        ReadinProjection.replay([*events, reassessment])


def test_candidate_history_respects_epistemic_cutoff() -> None:
    events = phase2_events()
    projection = ReadinProjection.replay(events)
    entity_id = "11111111-1111-4111-8111-111111111111"
    cutoff = "2026-08-21T12:00:18Z"

    known_then = projection.asset_view_at(
        entity_id,
        mode="AS_KNOWN_THEN",
        epistemic_cutoff=cutoff,
    )
    reconstructed = projection.asset_view_at(
        entity_id,
        mode="AS_RECONSTRUCTED_NOW",
        epistemic_cutoff=cutoff,
    )

    assert known_then["resolution_candidates"][0]["current_disposition"] == "PENDING_REVIEW"
    assert reconstructed["resolution_candidates"][0]["current_disposition"] == "POSSIBLE_MATCH"
    assert reconstructed["reconstruction"]["hindsight_included"] is True
    assert any(
        item["event_type"] == "entity.resolution_candidate_assessed" and item["hindsight"]
        for item in reconstructed["timeline"]
    )
