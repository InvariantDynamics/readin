from __future__ import annotations

from copy import deepcopy

import pytest

from readin.forecast_residuals import ForecastResidualError, execute_forecast_residual
from readin.projection import ProjectionError, ReadinProjection
from readin.readback_selection import (
    create_readback_selection_plan,
    execute_readback_selection,
)
from readin.synthetic import phase8c_events, phase8d_events, phase8e_events

PLAN_ID = "d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0"
RUN_ID = "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d0"
RESIDUAL_ID = "e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0"
BASELINE_ID = "c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0"
FRAME_ID = "91919191-9191-4191-8191-919191919191"


def test_phase8e_computes_one_descriptive_reference_residual() -> None:
    events = phase8e_events()
    assert len(events) == 47
    projection = ReadinProjection.replay(events)
    view = projection.forecast_residual_view(RESIDUAL_ID)
    residual = view["forecast_residual"]

    assert residual["selection_eligibility_state"] == "UNIQUE_MATCH_CONFIRMED"
    assert residual["baseline_state"] == "USER_DECLARED_CONSTANT_UNCALIBRATED"
    assert residual["sample_count"] == 1
    assert residual["metric"] == {
        "name": "ABSOLUTE_ERROR",
        "direction": "LOWER_IS_BETTER",
        "residual_definition": "OBSERVED_MINUS_PREDICTED",
        "metric_state": "COMPUTED_REFERENCE_BASELINE_NOT_VALIDATED",
    }
    assert residual["score"] == {
        "prediction_value": 0.75,
        "observed_value": 1.0,
        "signed_residual": 0.25,
        "absolute_error": 0.25,
        "unit": "synthetic_activity_index",
        "unit_match_state": "USER_DECLARED_NOT_VERIFIED",
    }
    assert residual["residual_state"] == "COMPUTED_DESCRIPTIVE_REFERENCE_ONLY"
    assert residual["residual_scoring_state"] == ("COMPLETED_REFERENCE_BASELINE_ONLY")
    assert residual["uncertainty_state"] == "NOT_ESTIMATED_SINGLE_READBACK"
    assert residual["calibration_state"] == "NOT_ESTABLISHED"
    assert residual["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert residual["validity_update_state"] == "NOT_APPLIED"
    assert residual["weighting_update_state"] == "NOT_APPLIED"
    assert residual["future_admissibility_update_state"] == "NOT_APPLIED"
    assert residual["learning_state"] == "NOT_STARTED"
    assert residual["interpretation"] == ("DESCRIPTIVE_ERROR_NOT_FORECAST_VALIDATION")
    assert residual["authority_state"] == "NO_AUTHORITY"
    assert residual["execution_receipt"]["network_access"] is False
    assert view["selected_observation"]["id"] == residual["selected_observation_id"]
    assert view["selected_observer_frame"]["id"] == FRAME_ID
    assert view["calibration_state"] == "NOT_ESTABLISHED"
    assert view["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert view["authority_state"] == "NO_AUTHORITY"


def test_phase8e_fixture_and_execution_are_deterministic() -> None:
    assert phase8e_events() == phase8e_events()
    projection = ReadinProjection.replay(phase8d_events())
    first = execute_forecast_residual(
        projection,
        RUN_ID,
        forecast_residual_id=RESIDUAL_ID,
        receipt_id="e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e1",
        event_id="e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e2",
        occurred_at="2026-09-23T12:00:02Z",
    )
    second = execute_forecast_residual(
        projection,
        RUN_ID,
        forecast_residual_id=RESIDUAL_ID,
        receipt_id="e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e1",
        event_id="e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e2",
        occurred_at="2026-09-23T12:00:02Z",
    )
    assert first == second


def test_forecast_residual_rejects_unknown_early_and_duplicate_execution() -> None:
    projection = ReadinProjection.replay(phase8d_events())
    with pytest.raises(ForecastResidualError, match="unknown readback selection run"):
        execute_forecast_residual(
            projection,
            "00000000-0000-4000-8000-000000000000",
        )
    with pytest.raises(ForecastResidualError, match="cannot precede readback selection"):
        execute_forecast_residual(
            projection,
            RUN_ID,
            occurred_at="2026-09-23T12:00:00Z",
        )

    projection = ReadinProjection.replay(phase8e_events())
    with pytest.raises(ForecastResidualError, match="already has a forecast residual"):
        execute_forecast_residual(projection, RUN_ID)


def test_forecast_residual_rejects_abstained_selection() -> None:
    phase8c = phase8c_events()
    events = list(phase8c[:42])
    projection = ReadinProjection.replay(events)
    events.append(
        create_readback_selection_plan(
            projection,
            BASELINE_ID,
            [FRAME_ID],
            name="No-match readback aperture",
            observed_window_end="2026-09-21T12:00:00Z",
            ledger_admission_cutoff="2026-09-23T12:00:00Z",
            plan_id=PLAN_ID,
            event_id="d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d1",
            occurred_at="2026-08-21T12:00:40Z",
        )
    )
    events.extend(phase8c[42:44])
    projection = ReadinProjection.replay(events)
    events.append(
        execute_readback_selection(
            projection,
            PLAN_ID,
            run_id=RUN_ID,
            receipt_id="d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d1",
            event_id="d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d2",
            occurred_at="2026-09-23T12:00:01Z",
        )
    )
    projection = ReadinProjection.replay(events)
    with pytest.raises(
        ForecastResidualError,
        match="requires UNIQUE_MATCH_SELECTED, got ABSTAINED_NO_MATCH",
    ):
        execute_forecast_residual(projection, RUN_ID)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda event: event["payload"]["forecast_residual"]["execution_receipt"].__setitem__(
                "input_snapshot_sha256", "0" * 64
            ),
            "receipt binding mismatch",
        ),
        (
            lambda event: event["payload"]["forecast_residual"]["score"].__setitem__(
                "absolute_error", 0.5
            ),
            "does not match reference arithmetic",
        ),
    ],
)
def test_projection_rejects_tampered_forecast_residual(mutate: object, message: str) -> None:
    events = deepcopy(phase8e_events())
    mutate(events[-1])  # type: ignore[operator]
    with pytest.raises(ProjectionError, match=message):
        ReadinProjection.replay(events)


def test_projection_rejects_second_residual_for_same_selection() -> None:
    events = phase8e_events()
    projection = ReadinProjection.replay(events)
    duplicate = deepcopy(events[-1])
    result = duplicate["payload"]["forecast_residual"]
    duplicate["event_id"] = "e5e5e5e5-e5e5-45e5-85e5-e5e5e5e5e5e2"
    result["id"] = "e5e5e5e5-e5e5-45e5-85e5-e5e5e5e5e5e0"
    result["execution_receipt"]["id"] = "e5e5e5e5-e5e5-45e5-85e5-e5e5e5e5e5e1"
    result["execution_receipt"]["forecast_residual_id"] = result["id"]
    with pytest.raises(ProjectionError, match="already has a forecast residual"):
        projection.apply(duplicate)
