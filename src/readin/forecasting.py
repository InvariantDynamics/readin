"""Predeclared Phase 8B forecast-evaluation design without forecast execution."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import create_forecast_evaluation_design_created

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]


class ForecastDesignError(ValueError):
    """Raised when a forecast-evaluation design would violate its temporal boundary."""


def create_forecast_evaluation_design(
    projection: ReadinProjection,
    scenario_id: str,
    name: str,
    observation_type: str,
    structured_field_path: Iterable[str],
    unit: str,
    *,
    training_cutoff: str | datetime,
    design_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Predeclare one numeric target and leakage boundary without selecting a fitter."""

    if scenario_id not in projection.scenarios:
        raise ForecastDesignError(f"unknown scenario: {scenario_id}")
    scenario = projection.scenarios[scenario_id]
    asset_id = scenario["asset_entity_id"]
    event_time = _timestamp(occurred_at)
    parsed_event_time = _parse_timestamp(event_time)
    parsed_training_cutoff = _parse_timestamp(_timestamp(training_cutoff))
    forecast_origin = _parse_timestamp(scenario["start_time"])
    horizon_end = forecast_origin + timedelta(days=scenario["horizon_days"])
    if parsed_training_cutoff > parsed_event_time:
        raise ForecastDesignError("training cutoff cannot follow design creation")
    if parsed_event_time >= forecast_origin:
        raise ForecastDesignError(
            "forecast evaluation design must be recorded before forecast origin"
        )
    path = list(structured_field_path)
    if not path or any(not isinstance(item, str) or not item.strip() for item in path):
        raise ForecastDesignError("structured field path requires non-empty string segments")

    design = {
        "id": str(design_id or uuid4()),
        "asset_entity_id": asset_id,
        "scenario_id": scenario_id,
        "name": name,
        "initial_state_version": projection.assets[asset_id]["epistemic_state_version"],
        "target": {
            "observation_type": observation_type,
            "structured_field_path": path,
            "value_kind": "NUMBER",
            "unit": unit,
            "target_semantics": "USER_DECLARED_NOT_VALIDATED",
        },
        "metric": {
            "name": "ABSOLUTE_ERROR",
            "residual_definition": "OBSERVED_MINUS_PREDICTED",
            "direction": "LOWER_IS_BETTER",
            "metric_state": "PREDECLARED_NOT_VALIDATED",
        },
        "timing": {
            "training_cutoff": _format_timestamp(parsed_training_cutoff),
            "forecast_origin": _format_timestamp(forecast_origin),
            "horizon_end": _format_timestamp(horizon_end),
            "leakage_basis": "LEDGER_RECORDED_AT",
            "post_cutoff_input_policy": "EXCLUDE",
            "readback_observation_policy": "STRICTLY_AFTER_HORIZON",
        },
        "preregistration_state": "RECORDED_BEFORE_FORECAST_ORIGIN",
        "fitter_selection_state": "NOT_SELECTED",
        "forecast_execution_state": "NOT_STARTED",
        "prediction_state": "NOT_PRODUCED",
        "calibration_state": "NOT_ESTABLISHED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "created_at": event_time,
    }
    return create_forecast_evaluation_design_created(
        design,
        event_id=event_id,
        occurred_at=event_time,
    )


def resolve_numeric_target(payload: Any, path: Iterable[str]) -> int | float:
    """Resolve the predeclared field path and require a non-boolean numeric observation."""

    current = payload
    selected_path = list(path)
    for segment in selected_path:
        if not isinstance(current, dict) or segment not in current:
            raise ForecastDesignError(
                f"observation is missing predeclared numeric target path: {selected_path}"
            )
        current = current[segment]
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        raise ForecastDesignError(f"observation target path is not numeric: {selected_path}")
    return current


def _timestamp(value: str | datetime | None = None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = _parse_timestamp(value)
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForecastDesignError("timestamps must include a UTC offset")
    return _format_timestamp(parsed)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForecastDesignError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
