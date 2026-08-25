"""Fail-closed Phase 8A residual readback eligibility for non-forecast runs."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import create_residual_readback_completed
from readin.fitters import canonical_sha256
from readin.forecasting import ForecastDesignError, resolve_numeric_target

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

RESIDUAL_ALGORITHM_ID = "readin.reference.residual.forecast-eligibility-gate.v0.1"


class ResidualRuntimeError(ValueError):
    """Raised when a residual readback cannot be bound to eligible local state."""


def _timestamp(value: str | datetime | None = None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ResidualRuntimeError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def residual_implementation_sha256() -> str:
    """Bind receipts to the exact residual eligibility implementation."""

    return canonical_sha256(
        {
            "algorithm_id": RESIDUAL_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_residual_snapshot),
            "components_source": inspect.getsource(compute_residual_components),
        }
    )


def build_residual_snapshot(
    projection: ReadinProjection,
    scenario_run_id: str,
    observation_ids: Iterable[str],
) -> JsonObject:
    """Bind one scenario run to observations strictly later than its horizon."""

    if scenario_run_id not in projection.scenario_runs:
        raise ResidualRuntimeError(f"unknown scenario run: {scenario_run_id}")
    selected_observation_ids = list(observation_ids)
    if not selected_observation_ids:
        raise ResidualRuntimeError("at least one readback observation is required")
    if len(selected_observation_ids) != len(set(selected_observation_ids)):
        raise ResidualRuntimeError("readback observation ids must be unique")
    selected_observation_ids.sort()

    scenario_run = deepcopy(projection.scenario_runs[scenario_run_id])
    scenario = deepcopy(projection.scenarios[scenario_run["scenario_id"]])
    asset_id = scenario_run["asset_entity_id"]
    unknown_observation_ids = sorted(set(selected_observation_ids) - projection.observations.keys())
    if unknown_observation_ids:
        raise ResidualRuntimeError(
            f"readback references unknown observations: {unknown_observation_ids}"
        )

    observations = [deepcopy(projection.observations[item]) for item in selected_observation_ids]
    wrong_asset_ids = sorted(
        item["id"] for item in observations if asset_id not in item["subject_entities"]
    )
    if wrong_asset_ids:
        raise ResidualRuntimeError(
            f"readback observations do not concern the scenario asset: {wrong_asset_ids}"
        )
    horizon_end = _parse_timestamp(scenario["start_time"]) + timedelta(
        days=scenario["horizon_days"]
    )
    non_later_ids = sorted(
        item["id"] for item in observations if _parse_timestamp(item["observed_at"]) <= horizon_end
    )
    if non_later_ids:
        raise ResidualRuntimeError(
            f"readback observations must be later than the scenario horizon: {non_later_ids}"
        )

    design_ids = sorted(
        design_id
        for design_id, design in projection.forecast_evaluation_designs.items()
        if design["scenario_id"] == scenario["id"]
    )
    if not design_ids:
        raise ResidualRuntimeError("scenario has no predeclared forecast evaluation design")
    if len(design_ids) != 1:
        raise ResidualRuntimeError("scenario has multiple forecast evaluation designs")
    forecast_evaluation_design = deepcopy(projection.forecast_evaluation_designs[design_ids[0]])
    baseline_ids = sorted(
        baseline_id
        for baseline_id, baseline in projection.forecast_baselines.items()
        if baseline["forecast_evaluation_design_id"] == forecast_evaluation_design["id"]
    )
    if baseline_ids:
        baseline_id = baseline_ids[0]
        plan_id = projection._baseline_readback_selection_plan.get(baseline_id)
        if plan_id is None:
            raise ResidualRuntimeError(
                "forecast baseline exists, but Phase 8C residual scoring is not enabled"
            )
        selection_run_id = projection._plan_readback_selection_run.get(plan_id)
        if selection_run_id is None:
            raise ResidualRuntimeError(
                "forecast readback selection has not completed; residual scoring is not enabled"
            )
        selection_run = projection.readback_selection_runs[selection_run_id]
        if selection_run["selection_state"] != "UNIQUE_MATCH_SELECTED":
            raise ResidualRuntimeError(
                "forecast readback selection abstained: "
                f"{selection_run['selection_state']}; residual scoring is not enabled"
            )
        if selection_run_id in projection._selection_run_forecast_residual:
            raise ResidualRuntimeError(
                "Phase 8E descriptive forecast residual already exists; "
                "the Phase 8A no-baseline readback path is not applicable"
            )
        raise ResidualRuntimeError(
            "Phase 8D selected a unique readback observation, but residual scoring is not enabled"
        )
    target = forecast_evaluation_design["target"]
    mismatched_observation_ids = sorted(
        item["id"]
        for item in observations
        if item["observation_type"] != target["observation_type"]
    )
    if mismatched_observation_ids:
        raise ResidualRuntimeError(
            "readback observations do not match the predeclared target type: "
            f"{mismatched_observation_ids}"
        )
    target_values = []
    try:
        for observation in observations:
            target_values.append(
                {
                    "observation_id": observation["id"],
                    "value": resolve_numeric_target(
                        observation["content"]["structured_payload"],
                        target["structured_field_path"],
                    ),
                }
            )
    except ForecastDesignError as error:
        raise ResidualRuntimeError(str(error)) from error

    artifact_ids = sorted({item["source_artifact_id"] for item in observations})
    frame_ids = sorted({item["observer_frame_id"] for item in observations})
    observation_snapshot = {
        "observations": observations,
        "evidence_manifests": [deepcopy(projection.evidence[item]) for item in artifact_ids],
        "observer_frames": [deepcopy(projection.frames[item]) for item in frame_ids],
        "forecast_evaluation_design": forecast_evaluation_design,
        "target_values": target_values,
    }
    return {
        "asset_entity_id": asset_id,
        "scenario": scenario,
        "scenario_run": scenario_run,
        "forecast_evaluation_design": forecast_evaluation_design,
        "horizon_end": horizon_end.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "observation_ids": selected_observation_ids,
        "source_artifact_ids": artifact_ids,
        "observer_frame_ids": frame_ids,
        "observation_snapshot": observation_snapshot,
    }


def compute_residual_components(snapshot: Mapping[str, Any]) -> JsonObject:
    """Abstain unless the reference run contains an actual forecast baseline."""

    prediction_state = snapshot["scenario_run"]["prediction_state"]
    if prediction_state != "NOT_REQUESTED":
        raise ResidualRuntimeError(
            f"unsupported scenario prediction state for Phase 8A: {prediction_state}"
        )
    return {
        "temporal_order_state": "LATER_THAN_SCENARIO_HORIZON_CONFIRMED",
        "baseline_eligibility_state": "INELIGIBLE_NO_FORECAST_BASELINE",
        "reference_prediction_state": "NOT_REQUESTED",
        "residual_state": "NOT_COMPUTED",
        "residual_value": None,
        "validity_update_state": "NOT_APPLIED",
        "weighting_update_state": "NOT_APPLIED",
        "future_admissibility_update_state": "NOT_APPLIED",
        "learning_state": "NOT_STARTED",
        "interpretation": "READBACK_RETAINED_WITHOUT_FORECAST_RESIDUAL",
    }


def execute_residual_readback(
    projection: ReadinProjection,
    scenario_run_id: str,
    observation_ids: Iterable[str],
    *,
    readback_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Record a replay-verifiable readback abstention without updating validity."""

    snapshot = build_residual_snapshot(projection, scenario_run_id, observation_ids)
    components = compute_residual_components(snapshot)
    selected_readback_id = str(readback_id or uuid4())
    selected_receipt_id = str(receipt_id or uuid4())
    event_time = _timestamp(occurred_at)
    asset_id = snapshot["asset_entity_id"]
    receipt = {
        "id": selected_receipt_id,
        "readback_id": selected_readback_id,
        "asset_entity_id": asset_id,
        "asset_state_version": projection.assets[asset_id]["epistemic_state_version"],
        "scenario_run_id": scenario_run_id,
        "forecast_evaluation_design_id": snapshot["forecast_evaluation_design"]["id"],
        "forecast_evaluation_design_sha256": canonical_sha256(
            snapshot["forecast_evaluation_design"]
        ),
        "scenario_run_sha256": canonical_sha256(snapshot["scenario_run"]),
        "scenario_sha256": canonical_sha256(snapshot["scenario"]),
        "observation_ids": deepcopy(snapshot["observation_ids"]),
        "source_artifact_ids": deepcopy(snapshot["source_artifact_ids"]),
        "observer_frame_ids": deepcopy(snapshot["observer_frame_ids"]),
        "observation_snapshot_sha256": canonical_sha256(snapshot["observation_snapshot"]),
        "algorithm_id": RESIDUAL_ALGORITHM_ID,
        "implementation_sha256": residual_implementation_sha256(),
        "outcome_sha256": canonical_sha256(components),
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    readback = {
        "id": selected_readback_id,
        "asset_entity_id": asset_id,
        "scenario_run_id": scenario_run_id,
        "observation_ids": deepcopy(snapshot["observation_ids"]),
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_residual_readback_completed(
        readback,
        event_id=event_id,
        occurred_at=event_time,
    )
