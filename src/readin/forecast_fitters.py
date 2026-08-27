"""Bounded Phase 8G prospective forecast-fitter specification registration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import create_forecast_fitter_specification_registered

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

FORECAST_FITTER_MODEL_FAMILIES = frozenset({"LINEAR_REGRESSION"})


class ForecastFitterSpecificationError(ValueError):
    """Raised when a prospective fitter specification is not safely bounded."""


def register_forecast_fitter_specification(
    projection: ReadinProjection,
    asset_entity_id: str,
    name: str,
    model_family: str,
    target_observation_type: str,
    target_field_path: Iterable[str],
    target_unit: str,
    features: Iterable[Mapping[str, Any]],
    *,
    specification_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Register a future-only fitter specification without training or execution."""

    if asset_entity_id not in projection.assets:
        raise ForecastFitterSpecificationError(f"unknown tracked asset: {asset_entity_id}")
    if not name.strip():
        raise ForecastFitterSpecificationError("forecast fitter name must not be empty")
    if model_family not in FORECAST_FITTER_MODEL_FAMILIES:
        raise ForecastFitterSpecificationError(
            f"unsupported forecast fitter model family: {model_family}"
        )
    target_path = _field_path(target_field_path, "target")
    if not target_observation_type.strip():
        raise ForecastFitterSpecificationError("target observation type must not be empty")
    if not target_unit.strip():
        raise ForecastFitterSpecificationError("target unit must not be empty")

    normalized_features = [_feature(item) for item in features]
    if not normalized_features:
        raise ForecastFitterSpecificationError("at least one numeric feature is required")
    if len(normalized_features) > 32:
        raise ForecastFitterSpecificationError("at most 32 numeric features are supported")
    feature_names = [item["name"] for item in normalized_features]
    if len(feature_names) != len(set(feature_names)):
        raise ForecastFitterSpecificationError("forecast fitter feature names must be unique")
    normalized_features.sort(key=lambda item: item["name"])

    event_time = _timestamp(occurred_at)
    specification = {
        "id": str(specification_id or uuid4()),
        "asset_entity_id": asset_entity_id,
        "name": name,
        "initial_state_version": projection.assets[asset_entity_id]["epistemic_state_version"],
        "fitter_class": "FORECAST",
        "model_family": model_family,
        "registration_state": "REGISTERED_SPECIFICATION_ONLY",
        "capability_state": "DECLARED_NOT_VERIFIED",
        "target_contract": {
            "observation_type": target_observation_type,
            "structured_field_path": target_path,
            "value_kind": "NUMBER",
            "unit": target_unit,
            "semantics_state": "USER_DECLARED_NOT_VALIDATED",
        },
        "feature_contracts": normalized_features,
        "training_contract": {
            "objective": "SQUARED_ERROR",
            "objective_state": "DECLARED_NOT_EXECUTED",
            "training_data_state": "NOT_SELECTED",
            "training_state": "NOT_STARTED",
            "temporal_split_state": "REQUIRED_NOT_PREDECLARED",
            "negative_controls_state": "REQUIRED_NOT_PREDECLARED",
            "leakage_basis": "LEDGER_RECORDED_AT",
            "training_cutoff_state": "REQUIRED_PER_FUTURE_DESIGN",
            "post_cutoff_input_policy": "EXCLUDE",
        },
        "output_contract": {
            "point_prediction_state": "REQUIRED_NOT_IMPLEMENTED",
            "uncertainty_state": "REQUIRED_NOT_IMPLEMENTED",
            "unit_binding_policy": "EXACT_MATCH_REQUIRED",
        },
        "applicability": {
            "temporal_scope": "FUTURE_FORECASTS_ONLY",
            "retroactive_application_state": "PROHIBITED",
            "prior_assessment_effect": "NONE",
            "future_design_binding_state": "NOT_BOUND",
        },
        "implementation_state": "NOT_PROVIDED",
        "selection_state": "NOT_SELECTED",
        "execution_state": "NOT_ENABLED",
        "prediction_state": "NOT_PRODUCED",
        "validation_corpus_state": "NOT_PREDECLARED",
        "calibration_state": "NOT_ESTABLISHED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "future_admissibility_state": "NOT_ESTABLISHED",
        "network_access": False,
        "authority_state": "NO_AUTHORITY",
        "registered_at": event_time,
    }
    return create_forecast_fitter_specification_registered(
        specification,
        event_id=event_id,
        occurred_at=event_time,
    )


def _feature(value: Mapping[str, Any]) -> JsonObject:
    allowed = {"name", "observation_type", "structured_field_path", "unit"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ForecastFitterSpecificationError(f"unsupported feature fields: {unknown}")
    missing = sorted(allowed - set(value))
    if missing:
        raise ForecastFitterSpecificationError(f"missing feature fields: {missing}")
    name = value["name"]
    observation_type = value["observation_type"]
    unit = value["unit"]
    if not isinstance(name, str) or not name.strip():
        raise ForecastFitterSpecificationError("feature name must be a non-empty string")
    if not isinstance(observation_type, str) or not observation_type.strip():
        raise ForecastFitterSpecificationError(
            "feature observation type must be a non-empty string"
        )
    if not isinstance(unit, str) or not unit.strip():
        raise ForecastFitterSpecificationError("feature unit must be a non-empty string")
    return {
        "name": name,
        "observation_type": observation_type,
        "structured_field_path": _field_path(value["structured_field_path"], "feature"),
        "value_kind": "NUMBER",
        "unit": unit,
        "temporal_role": "PRE_ORIGIN_INPUT_ONLY",
        "semantics_state": "USER_DECLARED_NOT_VALIDATED",
        "missing_value_policy": "REJECT",
    }


def _field_path(value: Any, label: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ForecastFitterSpecificationError(
            f"{label} structured field path requires a list of string segments"
        )
    path = list(value)
    if not path or len(path) > 8:
        raise ForecastFitterSpecificationError(
            f"{label} structured field path requires between 1 and 8 segments"
        )
    if any(not isinstance(item, str) or not item.strip() for item in path):
        raise ForecastFitterSpecificationError(
            f"{label} structured field path requires non-empty string segments"
        )
    return path


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ForecastFitterSpecificationError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
