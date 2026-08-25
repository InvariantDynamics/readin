from __future__ import annotations

from copy import deepcopy

import pytest

from readin.forecasting import ForecastDesignError, create_forecast_evaluation_design
from readin.projection import ProjectionError, ReadinProjection
from readin.residuals import ResidualRuntimeError, build_residual_snapshot
from readin.synthetic import phase7_events, phase8_events

SCENARIO_ID = "85858585-8585-4585-8585-858585858585"
SCENARIO_RUN_ID = "89898989-8989-4989-8989-898989898981"
DESIGN_ID = "a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0"
OBSERVATION_ID = "a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"


def test_phase8_forecast_design_predeclares_target_without_prediction() -> None:
    projection = ReadinProjection.replay(phase8_events())
    view = projection.forecast_evaluation_design_view(DESIGN_ID)
    design = view["design"]

    assert design["target"] == {
        "observation_type": "independent_record.program_activity_follow_up",
        "structured_field_path": ["activity_score"],
        "value_kind": "NUMBER",
        "unit": "synthetic_activity_index",
        "target_semantics": "USER_DECLARED_NOT_VALIDATED",
    }
    assert design["metric"]["name"] == "ABSOLUTE_ERROR"
    assert design["metric"]["residual_definition"] == "OBSERVED_MINUS_PREDICTED"
    assert design["timing"]["training_cutoff"] == "2026-08-21T12:00:37Z"
    assert design["timing"]["forecast_origin"] == "2026-08-22T00:00:00Z"
    assert design["timing"]["horizon_end"] == "2026-09-21T00:00:00Z"
    assert design["preregistration_state"] == "RECORDED_BEFORE_FORECAST_ORIGIN"
    assert view["forecast_capable_fitter_state"] == "NO_ELIGIBLE_FITTER_REGISTERED"
    assert view["eligible_fitter_ids"] == []
    assert view["forecast_execution_state"] == "NOT_STARTED"
    assert view["prediction_state"] == "NOT_PRODUCED"
    assert view["calibration_state"] == "NOT_ESTABLISHED"
    assert view["authority_state"] == "NO_AUTHORITY"


def test_forecast_design_factory_rejects_unknown_or_temporally_invalid_designs() -> None:
    projection = ReadinProjection.replay(phase7_events())
    common = {
        "name": "Bounded evaluation design",
        "observation_type": "synthetic.outcome",
        "structured_field_path": ["value"],
        "unit": "synthetic_unit",
        "training_cutoff": "2026-08-21T12:00:37Z",
    }

    with pytest.raises(ForecastDesignError, match="unknown scenario"):
        create_forecast_evaluation_design(projection, "missing", **common)
    with pytest.raises(ForecastDesignError, match="before forecast origin"):
        create_forecast_evaluation_design(
            projection,
            SCENARIO_ID,
            **common,
            occurred_at="2026-08-22T00:00:00Z",
        )
    with pytest.raises(ForecastDesignError, match="cutoff cannot follow"):
        create_forecast_evaluation_design(
            projection,
            SCENARIO_ID,
            **{**common, "training_cutoff": "2026-08-21T12:00:39Z"},
            occurred_at="2026-08-21T12:00:38Z",
        )
    with pytest.raises(ForecastDesignError, match="non-empty string segments"):
        create_forecast_evaluation_design(
            projection,
            SCENARIO_ID,
            **{**common, "structured_field_path": []},
            occurred_at="2026-08-21T12:00:38Z",
        )


def test_projection_rejects_forecast_design_state_and_timing_drift() -> None:
    events = phase8_events()
    invalid_state = deepcopy(events[40])
    invalid_state["payload"]["forecast_evaluation_design"]["initial_state_version"] = (
        "00000000-0000-4000-8000-000000000000"
    )
    with pytest.raises(ProjectionError, match="initial state version mismatch"):
        ReadinProjection.replay([*events[:40], invalid_state])

    invalid_timing = deepcopy(events[40])
    invalid_timing["payload"]["forecast_evaluation_design"]["timing"]["horizon_end"] = (
        "2026-09-22T00:00:00Z"
    )
    with pytest.raises(ProjectionError, match="timing mismatch"):
        ReadinProjection.replay([*events[:40], invalid_timing])


def test_projection_allows_only_one_forecast_design_per_scenario() -> None:
    events = phase8_events()
    projection = ReadinProjection.replay(events[:41])
    second = create_forecast_evaluation_design(
        projection,
        SCENARIO_ID,
        "Second design",
        "synthetic.outcome",
        ["value"],
        "synthetic_unit",
        training_cutoff="2026-08-21T12:00:37Z",
        design_id="c3c3c3c3-c3c3-43c3-83c3-c3c3c3c3c3c3",
        event_id="c4c4c4c4-c4c4-44c4-84c4-c4c4c4c4c4c4",
        occurred_at="2026-08-21T12:00:39Z",
    )

    with pytest.raises(ProjectionError, match="already has a forecast evaluation design"):
        projection.apply(second)


def test_residual_snapshot_requires_predeclared_matching_numeric_target() -> None:
    events = phase8_events()
    without_design = ReadinProjection.replay([*events[:40], events[41], events[42]])
    with pytest.raises(ResidualRuntimeError, match="no predeclared forecast evaluation design"):
        build_residual_snapshot(without_design, SCENARIO_RUN_ID, [OBSERVATION_ID])

    mismatched_design = deepcopy(events[40])
    mismatched_design["payload"]["forecast_evaluation_design"]["target"]["observation_type"] = (
        "synthetic.other_outcome"
    )
    mismatched = ReadinProjection.replay([*events[:40], mismatched_design, events[41], events[42]])
    with pytest.raises(ResidualRuntimeError, match="do not match the predeclared target type"):
        build_residual_snapshot(mismatched, SCENARIO_RUN_ID, [OBSERVATION_ID])

    nonnumeric_observation = deepcopy(events[42])
    nonnumeric_observation["payload"]["observation"]["content"]["structured_payload"][
        "activity_score"
    ] = "one"
    nonnumeric = ReadinProjection.replay([*events[:42], nonnumeric_observation])
    with pytest.raises(ResidualRuntimeError, match="target path is not numeric"):
        build_residual_snapshot(nonnumeric, SCENARIO_RUN_ID, [OBSERVATION_ID])


def test_projection_rejects_tampered_forecast_design_binding_in_readback() -> None:
    events = phase8_events()
    invalid = deepcopy(events[43])
    invalid["payload"]["residual_readback"]["execution_receipt"][
        "forecast_evaluation_design_sha256"
    ] = "0" * 64

    with pytest.raises(ProjectionError, match="residual receipt binding mismatch"):
        ReadinProjection.replay([*events[:43], invalid])
