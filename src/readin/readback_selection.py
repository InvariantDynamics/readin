"""Predeclared Phase 8D readback selection without residual scoring."""

from __future__ import annotations

import inspect
import math
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import (
    create_forecast_readback_selection_completed,
    create_forecast_readback_selection_plan_created,
)
from readin.fitters import canonical_sha256
from readin.forecasting import ForecastDesignError, resolve_numeric_target

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

READBACK_SELECTION_ALGORITHM_ID = "readin.reference.forecast.readback-selection-exactly-one.v0.1"


class ReadbackSelectionError(ValueError):
    """Raised when a readback-selection boundary or execution is invalid."""


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReadbackSelectionError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC)


def _timestamp(value: str | datetime | None = None) -> str:
    parsed = datetime.now(UTC) if value is None else _parse_timestamp(value)
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def readback_selection_implementation_sha256() -> str:
    """Bind execution receipts to the exact deterministic selector."""

    return canonical_sha256(
        {
            "algorithm_id": READBACK_SELECTION_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_readback_selection_snapshot),
            "components_source": inspect.getsource(compute_readback_selection_components),
        }
    )


def create_readback_selection_plan(
    projection: ReadinProjection,
    forecast_baseline_id: str,
    eligible_observer_frame_ids: Iterable[str],
    *,
    name: str,
    observed_window_end: str | datetime,
    ledger_admission_cutoff: str | datetime,
    plan_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Predeclare an exactly-one selection aperture before forecast origin."""

    if forecast_baseline_id not in projection.forecast_baselines:
        raise ReadbackSelectionError(f"unknown forecast baseline: {forecast_baseline_id}")
    if any(
        plan["forecast_baseline_id"] == forecast_baseline_id
        for plan in projection.readback_selection_plans.values()
    ):
        raise ReadbackSelectionError("forecast baseline already has a readback selection plan")
    frame_ids = list(eligible_observer_frame_ids)
    if not frame_ids:
        raise ReadbackSelectionError("at least one eligible observer frame is required")
    if len(frame_ids) != len(set(frame_ids)):
        raise ReadbackSelectionError("eligible observer frame ids must be unique")
    frame_ids.sort()
    missing_frames = sorted(set(frame_ids) - projection.frames.keys())
    if missing_frames:
        raise ReadbackSelectionError(f"unknown eligible observer frames: {missing_frames}")

    baseline = projection.forecast_baselines[forecast_baseline_id]
    design = projection.forecast_evaluation_designs[baseline["forecast_evaluation_design_id"]]
    event_time = _timestamp(occurred_at)
    event_dt = _parse_timestamp(event_time)
    baseline_dt = _parse_timestamp(baseline["recorded_at"])
    origin_dt = _parse_timestamp(design["timing"]["forecast_origin"])
    horizon_dt = _parse_timestamp(design["timing"]["horizon_end"])
    window_end = _parse_timestamp(observed_window_end)
    admission_cutoff = _parse_timestamp(ledger_admission_cutoff)
    if event_dt < baseline_dt:
        raise ReadbackSelectionError("readback selection plan cannot precede its baseline")
    if event_dt >= origin_dt:
        raise ReadbackSelectionError(
            "readback selection plan must be recorded before forecast origin"
        )
    if window_end <= horizon_dt:
        raise ReadbackSelectionError("observed window end must follow the forecast horizon")
    if admission_cutoff < window_end:
        raise ReadbackSelectionError("ledger admission cutoff cannot precede observed window end")

    target = design["target"]
    plan = {
        "id": str(plan_id or uuid4()),
        "asset_entity_id": baseline["asset_entity_id"],
        "forecast_baseline_id": forecast_baseline_id,
        "forecast_evaluation_design_id": design["id"],
        "scenario_id": baseline["scenario_id"],
        "name": name,
        "initial_state_version": projection.assets[baseline["asset_entity_id"]][
            "epistemic_state_version"
        ],
        "target": {
            "observation_type": target["observation_type"],
            "structured_field_path": deepcopy(target["structured_field_path"]),
            "value_kind": "NUMBER",
            "unit": target["unit"],
            "unit_match_state": "USER_DECLARED_NOT_VERIFIED",
        },
        "timing": {
            "forecast_origin": design["timing"]["forecast_origin"],
            "horizon_end": design["timing"]["horizon_end"],
            "observed_window_end": _timestamp(window_end),
            "ledger_admission_cutoff": _timestamp(admission_cutoff),
            "observation_time_policy": "STRICTLY_AFTER_HORIZON_THROUGH_WINDOW_END",
            "admission_time_policy": "AT_OR_BEFORE_CUTOFF",
        },
        "eligible_observer_frame_ids": frame_ids,
        "selection_policy": {
            "cardinality": "EXACTLY_ONE",
            "zero_candidate_policy": "ABSTAIN",
            "multiple_candidate_policy": "ABSTAIN",
            "aggregation_policy": "PROHIBITED",
            "ranking_policy": "NONE",
            "post_hoc_selection_policy": "PROHIBITED",
        },
        "preregistration_state": "RECORDED_BEFORE_FORECAST_ORIGIN",
        "residual_scoring_state": "NOT_ENABLED",
        "created_at": event_time,
    }
    return create_forecast_readback_selection_plan_created(
        plan, event_id=event_id, occurred_at=event_time
    )


def build_readback_selection_snapshot(projection: ReadinProjection, plan_id: str) -> JsonObject:
    """Classify every observation concerning the asset against the frozen aperture."""

    if plan_id not in projection.readback_selection_plans:
        raise ReadbackSelectionError(f"unknown readback selection plan: {plan_id}")
    if plan_id in projection._plan_readback_selection_run:
        raise ReadbackSelectionError("readback selection plan already has a completed run")
    plan = deepcopy(projection.readback_selection_plans[plan_id])
    baseline = deepcopy(projection.forecast_baselines[plan["forecast_baseline_id"]])
    design = deepcopy(projection.forecast_evaluation_designs[plan["forecast_evaluation_design_id"]])
    scenario = deepcopy(projection.scenarios[plan["scenario_id"]])
    horizon = _parse_timestamp(plan["timing"]["horizon_end"])
    window_end = _parse_timestamp(plan["timing"]["observed_window_end"])
    cutoff = _parse_timestamp(plan["timing"]["ledger_admission_cutoff"])

    classifications: dict[str, list[str]] = {
        "excluded_after_admission_cutoff_observation_ids": [],
        "excluded_outside_observed_window_observation_ids": [],
        "excluded_observation_type_mismatch_observation_ids": [],
        "excluded_frame_mismatch_observation_ids": [],
        "excluded_invalid_target_observation_ids": [],
    }
    candidates: list[dict[str, Any]] = []
    considered: list[dict[str, Any]] = []
    asset_id = plan["asset_entity_id"]
    for observation_id in sorted(projection.observations):
        observation = projection.observations[observation_id]
        if asset_id not in observation["subject_entities"]:
            continue
        recorded_at = projection._observation_recorded_at[observation_id]
        considered.append({"observation": deepcopy(observation), "ledger_recorded_at": recorded_at})
        if _parse_timestamp(recorded_at) > cutoff:
            classifications["excluded_after_admission_cutoff_observation_ids"].append(
                observation_id
            )
            continue
        observed_at = _parse_timestamp(observation["observed_at"])
        if observed_at <= horizon or observed_at > window_end:
            classifications["excluded_outside_observed_window_observation_ids"].append(
                observation_id
            )
            continue
        if observation["observation_type"] != plan["target"]["observation_type"]:
            classifications["excluded_observation_type_mismatch_observation_ids"].append(
                observation_id
            )
            continue
        if observation["observer_frame_id"] not in plan["eligible_observer_frame_ids"]:
            classifications["excluded_frame_mismatch_observation_ids"].append(observation_id)
            continue
        try:
            value = resolve_numeric_target(
                observation["content"]["structured_payload"],
                plan["target"]["structured_field_path"],
            )
            if not math.isfinite(value):
                raise ForecastDesignError("observation target value must be finite")
        except ForecastDesignError:
            classifications["excluded_invalid_target_observation_ids"].append(observation_id)
            continue
        candidates.append({"observation_id": observation_id, "target_value": value})

    artifact_ids = sorted({item["observation"]["source_artifact_id"] for item in considered})

    return {
        "plan": plan,
        "forecast_baseline": baseline,
        "forecast_evaluation_design": design,
        "scenario": scenario,
        "eligible_observer_frames": [
            deepcopy(projection.frames[item]) for item in plan["eligible_observer_frame_ids"]
        ],
        "considered_observations": considered,
        "evidence_manifests": [deepcopy(projection.evidence[item]) for item in artifact_ids],
        "candidate_observations": candidates,
        **classifications,
    }


def compute_readback_selection_components(snapshot: Mapping[str, Any]) -> JsonObject:
    """Select exactly one compatible observation or preserve an explicit abstention."""

    candidates = deepcopy(snapshot["candidate_observations"])
    candidate_ids = [item["observation_id"] for item in candidates]
    if len(candidates) == 1:
        state = "UNIQUE_MATCH_SELECTED"
        selected_id: str | None = candidates[0]["observation_id"]
        selected_value: int | float | None = candidates[0]["target_value"]
    elif not candidates:
        state = "ABSTAINED_NO_MATCH"
        selected_id = None
        selected_value = None
    else:
        state = "ABSTAINED_MULTIPLE_MATCHES"
        selected_id = None
        selected_value = None
    classification_keys = [
        "excluded_after_admission_cutoff_observation_ids",
        "excluded_outside_observed_window_observation_ids",
        "excluded_observation_type_mismatch_observation_ids",
        "excluded_frame_mismatch_observation_ids",
        "excluded_invalid_target_observation_ids",
    ]
    return {
        "selection_state": state,
        "candidate_count": len(candidates),
        "candidate_observation_ids": candidate_ids,
        "selected_observation_id": selected_id,
        "selected_target_value": selected_value,
        **{key: deepcopy(snapshot[key]) for key in classification_keys},
        "aggregation_state": "NOT_PERFORMED",
        "ranking_state": "NOT_PERFORMED",
        "unit_match_state": "USER_DECLARED_NOT_VERIFIED",
        "residual_state": "NOT_COMPUTED",
        "residual_value": None,
        "residual_scoring_state": "NOT_ENABLED",
        "calibration_state": "NOT_ESTABLISHED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "validity_update_state": "NOT_APPLIED",
        "weighting_update_state": "NOT_APPLIED",
        "future_admissibility_update_state": "NOT_APPLIED",
        "learning_state": "NOT_STARTED",
        "authority_state": "NO_AUTHORITY",
    }


def execute_readback_selection(
    projection: ReadinProjection,
    plan_id: str,
    *,
    run_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Execute the frozen aperture after its admission cutoff without scoring."""

    snapshot = build_readback_selection_snapshot(projection, plan_id)
    components = compute_readback_selection_components(snapshot)
    event_time = _timestamp(occurred_at)
    if _parse_timestamp(event_time) < _parse_timestamp(
        snapshot["plan"]["timing"]["ledger_admission_cutoff"]
    ):
        raise ReadbackSelectionError(
            "readback selection cannot execute before ledger admission cutoff"
        )
    selected_run_id = str(run_id or uuid4())
    selected_receipt_id = str(receipt_id or uuid4())
    plan = snapshot["plan"]
    asset_id = plan["asset_entity_id"]
    receipt = {
        "id": selected_receipt_id,
        "readback_selection_run_id": selected_run_id,
        "readback_selection_plan_id": plan_id,
        "asset_entity_id": asset_id,
        "asset_state_version": projection.assets[asset_id]["epistemic_state_version"],
        "forecast_baseline_id": plan["forecast_baseline_id"],
        "forecast_evaluation_design_id": plan["forecast_evaluation_design_id"],
        "scenario_id": plan["scenario_id"],
        "plan_sha256": canonical_sha256(plan),
        "forecast_baseline_sha256": canonical_sha256(snapshot["forecast_baseline"]),
        "forecast_evaluation_design_sha256": canonical_sha256(
            snapshot["forecast_evaluation_design"]
        ),
        "scenario_sha256": canonical_sha256(snapshot["scenario"]),
        "eligible_observer_frame_ids": deepcopy(plan["eligible_observer_frame_ids"]),
        "eligible_observer_frames_sha256": canonical_sha256(snapshot["eligible_observer_frames"]),
        "input_snapshot_sha256": canonical_sha256(snapshot),
        "algorithm_id": READBACK_SELECTION_ALGORITHM_ID,
        "implementation_sha256": readback_selection_implementation_sha256(),
        "outcome_sha256": canonical_sha256(components),
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    run = {
        "id": selected_run_id,
        "readback_selection_plan_id": plan_id,
        "asset_entity_id": asset_id,
        "forecast_baseline_id": plan["forecast_baseline_id"],
        "forecast_evaluation_design_id": plan["forecast_evaluation_design_id"],
        "scenario_id": plan["scenario_id"],
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_forecast_readback_selection_completed(
        run, event_id=event_id, occurred_at=event_time
    )
