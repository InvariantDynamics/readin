from __future__ import annotations

from copy import deepcopy

import pytest

from readin.projection import ProjectionError, ReadinProjection
from readin.readback_selection import (
    ReadbackSelectionError,
    create_readback_selection_plan,
    execute_readback_selection,
)
from readin.residuals import ResidualRuntimeError, build_residual_snapshot
from readin.synthetic import phase8c_events, phase8d_events

PLAN_ID = "d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0"
RUN_ID = "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d0"
BASELINE_ID = "c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0"
FRAME_ID = "91919191-9191-4191-8191-919191919191"
SCENARIO_RUN_ID = "89898989-8989-4989-8989-898989898981"


def _plan_event(
    projection: ReadinProjection,
    *,
    window_end: str = "2026-09-23T00:00:00Z",
) -> dict:
    return create_readback_selection_plan(
        projection,
        BASELINE_ID,
        [FRAME_ID],
        name="Test readback aperture",
        observed_window_end=window_end,
        ledger_admission_cutoff="2026-09-23T12:00:00Z",
        plan_id=PLAN_ID,
        event_id="d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d1",
        occurred_at="2026-08-21T12:00:40Z",
    )


def test_phase8d_selects_one_readback_without_scoring_or_learning() -> None:
    events = phase8d_events()
    assert len(events) == 46
    projection = ReadinProjection.replay(events)
    view = projection.readback_selection_run_view(RUN_ID)
    run = view["run"]

    assert run["selection_state"] == "UNIQUE_MATCH_SELECTED"
    assert run["candidate_count"] == 1
    assert run["candidate_observation_ids"] == ["a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"]
    assert run["selected_target_value"] == 1.0
    assert run["aggregation_state"] == "NOT_PERFORMED"
    assert run["ranking_state"] == "NOT_PERFORMED"
    assert run["unit_match_state"] == "USER_DECLARED_NOT_VERIFIED"
    assert run["residual_state"] == "NOT_COMPUTED"
    assert run["residual_scoring_state"] == "NOT_ENABLED"
    assert run["calibration_state"] == "NOT_ESTABLISHED"
    assert run["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert run["validity_update_state"] == "NOT_APPLIED"
    assert run["learning_state"] == "NOT_STARTED"
    assert run["execution_receipt"]["network_access"] is False
    assert run["authority_state"] == "NO_AUTHORITY"


def test_phase8d_fixture_and_execution_are_deterministic() -> None:
    assert phase8d_events() == phase8d_events()


def test_selection_abstains_when_no_observation_is_inside_frozen_window() -> None:
    phase8c = phase8c_events()
    events = list(phase8c[:42])
    projection = ReadinProjection.replay(events)
    events.append(_plan_event(projection, window_end="2026-09-21T12:00:00Z"))
    events.extend(phase8c[42:44])
    projection = ReadinProjection.replay(events)
    event = execute_readback_selection(
        projection,
        PLAN_ID,
        run_id=RUN_ID,
        receipt_id="d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d1",
        event_id="d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d2",
        occurred_at="2026-09-23T12:00:01Z",
    )
    run = event["payload"]["readback_selection_run"]
    assert run["selection_state"] == "ABSTAINED_NO_MATCH"
    assert run["selected_observation_id"] is None
    assert (
        "a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"
        in run["excluded_outside_observed_window_observation_ids"]
    )


def test_selection_abstains_on_multiple_matches_without_ranking_or_aggregation() -> None:
    events = phase8d_events()[:-1]
    extra_manifest = deepcopy(events[-2])
    extra_manifest["event_id"] = "e0e0e0e0-e0e0-40e0-80e0-e0e0e0e0e0e0"
    extra_manifest["occurred_at"] = "2026-09-22T12:00:02Z"
    extra_manifest["payload"]["evidence_manifest"]["id"] = "e1e1e1e1-e1e1-41e1-81e1-e1e1e1e1e1e1"
    extra_manifest["payload"]["evidence_manifest"]["sha256"] = "e" * 64
    extra_observation = deepcopy(events[-1])
    extra_observation["event_id"] = "e2e2e2e2-e2e2-42e2-82e2-e2e2e2e2e2e2"
    extra_observation["occurred_at"] = "2026-09-22T12:00:03Z"
    extra_observation["payload"]["observation"]["id"] = "e3e3e3e3-e3e3-43e3-83e3-e3e3e3e3e3e3"
    extra_observation["payload"]["observation"]["source_artifact_id"] = (
        "e1e1e1e1-e1e1-41e1-81e1-e1e1e1e1e1e1"
    )
    events.extend([extra_manifest, extra_observation])
    projection = ReadinProjection.replay(events)
    run = execute_readback_selection(
        projection,
        PLAN_ID,
        occurred_at="2026-09-23T12:00:01Z",
    )["payload"]["readback_selection_run"]
    assert run["selection_state"] == "ABSTAINED_MULTIPLE_MATCHES"
    assert run["candidate_count"] == 2
    assert run["selected_observation_id"] is None
    assert run["aggregation_state"] == "NOT_PERFORMED"
    assert run["ranking_state"] == "NOT_PERFORMED"


def test_plan_rejects_unknown_duplicate_and_invalid_temporal_bindings() -> None:
    projection = ReadinProjection.replay(phase8c_events()[:42])
    with pytest.raises(ReadbackSelectionError, match="unknown forecast baseline"):
        create_readback_selection_plan(
            projection,
            "00000000-0000-4000-8000-000000000000",
            [FRAME_ID],
            name="Invalid",
            observed_window_end="2026-09-23T00:00:00Z",
            ledger_admission_cutoff="2026-09-23T12:00:00Z",
            occurred_at="2026-08-21T12:00:40Z",
        )
    with pytest.raises(ReadbackSelectionError, match="unknown eligible observer frames"):
        create_readback_selection_plan(
            projection,
            BASELINE_ID,
            ["00000000-0000-4000-8000-000000000000"],
            name="Invalid",
            observed_window_end="2026-09-23T00:00:00Z",
            ledger_admission_cutoff="2026-09-23T12:00:00Z",
            occurred_at="2026-08-21T12:00:40Z",
        )
    with pytest.raises(ReadbackSelectionError, match="must follow the forecast horizon"):
        _plan_event(projection, window_end="2026-09-21T00:00:00Z")
    event = _plan_event(projection)
    projection.apply(event)
    with pytest.raises(ReadbackSelectionError, match="already has"):
        _plan_event(projection)


def test_execution_rejects_early_run_and_projection_rejects_tampered_receipt() -> None:
    projection = ReadinProjection.replay(phase8d_events()[:-1])
    with pytest.raises(ReadbackSelectionError, match="before ledger admission cutoff"):
        execute_readback_selection(projection, PLAN_ID, occurred_at="2026-09-23T11:59:59Z")

    invalid = deepcopy(phase8d_events())
    invalid[-1]["payload"]["readback_selection_run"]["execution_receipt"][
        "input_snapshot_sha256"
    ] = "0" * 64
    with pytest.raises(ProjectionError, match="receipt binding mismatch"):
        ReadinProjection.replay(invalid)


def test_residual_scoring_remains_fail_closed_after_unique_selection() -> None:
    projection = ReadinProjection.replay(phase8d_events())
    with pytest.raises(
        ResidualRuntimeError,
        match="selected a unique readback observation, but residual scoring is not enabled",
    ):
        build_residual_snapshot(
            projection,
            SCENARIO_RUN_ID,
            ["a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"],
        )
