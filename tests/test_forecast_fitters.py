from __future__ import annotations

from copy import deepcopy

import pytest

from readin.forecast_fitters import (
    ForecastFitterSpecificationError,
    register_forecast_fitter_specification,
)
from readin.forecast_validity import (
    ForecastValidityError,
    execute_forecast_validity_assessment,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase8e_events, phase8f_events, phase8g_events

ASSET_ID = "11111111-1111-4111-8111-111111111111"
SPECIFICATION_ID = "f3f3f3f3-f3f3-43f3-83f3-f3f3f3f3f3f3"


def _register(
    projection: ReadinProjection,
    *,
    asset_id: str = ASSET_ID,
    model_family: str = "LINEAR_REGRESSION",
    features: list[dict] | None = None,
) -> dict:
    return register_forecast_fitter_specification(
        projection,
        asset_id,
        "Prospective linear forecast candidate",
        model_family,
        "independent_record.program_activity_follow_up",
        ["activity_score"],
        "synthetic_activity_index",
        features
        if features is not None
        else [
            {
                "name": "prior_activity_score",
                "observation_type": "independent_record.program_activity_follow_up",
                "structured_field_path": ["activity_score"],
                "unit": "synthetic_activity_index",
            }
        ],
        specification_id="f6f6f6f6-f6f6-46f6-86f6-f6f6f6f6f6f6",
        event_id="f7f7f7f7-f7f7-47f7-87f7-f7f7f7f7f7f7",
        occurred_at="2026-09-23T12:00:04Z",
    )


def test_phase8g_registers_only_a_prospective_fitter_specification() -> None:
    events = phase8g_events()
    assert len(events) == 49
    projection = ReadinProjection.replay(events)
    view = projection.forecast_fitter_specification_view(SPECIFICATION_ID)
    specification = view["specification"]

    assert specification["fitter_class"] == "FORECAST"
    assert specification["model_family"] == "LINEAR_REGRESSION"
    assert specification["registration_state"] == "REGISTERED_SPECIFICATION_ONLY"
    assert specification["capability_state"] == "DECLARED_NOT_VERIFIED"
    assert specification["training_contract"]["training_data_state"] == "NOT_SELECTED"
    assert specification["training_contract"]["training_state"] == "NOT_STARTED"
    assert specification["training_contract"]["temporal_split_state"] == (
        "REQUIRED_NOT_PREDECLARED"
    )
    assert specification["training_contract"]["negative_controls_state"] == (
        "REQUIRED_NOT_PREDECLARED"
    )
    assert specification["implementation_state"] == "NOT_PROVIDED"
    assert specification["selection_state"] == "NOT_SELECTED"
    assert specification["execution_state"] == "NOT_ENABLED"
    assert specification["prediction_state"] == "NOT_PRODUCED"
    assert specification["output_contract"]["uncertainty_state"] == ("REQUIRED_NOT_IMPLEMENTED")
    assert specification["validation_corpus_state"] == "NOT_PREDECLARED"
    assert specification["calibration_state"] == "NOT_ESTABLISHED"
    assert specification["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert specification["applicability"]["retroactive_application_state"] == "PROHIBITED"
    assert specification["network_access"] is False
    assert specification["authority_state"] == "NO_AUTHORITY"
    assert view["earlier_validity_assessment_ids"] == ["f0f0f0f0-f0f0-40f0-80f0-f0f0f0f0f0f0"]
    assert view["retroactive_effect_state"] == "NONE"


def test_phase8g_fixture_and_registration_are_deterministic() -> None:
    assert phase8g_events() == phase8g_events()
    projection = ReadinProjection.replay(phase8f_events())
    features = [
        {
            "name": "z_feature",
            "observation_type": "synthetic.z",
            "structured_field_path": ["z"],
            "unit": "index",
        },
        {
            "name": "a_feature",
            "observation_type": "synthetic.a",
            "structured_field_path": ["a"],
            "unit": "index",
        },
    ]
    first = _register(projection, features=features)
    second = _register(projection, features=features)
    assert first == second
    names = [
        item["name"]
        for item in first["payload"]["forecast_fitter_specification"]["feature_contracts"]
    ]
    assert names == ["a_feature", "z_feature"]


def test_registration_rejects_unknown_asset_family_and_invalid_features() -> None:
    projection = ReadinProjection.replay(phase8f_events())
    with pytest.raises(ForecastFitterSpecificationError, match="unknown tracked asset"):
        _register(projection, asset_id="00000000-0000-4000-8000-000000000000")
    with pytest.raises(ForecastFitterSpecificationError, match="unsupported.*model family"):
        _register(projection, model_family="NEURAL_NETWORK")
    with pytest.raises(ForecastFitterSpecificationError, match="at least one numeric feature"):
        _register(projection, features=[])
    duplicate = {
        "name": "duplicate",
        "observation_type": "synthetic.feature",
        "structured_field_path": ["value"],
        "unit": "index",
    }
    with pytest.raises(ForecastFitterSpecificationError, match="names must be unique"):
        _register(projection, features=[duplicate, duplicate])


def test_projection_rejects_state_drift_and_duplicate_specification() -> None:
    events = deepcopy(phase8g_events())
    events[-1]["payload"]["forecast_fitter_specification"]["initial_state_version"] = (
        "00000000-0000-4000-8000-000000000000"
    )
    with pytest.raises(ProjectionError, match="initial state version mismatch"):
        ReadinProjection.replay(events)

    projection = ReadinProjection.replay(phase8g_events())
    duplicate = deepcopy(phase8g_events()[-1])
    duplicate["event_id"] = "f5f5f5f5-f5f5-45f5-85f5-f5f5f5f5f5f5"
    duplicate["occurred_at"] = "2026-09-23T12:00:05Z"
    duplicate["payload"]["forecast_fitter_specification"]["registered_at"] = "2026-09-23T12:00:05Z"
    with pytest.raises(ProjectionError, match="duplicate forecast fitter specification"):
        projection.apply(duplicate)


def test_later_registration_does_not_rewrite_phase8f_assessment() -> None:
    assessment_before = ReadinProjection.replay(phase8f_events()).forecast_validity_assessment_view(
        "f0f0f0f0-f0f0-40f0-80f0-f0f0f0f0f0f0"
    )
    projection = ReadinProjection.replay(phase8g_events())
    assessment_after = projection.forecast_validity_assessment_view(
        "f0f0f0f0-f0f0-40f0-80f0-f0f0f0f0f0f0"
    )

    assert assessment_after == assessment_before
    assert assessment_after["forecast_validity_assessment"]["blockers"][0] == (
        "NO_REGISTERED_FORECAST_FITTER"
    )
    assert (
        projection.forecast_fitter_specification_view(SPECIFICATION_ID)["retroactive_effect_state"]
        == "NONE"
    )


def test_phase8f_gate_rejects_execution_after_a_specification_is_registered() -> None:
    projection = ReadinProjection.replay(phase8e_events())
    specification_event = _register(projection)
    projection.apply(specification_event)

    with pytest.raises(ForecastValidityError, match="requires no registered forecast fitter"):
        execute_forecast_validity_assessment(
            projection,
            "e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0",
            occurred_at="2026-09-23T12:00:05Z",
        )
