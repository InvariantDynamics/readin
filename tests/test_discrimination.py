"""Phase 7 discriminating-observation planning without acquisition."""

from __future__ import annotations

from copy import deepcopy

import pytest

from readin.discrimination import (
    DiscriminationRuntimeError,
    create_bounded_discrimination_plan,
    execute_discrimination_plan,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase7_events

ASSET_ID = "11111111-1111-4111-8111-111111111111"
UPSTREAM_ID = "81818181-8181-4181-8181-818181818181"
DOWNSTREAM_ID = "82828282-8282-4282-8282-828282828282"
REVISION_ID = "84848484-8484-4484-8484-848484848481"
QUERY_ID = "39393939-3939-4393-8393-393939393939"
FRAME_ID = "91919191-9191-4191-8191-919191919191"
PLAN_ID = "92929292-9292-4292-8292-929292929291"
RUN_ID = "94949494-9494-4494-8494-949494949491"
TOP_CANDIDATE_ID = "93939393-9393-4393-8393-939393939391"


def _candidate(
    candidate_id: str,
    *,
    name: str,
    question: str,
    effects: tuple[str, str] = ("NO_EFFECT", "SUPPORTS_HYPOTHESIS"),
) -> dict[str, object]:
    return {
        "id": candidate_id,
        "name": name,
        "observer_frame_id": FRAME_ID,
        "observation_type": f"manual.{candidate_id[-4:]}",
        "question": question,
        "expected_outcomes": [
            {
                "label": "Declared outcome",
                "hypothesis_effects": [
                    {"hypothesis_id": UPSTREAM_ID, "effect": effects[0]},
                    {"hypothesis_id": DOWNSTREAM_ID, "effect": effects[1]},
                ],
            }
        ],
        "effort": "NOT_EVALUATED",
    }


def _base_projection() -> ReadinProjection:
    return ReadinProjection.replay(phase7_events()[:38])


def test_phase7_ranks_structural_discrimination_without_collection() -> None:
    events = phase7_events()
    projection = ReadinProjection.replay(events)
    view = projection.discrimination_run_view(RUN_ID)
    run = view["run"]

    assert len(events) == 40
    assert run["recommendation_state"] == "RANKED_STRUCTURAL_CANDIDATES"
    assert run["top_candidate_ids"] == [TOP_CANDIDATE_ID]
    assert [(item["rank"], item["discrimination_state"]) for item in run["candidate_scores"]] == [
        (1, "DISCRIMINATING"),
        (None, "NON_DISCRIMINATING"),
    ]
    assert run["collection_state"] == "NOT_STARTED"
    assert run["acquisition_state"] == "NOT_ATTEMPTED"
    assert run["expected_information_gain_state"] == "NOT_COMPUTED"
    assert run["probability_state"] == "NOT_COMPUTED"
    assert run["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert run["execution_receipt"]["network_access"] is False
    assert view["source_independence_state"] == "NOT_ESTABLISHED"
    assert view["authority_state"] == "NO_AUTHORITY"
    assert projection.catalog_view()[0]["discrimination_run_count"] == 1


def test_phase7_fixture_and_receipt_are_deterministic() -> None:
    first = phase7_events()
    second = phase7_events()

    assert first == second
    assert ReadinProjection.replay(first).discrimination_run_view(
        RUN_ID
    ) == ReadinProjection.replay(second).discrimination_run_view(RUN_ID)


def test_ranking_preserves_top_ties() -> None:
    projection = _base_projection()
    event = create_bounded_discrimination_plan(
        projection,
        ASSET_ID,
        "Tie fixture",
        "Two declared candidates are structurally indistinguishable",
        REVISION_ID,
        QUERY_ID,
        [UPSTREAM_ID, DOWNSTREAM_ID],
        [
            _candidate(
                "95959595-9595-4595-8595-959595959591",
                name="Candidate one",
                question="Could source one discriminate?",
            ),
            _candidate(
                "95959595-9595-4595-8595-959595959592",
                name="Candidate two",
                question="Could source two discriminate?",
            ),
        ],
        plan_id="95959595-9595-4595-8595-959595959593",
        event_id="95959595-9595-4595-8595-959595959594",
        occurred_at="2026-08-21T12:00:36Z",
    )
    projection.apply(event)
    run_event = execute_discrimination_plan(
        projection,
        "95959595-9595-4595-8595-959595959593",
        run_id="95959595-9595-4595-8595-959595959595",
        receipt_id="95959595-9595-4595-8595-959595959596",
        event_id="95959595-9595-4595-8595-959595959597",
        occurred_at="2026-08-21T12:00:37Z",
    )
    projection.apply(run_event)
    scores = projection.discrimination_run_view("95959595-9595-4595-8595-959595959595")["run"][
        "candidate_scores"
    ]

    assert [item["rank"] for item in scores] == [1, 1]
    assert all(item["tie_state"] == "TIED_AT_RANK" for item in scores)


def test_ranking_abstains_when_candidates_do_not_distinguish_hypotheses() -> None:
    projection = _base_projection()
    event = create_bounded_discrimination_plan(
        projection,
        ASSET_ID,
        "Abstention fixture",
        "The declared candidate affects both hypotheses identically",
        REVISION_ID,
        QUERY_ID,
        [UPSTREAM_ID, DOWNSTREAM_ID],
        [
            _candidate(
                "96969696-9696-4696-8696-969696969691",
                name="Redundant candidate",
                question="Does this restate the same signal?",
                effects=("SUPPORTS_HYPOTHESIS", "SUPPORTS_HYPOTHESIS"),
            )
        ],
        plan_id="96969696-9696-4696-8696-969696969692",
        event_id="96969696-9696-4696-8696-969696969693",
        occurred_at="2026-08-21T12:00:36Z",
    )
    projection.apply(event)
    run_event = execute_discrimination_plan(
        projection,
        "96969696-9696-4696-8696-969696969692",
        run_id="96969696-9696-4696-8696-969696969694",
        receipt_id="96969696-9696-4696-8696-969696969695",
        event_id="96969696-9696-4696-8696-969696969696",
        occurred_at="2026-08-21T12:00:37Z",
    )
    projection.apply(run_event)
    run = projection.discrimination_run_view("96969696-9696-4696-8696-969696969694")["run"]

    assert run["recommendation_state"] == "ABSTAINED_NO_DISCRIMINATING_CANDIDATE"
    assert run["top_candidate_ids"] == []
    assert run["candidate_scores"][0]["rank"] is None


def test_factory_rejects_duplicate_target_hypotheses() -> None:
    projection = _base_projection()

    with pytest.raises(DiscriminationRuntimeError, match="must be unique"):
        create_bounded_discrimination_plan(
            projection,
            ASSET_ID,
            "Invalid duplicate targets",
            "Duplicate hypothesis bindings are invalid",
            REVISION_ID,
            QUERY_ID,
            [UPSTREAM_ID, UPSTREAM_ID],
            [_candidate("97979797-9797-4797-8797-979797979791", name="One", question="One?")],
        )


def test_projection_rejects_unknown_blind_region_target() -> None:
    events = phase7_events()
    plan_event = deepcopy(events[38])
    plan_event["payload"]["discrimination_plan"]["candidates"][0][
        "declared_blind_region_targets"
    ] = ["Invented blind region"]

    with pytest.raises(ProjectionError, match="unknown query blind regions"):
        ReadinProjection.replay([*events[:38], plan_event])


def test_projection_requires_exact_hypothesis_effect_coverage() -> None:
    events = phase7_events()
    plan_event = deepcopy(events[38])
    effects = plan_event["payload"]["discrimination_plan"]["candidates"][0]["expected_outcomes"][0][
        "hypothesis_effects"
    ]
    effects[1]["hypothesis_id"] = UPSTREAM_ID

    with pytest.raises(ProjectionError, match="must cover every target hypothesis"):
        ReadinProjection.replay([*events[:38], plan_event])


def test_projection_recomputes_ranking_and_rejects_tampering() -> None:
    events = phase7_events()
    run_event = deepcopy(events[39])
    run_event["payload"]["discrimination_run"]["candidate_scores"][0]["rank"] = 2

    with pytest.raises(ProjectionError, match="does not match reference ranking"):
        ReadinProjection.replay([*events[:39], run_event])


def test_projection_rejects_second_run_for_bounded_plan() -> None:
    projection = ReadinProjection.replay(phase7_events())
    second = execute_discrimination_plan(
        projection,
        PLAN_ID,
        run_id="98989898-9898-4898-8898-989898989891",
        receipt_id="98989898-9898-4898-8898-989898989892",
        event_id="98989898-9898-4898-8898-989898989893",
        occurred_at="2026-08-21T12:00:38Z",
    )

    with pytest.raises(ProjectionError, match="already has a completed run"):
        projection.apply(second)
