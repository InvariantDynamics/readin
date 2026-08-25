from __future__ import annotations

from copy import deepcopy

import pytest

from readin.events import create_tracking_started
from readin.projection import ProjectionError, ReadinProjection
from readin.residuals import (
    ResidualRuntimeError,
    build_residual_snapshot,
    execute_residual_readback,
)
from readin.synthetic import phase7_events, phase8_events

SCENARIO_RUN_ID = "89898989-8989-4989-8989-898989898981"
LATER_OBSERVATION_ID = "a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"
READBACK_ID = "b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1"


def test_phase8_readback_retains_later_observation_and_abstains() -> None:
    events = phase8_events()
    projection = ReadinProjection.replay(events)
    view = projection.residual_readback_view(READBACK_ID)
    readback = view["readback"]

    assert len(events) == 44
    assert readback["observation_ids"] == [LATER_OBSERVATION_ID]
    assert readback["temporal_order_state"] == "LATER_THAN_SCENARIO_HORIZON_CONFIRMED"
    assert readback["baseline_eligibility_state"] == "INELIGIBLE_NO_FORECAST_BASELINE"
    assert readback["reference_prediction_state"] == "NOT_REQUESTED"
    assert readback["residual_state"] == "NOT_COMPUTED"
    assert readback["residual_value"] is None
    assert readback["validity_update_state"] == "NOT_APPLIED"
    assert readback["weighting_update_state"] == "NOT_APPLIED"
    assert readback["future_admissibility_update_state"] == "NOT_APPLIED"
    assert readback["learning_state"] == "NOT_STARTED"
    assert readback["execution_receipt"]["network_access"] is False
    assert readback["execution_receipt"]["forecast_evaluation_design_id"] == (
        "a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0"
    )
    assert view["forecast_baseline_state"] == "NOT_AVAILABLE"
    assert view["authority_state"] == "NO_AUTHORITY"
    assert view["observations"][0]["observed_at"] > "2026-09-21T00:00:00Z"


def test_phase8_fixture_is_deterministic() -> None:
    assert phase8_events() == phase8_events()


def test_residual_snapshot_rejects_unknown_empty_duplicate_and_non_later_inputs() -> None:
    projection = ReadinProjection.replay(phase7_events())

    with pytest.raises(ResidualRuntimeError, match="unknown scenario run"):
        build_residual_snapshot(projection, "missing", [LATER_OBSERVATION_ID])
    with pytest.raises(ResidualRuntimeError, match="at least one"):
        build_residual_snapshot(projection, SCENARIO_RUN_ID, [])
    with pytest.raises(ResidualRuntimeError, match="must be unique"):
        build_residual_snapshot(
            projection,
            SCENARIO_RUN_ID,
            ["44444444-4444-4444-8444-444444444444"] * 2,
        )
    with pytest.raises(ResidualRuntimeError, match="later than the scenario horizon"):
        build_residual_snapshot(
            projection,
            SCENARIO_RUN_ID,
            ["44444444-4444-4444-8444-444444444444"],
        )


def test_projection_rejects_tampered_residual_receipt() -> None:
    events = phase8_events()
    invalid = deepcopy(events[43])
    invalid["payload"]["residual_readback"]["execution_receipt"]["observation_snapshot_sha256"] = (
        "0" * 64
    )

    with pytest.raises(ProjectionError, match="residual receipt binding mismatch"):
        ReadinProjection.replay([*events[:43], invalid])


def test_projection_rejects_readback_observation_from_another_entity() -> None:
    events = phase8_events()
    track_other_entity = create_tracking_started(
        "55555555-5555-4555-8555-555555555555",
        event_id="c2c2c2c2-c2c2-42c2-82c2-c2c2c2c2c2c2",
        occurred_at="2026-09-22T11:59:59Z",
    )
    wrong_observation = deepcopy(events[42])
    wrong_observation["payload"]["observation"]["subject_entities"] = [
        "55555555-5555-4555-8555-555555555555"
    ]
    invalid_readback = deepcopy(events[43])
    invalid_readback["payload"]["residual_readback"]["execution_receipt"]["asset_state_version"] = (
        "a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a2"
    )

    with pytest.raises(ProjectionError, match="do not concern the scenario asset"):
        ReadinProjection.replay(
            [
                *events[:41],
                track_other_entity,
                events[41],
                wrong_observation,
                invalid_readback,
            ]
        )


def test_projection_rejects_second_readback_for_same_scenario_run() -> None:
    events = phase8_events()
    projection = ReadinProjection.replay(events)
    second = execute_residual_readback(
        projection,
        SCENARIO_RUN_ID,
        [LATER_OBSERVATION_ID],
        readback_id="b4b4b4b4-b4b4-44b4-84b4-b4b4b4b4b4b4",
        receipt_id="b5b5b5b5-b5b5-45b5-85b5-b5b5b5b5b5b5",
        event_id="b6b6b6b6-b6b6-46b6-86b6-b6b6b6b6b6b6",
        occurred_at="2026-09-22T12:00:03Z",
    )

    with pytest.raises(ProjectionError, match="already has a residual readback"):
        projection.apply(second)
