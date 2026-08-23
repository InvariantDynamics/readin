"""Assumption-bound scenario branches for the bounded Phase 5 runtime."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from readin.events import create_scenario_created, create_scenario_run_completed
from readin.fitters import canonical_sha256

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

SCENARIO_ALGORITHM_ID = "readin.reference.scenario.conditional-branch-evaluation.v0.1"


class ScenarioRuntimeError(ValueError):
    """Raised when a bounded scenario cannot be created or evaluated safely."""


def scenario_implementation_sha256() -> str:
    """Bind a scenario receipt to executable branch and snapshot semantics."""

    return canonical_sha256(
        {
            "algorithm_id": SCENARIO_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_scenario_snapshot),
            "evaluation_source": inspect.getsource(compute_scenario_components),
            "topology_source": inspect.getsource(_branch_order),
        }
    )


def create_bounded_scenario(
    projection: ReadinProjection,
    asset_entity_id: str,
    name: str,
    belief_revision_id: str,
    target_entity_ids: Iterable[str],
    assumptions: Iterable[Mapping[str, Any]],
    interventions: Iterable[Mapping[str, Any]],
    branches: Iterable[Mapping[str, Any]],
    *,
    start_time: str | datetime,
    horizon_days: int,
    scenario_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Create a scenario plan and force one explicit unknown/unmodeled branch."""

    if asset_entity_id not in projection.assets:
        raise ScenarioRuntimeError(f"unknown tracked asset: {asset_entity_id}")
    selected_scenario_id = str(scenario_id or uuid4())
    normalized_assumptions = [
        {
            "id": str(item["id"]),
            "statement": item["statement"],
            "validation_state": "USER_SUPPLIED_NOT_VALIDATED",
        }
        for item in assumptions
    ]
    normalized_interventions = [
        {
            "id": str(item["id"]),
            "target_entity_id": str(item["target_entity_id"]),
            "description": item["description"],
            "causal_status": "NOT_ESTABLISHED",
        }
        for item in interventions
    ]
    normalized_branches = [
        {
            "id": str(item["id"]),
            "parent_branch_id": (
                str(item["parent_branch_id"]) if item.get("parent_branch_id") is not None else None
            ),
            "kind": "CONDITIONAL",
            "name": item["name"],
            "outcome_statement": item["outcome_statement"],
            "condition": {
                "hypothesis_id": str(item["condition"]["hypothesis_id"]),
                "expected_state": item["condition"]["expected_state"],
            },
            "assumption_ids": sorted(str(value) for value in item.get("assumption_ids", ())),
            "intervention_ids": sorted(str(value) for value in item.get("intervention_ids", ())),
            "transition_support_state": "USER_DEFINED_NOT_VALIDATED",
        }
        for item in branches
    ]
    unknown_branch_id = str(
        uuid5(NAMESPACE_URL, f"readin:scenario:{selected_scenario_id}:unknown-unmodeled")
    )
    normalized_branches.append(
        {
            "id": unknown_branch_id,
            "parent_branch_id": None,
            "kind": "UNKNOWN_UNMODELED",
            "name": "Unknown / unmodeled region",
            "outcome_statement": "Outcomes outside the declared conditional branches",
            "condition": None,
            "assumption_ids": [],
            "intervention_ids": [],
            "transition_support_state": "UNMODELED",
        }
    )
    normalized_branches.sort(key=lambda item: item["id"])
    event_time = _timestamp(occurred_at)
    scenario = {
        "id": selected_scenario_id,
        "asset_entity_id": asset_entity_id,
        "name": name,
        "mode": "CONDITIONAL_EXPLORATION",
        "initial_state_version": projection.assets[asset_entity_id]["epistemic_state_version"],
        "belief_revision_id": belief_revision_id,
        "target_entity_ids": sorted(str(item) for item in target_entity_ids),
        "start_time": _timestamp(start_time),
        "horizon_days": horizon_days,
        "assumptions": normalized_assumptions,
        "interventions": normalized_interventions,
        "branches": normalized_branches,
        "unknown_branch_policy": "REQUIRED_VISIBLE",
        "likelihood_state": "NOT_COMPUTED",
        "prediction_state": "NOT_REQUESTED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "created_at": event_time,
    }
    return create_scenario_created(
        scenario,
        event_id=event_id,
        occurred_at=event_time,
    )


def build_scenario_snapshot(projection: ReadinProjection, scenario_id: str) -> JsonObject:
    """Return the immutable plan and belief revision used by scenario execution."""

    if scenario_id not in projection.scenarios:
        raise ScenarioRuntimeError(f"unknown scenario: {scenario_id}")
    scenario = deepcopy(projection.scenarios[scenario_id])
    revision_id = scenario["belief_revision_id"]
    if revision_id not in projection.belief_revisions:
        raise ScenarioRuntimeError(f"scenario references unknown belief revision: {revision_id}")
    return {
        "scenario": scenario,
        "belief_revision": deepcopy(projection.belief_revisions[revision_id]),
    }


def compute_scenario_components(snapshot: Mapping[str, Any]) -> JsonObject:
    """Evaluate branch antecedents without simulating outcomes or assigning likelihoods."""

    scenario = snapshot["scenario"]
    revision_states = {
        item["hypothesis_id"]: item["state"] for item in snapshot["belief_revision"]["node_results"]
    }
    branches = {item["id"]: item for item in scenario["branches"]}
    order = _branch_order(branches)
    results_by_id: dict[str, JsonObject] = {}
    for branch_id in order:
        branch = branches[branch_id]
        source_hypothesis_id = None
        source_revision_state = None
        if branch["kind"] == "UNKNOWN_UNMODELED":
            antecedent_state = "UNMODELED_REGION_RETAINED"
        elif (
            branch["parent_branch_id"] is not None
            and results_by_id[branch["parent_branch_id"]]["antecedent_state"] != "CONDITION_MATCHED"
        ):
            antecedent_state = "BLOCKED_BY_PARENT"
            source_hypothesis_id = branch["condition"]["hypothesis_id"]
            source_revision_state = revision_states[source_hypothesis_id]
        else:
            source_hypothesis_id = branch["condition"]["hypothesis_id"]
            source_revision_state = revision_states[source_hypothesis_id]
            if source_revision_state == branch["condition"]["expected_state"]:
                antecedent_state = "CONDITION_MATCHED"
            elif source_revision_state in {"CONFLICTED", "UNRESOLVED"}:
                antecedent_state = "CONDITION_UNRESOLVED"
            else:
                antecedent_state = "CONDITION_NOT_MATCHED"
        results_by_id[branch_id] = {
            "branch_id": branch_id,
            "branch_kind": branch["kind"],
            "parent_branch_id": branch["parent_branch_id"],
            "source_hypothesis_id": source_hypothesis_id,
            "source_revision_state": source_revision_state,
            "antecedent_state": antecedent_state,
            "likelihood_state": "NOT_COMPUTED",
            "trajectory_state": (
                "UNMODELED_NOT_SIMULATED"
                if branch["kind"] == "UNKNOWN_UNMODELED"
                else "USER_DEFINED_NOT_SIMULATED"
            ),
            "outcome_state": "CONDITIONAL_NOT_PREDICTED",
        }

    results = [results_by_id[item] for item in sorted(results_by_id)]
    return {
        "branch_results": results,
        "summary": {
            "conditional_branch_count": sum(
                item["branch_kind"] == "CONDITIONAL" for item in results
            ),
            "matched_branch_count": sum(
                item["antecedent_state"] == "CONDITION_MATCHED" for item in results
            ),
            "unresolved_branch_count": sum(
                item["antecedent_state"] in {"CONDITION_UNRESOLVED", "BLOCKED_BY_PARENT"}
                for item in results
            ),
            "unknown_branch_visible": any(
                item["antecedent_state"] == "UNMODELED_REGION_RETAINED" for item in results
            ),
        },
        "fitter_execution_state": "NOT_RUN_NO_FORECAST_CAPABLE_FITTER",
        "likelihood_state": "NOT_COMPUTED",
        "trajectory_state": "NOT_SIMULATED",
        "prediction_state": "NOT_REQUESTED",
        "empirical_validity_state": "NOT_ESTABLISHED",
    }


def execute_scenario(
    projection: ReadinProjection,
    scenario_id: str,
    *,
    run_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
    deterministic_ids: bool = False,
) -> JsonObject:
    """Create one replay-verifiable structural scenario evaluation."""

    snapshot = build_scenario_snapshot(projection, scenario_id)
    scenario = snapshot["scenario"]
    asset_entity_id = scenario["asset_entity_id"]
    components = compute_scenario_components(snapshot)
    selected_ids = _execution_ids(
        scenario_id,
        run_id=run_id,
        receipt_id=receipt_id,
        event_id=event_id,
        deterministic=deterministic_ids,
    )
    event_time = _timestamp(occurred_at)
    receipt = {
        "id": selected_ids["receipt_id"],
        "scenario_id": scenario_id,
        "asset_entity_id": asset_entity_id,
        "asset_state_version": projection.assets[asset_entity_id]["epistemic_state_version"],
        "scenario_snapshot_sha256": canonical_sha256(scenario),
        "belief_revision_id": scenario["belief_revision_id"],
        "belief_revision_sha256": canonical_sha256(snapshot["belief_revision"]),
        "branch_ids": sorted(item["id"] for item in scenario["branches"]),
        "assumption_ids": sorted(item["id"] for item in scenario["assumptions"]),
        "intervention_ids": sorted(item["id"] for item in scenario["interventions"]),
        "algorithm_id": SCENARIO_ALGORITHM_ID,
        "implementation_sha256": scenario_implementation_sha256(),
        "outcome_sha256": canonical_sha256(components),
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "fitter_execution_state": "NOT_RUN_NO_FORECAST_CAPABLE_FITTER",
        "network_access": False,
        "likelihood_state": "NOT_COMPUTED",
        "trajectory_state": "NOT_SIMULATED",
        "prediction_state": "NOT_REQUESTED",
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    run = {
        "id": selected_ids["run_id"],
        "scenario_id": scenario_id,
        "asset_entity_id": asset_entity_id,
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_scenario_run_completed(
        run,
        event_id=selected_ids["event_id"],
        occurred_at=event_time,
    )


def _branch_order(branches: Mapping[str, Mapping[str, Any]]) -> list[str]:
    indegree = {item: 0 for item in branches}
    children: dict[str, set[str]] = {item: set() for item in branches}
    for branch in branches.values():
        parent = branch["parent_branch_id"]
        if parent is None:
            continue
        if parent not in branches:
            raise ScenarioRuntimeError(f"scenario branch references unknown parent: {parent}")
        children[parent].add(branch["id"])
        indegree[branch["id"]] += 1
    ready = sorted(item for item, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        branch_id = ready.pop(0)
        order.append(branch_id)
        for child in sorted(children[branch_id]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(order) != len(branches):
        raise ScenarioRuntimeError("scenario branches contain a cycle")
    return order


def _execution_ids(
    scenario_id: str,
    *,
    run_id: str | UUID | None,
    receipt_id: str | UUID | None,
    event_id: str | UUID | None,
    deterministic: bool,
) -> JsonObject:
    values = {
        "run_id": str(run_id or uuid4()),
        "receipt_id": str(receipt_id or uuid4()),
        "event_id": str(event_id or uuid4()),
    }
    if deterministic:
        provided = {"run_id": run_id, "receipt_id": receipt_id, "event_id": event_id}
        for key in values:
            if provided[key] is None:
                values[key] = str(uuid5(NAMESPACE_URL, f"readin:scenario:{scenario_id}:{key}"))
    return values


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ScenarioRuntimeError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
