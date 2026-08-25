from __future__ import annotations

from copy import deepcopy

import pytest

from readin.forecasting import (
    ForecastBaselineError,
    execute_frozen_forecast_baseline,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.residuals import ResidualRuntimeError, build_residual_snapshot
from readin.synthetic import phase8_events, phase8c_events

DESIGN_ID = "a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0"
BASELINE_ID = "c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0"
SCENARIO_RUN_ID = "89898989-8989-4989-8989-898989898981"
LATER_OBSERVATION_ID = "a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"


def test_phase8c_freezes_uncalibrated_constant_without_learning() -> None:
    events = phase8c_events()
    projection = ReadinProjection.replay(events)
    view = projection.forecast_baseline_view(BASELINE_ID)
    baseline = view["baseline"]

    assert len(events) == 44
    assert baseline["method"] == {
        "name": "USER_DECLARED_CONSTANT",
        "method_state": "REFERENCE_BENCHMARK_NOT_VALIDATED",
        "assumptions": [
            "The numeric value is manually declared and is not learned from observations",
            "A constant benchmark is not evidence that the target will occur",
            "The benchmark has no established calibration, empirical validity, "
            "or operational utility",
        ],
    }
    assert baseline["prediction"] == {
        "value": 0.75,
        "unit": "synthetic_activity_index",
        "target_observation_type": "independent_record.program_activity_follow_up",
        "structured_field_path": ["activity_score"],
        "forecast_origin": "2026-08-22T00:00:00Z",
        "horizon_end": "2026-09-21T00:00:00Z",
        "prediction_state": "PRODUCED_UNCALIBRATED_BASELINE",
    }
    assert baseline["input_boundary"]["selected_input_observation_ids"] == []
    assert baseline["input_boundary"]["input_state"] == "NO_TRAINING_INPUTS_USED"
    assert baseline["forecast_method_selection_state"] == ("SELECTED_REFERENCE_CONSTANT_BASELINE")
    assert baseline["calibration_state"] == "NOT_ESTABLISHED"
    assert baseline["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert baseline["residual_scoring_state"] == "NOT_ENABLED"
    assert baseline["validity_update_state"] == "NOT_APPLIED"
    assert baseline["weighting_update_state"] == "NOT_APPLIED"
    assert baseline["learning_state"] == "NOT_STARTED"
    assert baseline["execution_receipt"]["network_access"] is False
    assert view["authority_state"] == "NO_AUTHORITY"

    design_view = projection.forecast_evaluation_design_view(DESIGN_ID)
    assert design_view["forecast_baseline"]["id"] == BASELINE_ID
    assert design_view["forecast_capable_fitter_state"] == "NO_ELIGIBLE_FITTER_REGISTERED"
    assert design_view["eligible_fitter_ids"] == []
    assert design_view["forecast_baseline_state"] == "COMPLETED"
    assert design_view["forecast_execution_state"] == "COMPLETED"
    assert design_view["prediction_state"] == "PRODUCED_UNCALIBRATED_BASELINE"
    assert design_view["calibration_state"] == "NOT_ESTABLISHED"


def test_phase8c_fixture_is_deterministic() -> None:
    assert phase8c_events() == phase8c_events()


def test_baseline_factory_rejects_unknown_nonfinite_and_invalid_times() -> None:
    projection = ReadinProjection.replay(phase8_events()[:41])

    with pytest.raises(ForecastBaselineError, match="unknown forecast evaluation design"):
        execute_frozen_forecast_baseline(projection, "missing", 0.5)
    with pytest.raises(ForecastBaselineError, match="numeric and non-boolean"):
        execute_frozen_forecast_baseline(projection, DESIGN_ID, True)
    with pytest.raises(ForecastBaselineError, match="must be finite"):
        execute_frozen_forecast_baseline(projection, DESIGN_ID, float("inf"))
    with pytest.raises(ForecastBaselineError, match="before its evaluation design"):
        execute_frozen_forecast_baseline(
            projection,
            DESIGN_ID,
            0.5,
            occurred_at="2026-08-21T12:00:37Z",
        )
    with pytest.raises(ForecastBaselineError, match="before forecast origin"):
        execute_frozen_forecast_baseline(
            projection,
            DESIGN_ID,
            0.5,
            occurred_at="2026-08-22T00:00:00Z",
        )


def test_projection_rejects_tampered_baseline_value_or_receipt() -> None:
    events = phase8c_events()
    invalid_value = deepcopy(events[41])
    invalid_value["payload"]["forecast_baseline"]["prediction"]["value"] = 0.9
    with pytest.raises(ProjectionError, match="receipt binding mismatch"):
        ReadinProjection.replay([*events[:41], invalid_value])

    invalid_receipt = deepcopy(events[41])
    invalid_receipt["payload"]["forecast_baseline"]["execution_receipt"][
        "input_snapshot_sha256"
    ] = "0" * 64
    with pytest.raises(ProjectionError, match="receipt binding mismatch"):
        ReadinProjection.replay([*events[:41], invalid_receipt])


def test_projection_allows_only_one_baseline_per_design() -> None:
    events = phase8c_events()
    projection = ReadinProjection.replay(events[:42])
    second = deepcopy(events[41])
    second["event_id"] = "c1c1c1c1-c1c1-41c1-81c1-c1c1c1c1c1c1"
    second["payload"]["forecast_baseline"]["id"] = "c2c2c2c2-c2c2-42c2-82c2-c2c2c2c2c2c2"
    second["payload"]["forecast_baseline"]["execution_receipt"]["id"] = (
        "c3c3c3c3-c3c3-43c3-83c3-c3c3c3c3c3c3"
    )
    second["payload"]["forecast_baseline"]["execution_receipt"]["forecast_baseline_id"] = (
        "c2c2c2c2-c2c2-42c2-82c2-c2c2c2c2c2c2"
    )

    with pytest.raises(ProjectionError, match="already has a frozen baseline"):
        projection.apply(second)


def test_residual_runtime_fails_closed_when_phase8c_baseline_exists() -> None:
    projection = ReadinProjection.replay(phase8c_events())

    with pytest.raises(ResidualRuntimeError, match="residual scoring is not enabled"):
        build_residual_snapshot(
            projection,
            SCENARIO_RUN_ID,
            [LATER_OBSERVATION_ID],
        )
