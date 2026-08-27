from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy

import pytest

from readin.forecast_validity import (
    FORECAST_VALIDITY_BLOCKERS,
    ForecastValidityError,
    execute_forecast_validity_assessment,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase8e_events, phase8f_events

RESIDUAL_ID = "e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0"
ASSESSMENT_ID = "f0f0f0f0-f0f0-40f0-80f0-f0f0f0f0f0f0"


def test_phase8f_abstains_from_unsupported_validity_update() -> None:
    events = phase8f_events()
    assert len(events) == 48
    projection = ReadinProjection.replay(events)
    view = projection.forecast_validity_assessment_view(ASSESSMENT_ID)
    assessment = view["forecast_validity_assessment"]

    assert assessment["assessment_basis"] == {
        "source_kind": "PHASE_8E_DESCRIPTIVE_REFERENCE_RESIDUAL",
        "forecast_method": "USER_DECLARED_CONSTANT",
        "sample_count": 1,
        "unit_match_state": "USER_DECLARED_NOT_VERIFIED",
        "uncertainty_state": "NOT_ESTIMATED_SINGLE_READBACK",
        "validation_corpus_state": "NOT_PREDECLARED",
    }
    assert assessment["eligibility_state"] == "INELIGIBLE_VALIDITY_UPDATE"
    assert assessment["decision_state"] == "ABSTAINED"
    assert assessment["blockers"] == FORECAST_VALIDITY_BLOCKERS
    assert assessment["target_fitter_id"] is None
    assert assessment["target_fitter_state"] == ("NOT_AVAILABLE_NO_REGISTERED_FORECAST_FITTER")
    assert assessment["residual_use_state"] == "DESCRIPTIVE_ONLY"
    assert assessment["calibration_state"] == "NOT_ESTABLISHED"
    assert assessment["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert assessment["validity_update_state"] == "NOT_APPLIED"
    assert assessment["weighting_update_state"] == "NOT_APPLIED"
    assert assessment["future_admissibility_update_state"] == "NOT_APPLIED"
    assert assessment["learning_state"] == "NOT_STARTED"
    assert assessment["interpretation"] == ("ABSTENTION_NOT_MODEL_INVALIDITY_OR_VALIDATION")
    assert assessment["execution_receipt"]["network_access"] is False
    assert assessment["authority_state"] == "NO_AUTHORITY"
    assert view["forecast_residual"]["id"] == RESIDUAL_ID
    assert view["validity_update_state"] == "NOT_APPLIED"
    assert view["learning_state"] == "NOT_STARTED"
    assert view["authority_state"] == "NO_AUTHORITY"


def test_phase8f_fixture_and_execution_are_deterministic() -> None:
    assert phase8f_events() == phase8f_events()
    projection = ReadinProjection.replay(phase8e_events())
    first = execute_forecast_validity_assessment(
        projection,
        RESIDUAL_ID,
        assessment_id=ASSESSMENT_ID,
        receipt_id="f1f1f1f1-f1f1-41f1-81f1-f1f1f1f1f1f1",
        event_id="f2f2f2f2-f2f2-42f2-82f2-f2f2f2f2f2f2",
        occurred_at="2026-09-23T12:00:03Z",
    )
    second = execute_forecast_validity_assessment(
        projection,
        RESIDUAL_ID,
        assessment_id=ASSESSMENT_ID,
        receipt_id="f1f1f1f1-f1f1-41f1-81f1-f1f1f1f1f1f1",
        event_id="f2f2f2f2-f2f2-42f2-82f2-f2f2f2f2f2f2",
        occurred_at="2026-09-23T12:00:03Z",
    )
    assert first == second


def test_validity_assessment_rejects_unknown_early_and_duplicate_execution() -> None:
    projection = ReadinProjection.replay(phase8e_events())
    with pytest.raises(ForecastValidityError, match="unknown forecast residual"):
        execute_forecast_validity_assessment(projection, "00000000-0000-4000-8000-000000000000")
    with pytest.raises(ForecastValidityError, match="cannot precede its residual"):
        execute_forecast_validity_assessment(
            projection,
            RESIDUAL_ID,
            occurred_at="2026-09-23T12:00:01Z",
        )

    projection = ReadinProjection.replay(phase8f_events())
    with pytest.raises(ForecastValidityError, match="already has a validity assessment"):
        execute_forecast_validity_assessment(projection, RESIDUAL_ID)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda event: event["payload"]["forecast_validity_assessment"][
                "execution_receipt"
            ].__setitem__("input_snapshot_sha256", "0" * 64),
            "receipt binding mismatch",
        ),
        (
            lambda event: event["payload"]["forecast_validity_assessment"].__setitem__(
                "scenario_id", "00000000-0000-4000-8000-000000000000"
            ),
            "identity mismatch",
        ),
    ],
)
def test_projection_rejects_tampered_validity_assessment(
    mutate: Callable[[dict], None], message: str
) -> None:
    events = deepcopy(phase8f_events())
    mutate(events[-1])
    with pytest.raises(ProjectionError, match=message):
        ReadinProjection.replay(events)


def test_projection_rejects_second_assessment_for_same_residual() -> None:
    events = phase8f_events()
    projection = ReadinProjection.replay(events)
    duplicate = deepcopy(events[-1])
    assessment = duplicate["payload"]["forecast_validity_assessment"]
    duplicate["event_id"] = "f5f5f5f5-f5f5-45f5-85f5-f5f5f5f5f5f2"
    assessment["id"] = "f5f5f5f5-f5f5-45f5-85f5-f5f5f5f5f5f0"
    assessment["execution_receipt"]["id"] = "f5f5f5f5-f5f5-45f5-85f5-f5f5f5f5f5f1"
    assessment["execution_receipt"]["forecast_validity_assessment_id"] = assessment["id"]
    with pytest.raises(ProjectionError, match="already has a validity assessment"):
        projection.apply(duplicate)
