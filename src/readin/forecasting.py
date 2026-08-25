"""Predeclared evaluation design and frozen Phase 8C forecast baseline."""

from __future__ import annotations

import inspect
import math
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import (
    create_forecast_baseline_completed,
    create_forecast_evaluation_design_created,
)
from readin.fitters import canonical_sha256

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]


class ForecastDesignError(ValueError):
    """Raised when a forecast-evaluation design would violate its temporal boundary."""


class ForecastBaselineError(ValueError):
    """Raised when a frozen reference baseline would violate its bounded contract."""


FORECAST_BASELINE_ALGORITHM_ID = "readin.reference.forecast.user-declared-constant.v0.1"
FORECAST_BASELINE_ASSUMPTIONS = [
    "The numeric value is manually declared and is not learned from observations",
    "A constant benchmark is not evidence that the target will occur",
    "The benchmark has no established calibration, empirical validity, or operational utility",
]


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


def forecast_baseline_implementation_sha256() -> str:
    """Bind receipts to the exact frozen-baseline reference implementation."""

    return canonical_sha256(
        {
            "algorithm_id": FORECAST_BASELINE_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_forecast_baseline_snapshot),
            "components_source": inspect.getsource(compute_forecast_baseline_components),
        }
    )


def build_forecast_baseline_snapshot(
    projection: ReadinProjection,
    forecast_evaluation_design_id: str,
) -> JsonObject:
    """Bind one preregistered design and scenario without selecting training inputs."""

    if forecast_evaluation_design_id not in projection.forecast_evaluation_designs:
        raise ForecastBaselineError(
            f"unknown forecast evaluation design: {forecast_evaluation_design_id}"
        )
    existing = sorted(
        baseline_id
        for baseline_id, baseline in projection.forecast_baselines.items()
        if baseline["forecast_evaluation_design_id"] == forecast_evaluation_design_id
    )
    if existing:
        raise ForecastBaselineError(
            f"forecast evaluation design already has a frozen baseline: {existing[0]}"
        )
    design = deepcopy(projection.forecast_evaluation_designs[forecast_evaluation_design_id])
    scenario = deepcopy(projection.scenarios[design["scenario_id"]])
    return {
        "asset_entity_id": design["asset_entity_id"],
        "forecast_evaluation_design": design,
        "scenario": scenario,
        "selected_input_observation_ids": [],
    }


def compute_forecast_baseline_components(
    snapshot: Mapping[str, Any], prediction_value: int | float
) -> JsonObject:
    """Return a frozen, uncalibrated constant benchmark for later scoring."""

    if isinstance(prediction_value, bool) or not isinstance(prediction_value, (int, float)):
        raise ForecastBaselineError("forecast baseline value must be numeric and non-boolean")
    if not math.isfinite(prediction_value):
        raise ForecastBaselineError("forecast baseline value must be finite")
    design = snapshot["forecast_evaluation_design"]
    target = design["target"]
    timing = design["timing"]
    return {
        "forecast_evaluation_design_id": design["id"],
        "scenario_id": design["scenario_id"],
        "method": {
            "name": "USER_DECLARED_CONSTANT",
            "method_state": "REFERENCE_BENCHMARK_NOT_VALIDATED",
            "assumptions": list(FORECAST_BASELINE_ASSUMPTIONS),
        },
        "prediction": {
            "value": prediction_value,
            "unit": target["unit"],
            "target_observation_type": target["observation_type"],
            "structured_field_path": deepcopy(target["structured_field_path"]),
            "forecast_origin": timing["forecast_origin"],
            "horizon_end": timing["horizon_end"],
            "prediction_state": "PRODUCED_UNCALIBRATED_BASELINE",
        },
        "input_boundary": {
            "training_cutoff": timing["training_cutoff"],
            "leakage_basis": "LEDGER_RECORDED_AT",
            "post_cutoff_input_policy": "EXCLUDE",
            "selected_input_observation_ids": [],
            "input_state": "NO_TRAINING_INPUTS_USED",
        },
        "forecast_method_selection_state": "SELECTED_REFERENCE_CONSTANT_BASELINE",
        "forecast_execution_state": "COMPLETED",
        "calibration_state": "NOT_ESTABLISHED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "residual_scoring_state": "NOT_ENABLED",
        "validity_update_state": "NOT_APPLIED",
        "weighting_update_state": "NOT_APPLIED",
        "future_admissibility_update_state": "NOT_APPLIED",
        "learning_state": "NOT_STARTED",
    }


def execute_frozen_forecast_baseline(
    projection: ReadinProjection,
    forecast_evaluation_design_id: str,
    prediction_value: int | float,
    *,
    baseline_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Freeze one manual constant before origin without claiming forecast validity."""

    snapshot = build_forecast_baseline_snapshot(projection, forecast_evaluation_design_id)
    components = compute_forecast_baseline_components(snapshot, prediction_value)
    event_time = _timestamp(occurred_at)
    parsed_event_time = _parse_timestamp(event_time)
    design = snapshot["forecast_evaluation_design"]
    if parsed_event_time < _parse_timestamp(design["created_at"]):
        raise ForecastBaselineError(
            "forecast baseline cannot be recorded before its evaluation design"
        )
    if parsed_event_time >= _parse_timestamp(design["timing"]["forecast_origin"]):
        raise ForecastBaselineError("forecast baseline must be recorded before forecast origin")

    selected_baseline_id = str(baseline_id or uuid4())
    selected_receipt_id = str(receipt_id or uuid4())
    asset_id = snapshot["asset_entity_id"]
    receipt = {
        "id": selected_receipt_id,
        "forecast_baseline_id": selected_baseline_id,
        "asset_entity_id": asset_id,
        "asset_state_version": projection.assets[asset_id]["epistemic_state_version"],
        "forecast_evaluation_design_id": design["id"],
        "forecast_evaluation_design_sha256": canonical_sha256(design),
        "scenario_id": snapshot["scenario"]["id"],
        "scenario_sha256": canonical_sha256(snapshot["scenario"]),
        "input_snapshot_sha256": canonical_sha256(snapshot),
        "algorithm_id": FORECAST_BASELINE_ALGORITHM_ID,
        "implementation_sha256": forecast_baseline_implementation_sha256(),
        "outcome_sha256": canonical_sha256(components),
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    baseline = {
        "id": selected_baseline_id,
        "asset_entity_id": asset_id,
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_forecast_baseline_completed(
        baseline,
        event_id=event_id,
        occurred_at=event_time,
    )


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
