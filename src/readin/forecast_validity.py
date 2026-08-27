"""Bounded Phase 8F forecast-validity update eligibility gate."""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import create_forecast_validity_update_assessed
from readin.fitters import canonical_sha256

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

FORECAST_VALIDITY_ALGORITHM_ID = "readin.reference.forecast.validity-update-gate.v0.1"
FORECAST_VALIDITY_BLOCKERS = [
    "NO_REGISTERED_FORECAST_FITTER",
    "REFERENCE_BASELINE_NOT_TRAINED_MODEL",
    "SINGLE_READBACK_ONLY",
    "UNIT_EQUIVALENCE_NOT_VERIFIED",
    "NO_PREDECLARED_VALIDATION_CORPUS",
    "UNCERTAINTY_NOT_ESTIMATED",
]


class ForecastValidityError(ValueError):
    """Raised when a validity-update assessment cannot be bound safely."""


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForecastValidityError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC)


def _timestamp(value: str | datetime | None = None) -> str:
    parsed = datetime.now(UTC) if value is None else _parse_timestamp(value)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def forecast_validity_implementation_sha256() -> str:
    """Bind receipts to the exact fail-closed validity gate."""

    return canonical_sha256(
        {
            "algorithm_id": FORECAST_VALIDITY_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_forecast_validity_snapshot),
            "components_source": inspect.getsource(compute_forecast_validity_components),
        }
    )


def build_forecast_validity_snapshot(
    projection: ReadinProjection, forecast_residual_id: str
) -> JsonObject:
    """Bind one descriptive residual to its immutable forecast inputs."""

    if forecast_residual_id not in projection.forecast_residuals:
        raise ForecastValidityError(f"unknown forecast residual: {forecast_residual_id}")
    if forecast_residual_id in projection._residual_forecast_validity_assessment:
        raise ForecastValidityError("forecast residual already has a validity assessment")
    residual = deepcopy(projection.forecast_residuals[forecast_residual_id])
    registered_specification_ids = sorted(
        specification_id
        for specification_id, specification in projection.forecast_fitter_specifications.items()
        if specification["asset_entity_id"] == residual["asset_entity_id"]
    )
    if registered_specification_ids:
        raise ForecastValidityError(
            "Phase 8F validity gate requires no registered forecast fitter specification"
        )
    return {
        "forecast_residual": residual,
        "readback_selection_run": deepcopy(
            projection.readback_selection_runs[residual["readback_selection_run_id"]]
        ),
        "forecast_baseline": deepcopy(
            projection.forecast_baselines[residual["forecast_baseline_id"]]
        ),
        "forecast_evaluation_design": deepcopy(
            projection.forecast_evaluation_designs[residual["forecast_evaluation_design_id"]]
        ),
        "scenario": deepcopy(projection.scenarios[residual["scenario_id"]]),
    }


def compute_forecast_validity_components(snapshot: Mapping[str, Any]) -> JsonObject:
    """Abstain from updates when a descriptive reference residual lacks evidence."""

    residual = snapshot["forecast_residual"]
    baseline = snapshot["forecast_baseline"]
    design = snapshot["forecast_evaluation_design"]
    supported_boundary = {
        "residual_state": "COMPUTED_DESCRIPTIVE_REFERENCE_ONLY",
        "baseline_method": "USER_DECLARED_CONSTANT",
        "fitter_selection_state": "NOT_SELECTED",
        "sample_count": 1,
        "unit_match_state": "USER_DECLARED_NOT_VERIFIED",
        "uncertainty_state": "NOT_ESTIMATED_SINGLE_READBACK",
    }
    actual_boundary = {
        "residual_state": residual["residual_state"],
        "baseline_method": baseline["method"]["name"],
        "fitter_selection_state": design["fitter_selection_state"],
        "sample_count": residual["sample_count"],
        "unit_match_state": residual["score"]["unit_match_state"],
        "uncertainty_state": residual["uncertainty_state"],
    }
    if actual_boundary != supported_boundary:
        raise ForecastValidityError(
            "forecast validity gate supports only the bounded Phase 8E reference residual"
        )
    return {
        "assessment_basis": {
            "source_kind": "PHASE_8E_DESCRIPTIVE_REFERENCE_RESIDUAL",
            "forecast_method": baseline["method"]["name"],
            "sample_count": residual["sample_count"],
            "unit_match_state": residual["score"]["unit_match_state"],
            "uncertainty_state": residual["uncertainty_state"],
            "validation_corpus_state": "NOT_PREDECLARED",
        },
        "eligibility_state": "INELIGIBLE_VALIDITY_UPDATE",
        "decision_state": "ABSTAINED",
        "blockers": list(FORECAST_VALIDITY_BLOCKERS),
        "target_fitter_id": None,
        "target_fitter_state": "NOT_AVAILABLE_NO_REGISTERED_FORECAST_FITTER",
        "residual_use_state": "DESCRIPTIVE_ONLY",
        "calibration_state": "NOT_ESTABLISHED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "validity_update_state": "NOT_APPLIED",
        "weighting_update_state": "NOT_APPLIED",
        "future_admissibility_update_state": "NOT_APPLIED",
        "learning_state": "NOT_STARTED",
        "interpretation": "ABSTENTION_NOT_MODEL_INVALIDITY_OR_VALIDATION",
        "authority_state": "NO_AUTHORITY",
    }


def execute_forecast_validity_assessment(
    projection: ReadinProjection,
    forecast_residual_id: str,
    *,
    assessment_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Record why one descriptive residual cannot change model validity."""

    snapshot = build_forecast_validity_snapshot(projection, forecast_residual_id)
    components = compute_forecast_validity_components(snapshot)
    event_time = _timestamp(occurred_at)
    residual = snapshot["forecast_residual"]
    if _parse_timestamp(event_time) < _parse_timestamp(residual["recorded_at"]):
        raise ForecastValidityError("forecast validity assessment cannot precede its residual")
    selected_assessment_id = str(assessment_id or uuid4())
    selected_receipt_id = str(receipt_id or uuid4())
    asset_id = residual["asset_entity_id"]
    receipt = {
        "id": selected_receipt_id,
        "forecast_validity_assessment_id": selected_assessment_id,
        "forecast_residual_id": forecast_residual_id,
        "asset_entity_id": asset_id,
        "asset_state_version": projection.assets[asset_id]["epistemic_state_version"],
        "readback_selection_run_id": residual["readback_selection_run_id"],
        "forecast_baseline_id": residual["forecast_baseline_id"],
        "forecast_evaluation_design_id": residual["forecast_evaluation_design_id"],
        "scenario_id": residual["scenario_id"],
        "forecast_residual_sha256": canonical_sha256(residual),
        "readback_selection_run_sha256": canonical_sha256(snapshot["readback_selection_run"]),
        "forecast_baseline_sha256": canonical_sha256(snapshot["forecast_baseline"]),
        "forecast_evaluation_design_sha256": canonical_sha256(
            snapshot["forecast_evaluation_design"]
        ),
        "scenario_sha256": canonical_sha256(snapshot["scenario"]),
        "input_snapshot_sha256": canonical_sha256(snapshot),
        "algorithm_id": FORECAST_VALIDITY_ALGORITHM_ID,
        "implementation_sha256": forecast_validity_implementation_sha256(),
        "outcome_sha256": canonical_sha256(components),
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    assessment = {
        "id": selected_assessment_id,
        "asset_entity_id": asset_id,
        "forecast_residual_id": forecast_residual_id,
        "readback_selection_run_id": residual["readback_selection_run_id"],
        "forecast_baseline_id": residual["forecast_baseline_id"],
        "forecast_evaluation_design_id": residual["forecast_evaluation_design_id"],
        "scenario_id": residual["scenario_id"],
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_forecast_validity_update_assessed(
        assessment, event_id=event_id, occurred_at=event_time
    )
