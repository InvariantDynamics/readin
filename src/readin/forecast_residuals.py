"""Bounded Phase 8E descriptive residual arithmetic for a frozen reference baseline."""

from __future__ import annotations

import inspect
import math
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import create_forecast_residual_computed
from readin.fitters import canonical_sha256
from readin.forecasting import ForecastDesignError, resolve_numeric_target

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

FORECAST_RESIDUAL_ALGORITHM_ID = "readin.reference.forecast.descriptive-residual.v0.1"


class ForecastResidualError(ValueError):
    """Raised when descriptive residual arithmetic cannot be bound safely."""


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForecastResidualError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC)


def _timestamp(value: str | datetime | None = None) -> str:
    parsed = datetime.now(UTC) if value is None else _parse_timestamp(value)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def forecast_residual_implementation_sha256() -> str:
    """Bind receipts to the exact descriptive reference arithmetic."""

    return canonical_sha256(
        {
            "algorithm_id": FORECAST_RESIDUAL_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_forecast_residual_snapshot),
            "components_source": inspect.getsource(compute_forecast_residual_components),
        }
    )


def build_forecast_residual_snapshot(
    projection: ReadinProjection, readback_selection_run_id: str
) -> JsonObject:
    """Bind one unique selection to its immutable forecast and observation inputs."""

    if readback_selection_run_id not in projection.readback_selection_runs:
        raise ForecastResidualError(f"unknown readback selection run: {readback_selection_run_id}")
    if readback_selection_run_id in projection._selection_run_forecast_residual:
        raise ForecastResidualError("readback selection run already has a forecast residual")
    selection_run = deepcopy(projection.readback_selection_runs[readback_selection_run_id])
    if selection_run["selection_state"] != "UNIQUE_MATCH_SELECTED":
        raise ForecastResidualError(
            "forecast residual requires UNIQUE_MATCH_SELECTED, got "
            f"{selection_run['selection_state']}"
        )
    observation_id = selection_run["selected_observation_id"]
    selected_value = selection_run["selected_target_value"]
    if observation_id is None or selected_value is None:
        raise ForecastResidualError("unique selection is missing its observation or target value")

    plan = deepcopy(
        projection.readback_selection_plans[selection_run["readback_selection_plan_id"]]
    )
    baseline = deepcopy(projection.forecast_baselines[selection_run["forecast_baseline_id"]])
    design = deepcopy(
        projection.forecast_evaluation_designs[selection_run["forecast_evaluation_design_id"]]
    )
    scenario = deepcopy(projection.scenarios[selection_run["scenario_id"]])
    observation = deepcopy(projection.observations[observation_id])
    observer_frame = deepcopy(projection.frames[observation["observer_frame_id"]])
    evidence_manifest = deepcopy(projection.evidence[observation["source_artifact_id"]])
    try:
        resolved_value = resolve_numeric_target(
            observation["content"]["structured_payload"],
            plan["target"]["structured_field_path"],
        )
    except ForecastDesignError as error:
        raise ForecastResidualError(str(error)) from error
    if not math.isfinite(resolved_value):
        raise ForecastResidualError("selected observation target value must be finite")
    if resolved_value != selected_value:
        raise ForecastResidualError("selected observation target value binding mismatch")

    return {
        "selection_run": selection_run,
        "selection_plan": plan,
        "forecast_baseline": baseline,
        "forecast_evaluation_design": design,
        "scenario": scenario,
        "selected_observation": observation,
        "selected_observer_frame": observer_frame,
        "selected_evidence_manifest": evidence_manifest,
    }


def compute_forecast_residual_components(snapshot: Mapping[str, Any]) -> JsonObject:
    """Compute descriptive error without promoting one result to forecast validity."""

    baseline = snapshot["forecast_baseline"]
    design = snapshot["forecast_evaluation_design"]
    selection_run = snapshot["selection_run"]
    prediction_value = baseline["prediction"]["value"]
    observed_value = selection_run["selected_target_value"]
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in (prediction_value, observed_value)
    ):
        raise ForecastResidualError("forecast residual inputs must be finite numeric values")
    signed_residual = observed_value - prediction_value
    absolute_error = abs(signed_residual)
    if not math.isfinite(signed_residual) or not math.isfinite(absolute_error):
        raise ForecastResidualError("forecast residual outcome must be finite")
    return {
        "selection_eligibility_state": "UNIQUE_MATCH_CONFIRMED",
        "baseline_state": "USER_DECLARED_CONSTANT_UNCALIBRATED",
        "sample_count": 1,
        "metric": {
            "name": design["metric"]["name"],
            "direction": design["metric"]["direction"],
            "residual_definition": design["metric"]["residual_definition"],
            "metric_state": "COMPUTED_REFERENCE_BASELINE_NOT_VALIDATED",
        },
        "score": {
            "prediction_value": prediction_value,
            "observed_value": observed_value,
            "signed_residual": signed_residual,
            "absolute_error": absolute_error,
            "unit": design["target"]["unit"],
            "unit_match_state": "USER_DECLARED_NOT_VERIFIED",
        },
        "residual_state": "COMPUTED_DESCRIPTIVE_REFERENCE_ONLY",
        "residual_scoring_state": "COMPLETED_REFERENCE_BASELINE_ONLY",
        "uncertainty_state": "NOT_ESTIMATED_SINGLE_READBACK",
        "calibration_state": "NOT_ESTABLISHED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "validity_update_state": "NOT_APPLIED",
        "weighting_update_state": "NOT_APPLIED",
        "future_admissibility_update_state": "NOT_APPLIED",
        "learning_state": "NOT_STARTED",
        "interpretation": "DESCRIPTIVE_ERROR_NOT_FORECAST_VALIDATION",
        "authority_state": "NO_AUTHORITY",
    }


def execute_forecast_residual(
    projection: ReadinProjection,
    readback_selection_run_id: str,
    *,
    forecast_residual_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Record replay-verifiable descriptive residual arithmetic for one unique readback."""

    snapshot = build_forecast_residual_snapshot(projection, readback_selection_run_id)
    components = compute_forecast_residual_components(snapshot)
    event_time = _timestamp(occurred_at)
    if _parse_timestamp(event_time) < _parse_timestamp(snapshot["selection_run"]["recorded_at"]):
        raise ForecastResidualError("forecast residual cannot precede readback selection")
    selected_residual_id = str(forecast_residual_id or uuid4())
    selected_receipt_id = str(receipt_id or uuid4())
    selection_run = snapshot["selection_run"]
    asset_id = selection_run["asset_entity_id"]
    observation = snapshot["selected_observation"]
    receipt = {
        "id": selected_receipt_id,
        "forecast_residual_id": selected_residual_id,
        "readback_selection_run_id": readback_selection_run_id,
        "readback_selection_plan_id": selection_run["readback_selection_plan_id"],
        "asset_entity_id": asset_id,
        "asset_state_version": projection.assets[asset_id]["epistemic_state_version"],
        "forecast_baseline_id": selection_run["forecast_baseline_id"],
        "forecast_evaluation_design_id": selection_run["forecast_evaluation_design_id"],
        "scenario_id": selection_run["scenario_id"],
        "selected_observation_id": observation["id"],
        "selected_evidence_manifest_id": observation["source_artifact_id"],
        "selected_observer_frame_id": observation["observer_frame_id"],
        "readback_selection_run_sha256": canonical_sha256(selection_run),
        "readback_selection_plan_sha256": canonical_sha256(snapshot["selection_plan"]),
        "forecast_baseline_sha256": canonical_sha256(snapshot["forecast_baseline"]),
        "forecast_evaluation_design_sha256": canonical_sha256(
            snapshot["forecast_evaluation_design"]
        ),
        "scenario_sha256": canonical_sha256(snapshot["scenario"]),
        "selected_observation_sha256": canonical_sha256(observation),
        "selected_evidence_manifest_sha256": canonical_sha256(
            snapshot["selected_evidence_manifest"]
        ),
        "selected_observer_frame_sha256": canonical_sha256(snapshot["selected_observer_frame"]),
        "input_snapshot_sha256": canonical_sha256(snapshot),
        "algorithm_id": FORECAST_RESIDUAL_ALGORITHM_ID,
        "implementation_sha256": forecast_residual_implementation_sha256(),
        "outcome_sha256": canonical_sha256(components),
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    result = {
        "id": selected_residual_id,
        "asset_entity_id": asset_id,
        "readback_selection_run_id": readback_selection_run_id,
        "readback_selection_plan_id": selection_run["readback_selection_plan_id"],
        "forecast_baseline_id": selection_run["forecast_baseline_id"],
        "forecast_evaluation_design_id": selection_run["forecast_evaluation_design_id"],
        "scenario_id": selection_run["scenario_id"],
        "selected_observation_id": observation["id"],
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_forecast_residual_computed(result, event_id=event_id, occurred_at=event_time)
