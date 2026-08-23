"""Dependency-aware categorical belief propagation for bounded Phase 5 graphs."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from readin.events import create_belief_revision_completed
from readin.fitters import canonical_sha256

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

BELIEF_ALGORITHM_ID = "readin.reference.belief.dependency-aware-categorical-dag.v0.1"
BELIEF_INTERPRETATION = "DIAGNOSTIC_SIGNAL_BALANCE_NOT_TRUTH_PROBABILITY"


class BeliefRuntimeError(ValueError):
    """Raised when a bounded belief graph cannot be evaluated safely."""


def belief_implementation_sha256() -> str:
    """Bind receipts to the executable propagation and input-binding source."""

    return canonical_sha256(
        {
            "algorithm_id": BELIEF_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_belief_snapshot),
            "propagation_source": inspect.getsource(compute_belief_components),
            "state_source": inspect.getsource(_categorical_state),
            "topology_source": inspect.getsource(_topological_order),
        }
    )


def build_belief_snapshot(
    projection: ReadinProjection,
    asset_entity_id: str,
    hypothesis_ids: Iterable[str] | None = None,
) -> JsonObject:
    """Return the complete immutable input projection for one belief revision."""

    selected = list(hypothesis_ids or ())
    if not selected:
        selected = [
            hypothesis_id
            for hypothesis_id, hypothesis in projection.hypotheses.items()
            if hypothesis["asset_entity_id"] == asset_entity_id
        ]
    if not selected:
        raise BeliefRuntimeError("at least one hypothesis is required")
    if len(selected) != len(set(selected)):
        raise BeliefRuntimeError("a hypothesis may appear only once in a belief revision")
    selected = sorted(selected)

    unknown = sorted(set(selected) - projection.hypotheses.keys())
    if unknown:
        raise BeliefRuntimeError(f"unknown hypotheses: {unknown}")
    wrong_asset = sorted(
        hypothesis_id
        for hypothesis_id in selected
        if projection.hypotheses[hypothesis_id]["asset_entity_id"] != asset_entity_id
    )
    if wrong_asset:
        raise BeliefRuntimeError(f"hypotheses belong to another asset: {wrong_asset}")

    selected_set = set(selected)
    omitted_parents = sorted(
        edge["source_hypothesis_id"]
        for edge in projection.belief_edges.values()
        if edge["target_hypothesis_id"] in selected_set
        and edge["source_hypothesis_id"] not in selected_set
    )
    if omitted_parents:
        raise BeliefRuntimeError(
            f"belief revision omits upstream hypotheses: {sorted(set(omitted_parents))}"
        )

    hypotheses = [deepcopy(projection.hypotheses[item]) for item in selected]
    edges = [
        deepcopy(edge)
        for edge in projection.belief_edges.values()
        if edge["source_hypothesis_id"] in selected_set
        and edge["target_hypothesis_id"] in selected_set
    ]
    edges.sort(key=lambda item: item["id"])
    claim_ids = sorted(
        {
            binding["claim_id"]
            for hypothesis in hypotheses
            for binding in hypothesis["claim_bindings"]
        }
    )
    claims = [projection.claim_view(claim_id) for claim_id in claim_ids]
    evidence_link_ids = sorted(link["id"] for claim in claims for link in claim["evidence_links"])
    dependency_group_ids = {
        link["dependency_group"]
        for claim in claims
        for link in claim["evidence_links"]
        if link["dependency_group"] is not None
    }
    dependencies = [
        deepcopy(dependency)
        for dependency in projection.dependencies.values()
        if dependency["dependency_group_id"] in dependency_group_ids
    ]
    dependencies.sort(key=lambda item: item["id"])
    return {
        "asset_entity_id": asset_entity_id,
        "hypotheses": hypotheses,
        "belief_edges": edges,
        "claims": claims,
        "evidence_dependencies": dependencies,
        "input_ids": {
            "hypothesis_ids": selected,
            "belief_edge_ids": [item["id"] for item in edges],
            "claim_ids": claim_ids,
            "evidence_link_ids": evidence_link_ids,
            "dependency_ids": [item["id"] for item in dependencies],
        },
    }


def compute_belief_components(snapshot: Mapping[str, Any]) -> JsonObject:
    """Propagate categorical signals through a bounded directed acyclic graph."""

    hypotheses = {item["id"]: item for item in snapshot["hypotheses"]}
    claims = {item["claim"]["id"]: item for item in snapshot["claims"]}
    edges = list(snapshot["belief_edges"])
    order = _topological_order(hypotheses, edges)
    incoming: dict[str, list[Mapping[str, Any]]] = {item: [] for item in hypotheses}
    for edge in edges:
        incoming[edge["target_hypothesis_id"]].append(edge)
    for selected_edges in incoming.values():
        selected_edges.sort(key=lambda item: item["id"])

    results_by_id: dict[str, JsonObject] = {}
    for hypothesis_id in order:
        hypothesis = hypotheses[hypothesis_id]
        support_units: set[str] = set()
        challenge_units: set[str] = set()
        dependency_groups: set[str] = set()
        input_claim_ids: list[str] = []

        for binding in hypothesis["claim_bindings"]:
            claim_id = binding["claim_id"]
            input_claim_ids.append(claim_id)
            binding_supports = binding["polarity"] == "SUPPORTS_HYPOTHESIS"
            for link in claims[claim_id]["evidence_links"]:
                signal = _link_signal(link["role"])
                if signal is None:
                    continue
                if not binding_supports:
                    signal = "CHALLENGE" if signal == "SUPPORT" else "SUPPORT"
                dependency_group = link["dependency_group"]
                unit = (
                    f"dependency:{dependency_group}"
                    if dependency_group is not None
                    else f"evidence:{link['evidence_id']}"
                )
                if dependency_group is not None:
                    dependency_groups.add(dependency_group)
                if signal == "SUPPORT":
                    support_units.add(unit)
                else:
                    challenge_units.add(unit)

        incoming_evaluations: list[JsonObject] = []
        conditional_support_units: set[str] = set()
        conditional_challenge_units: set[str] = set()
        for edge in incoming[hypothesis_id]:
            source_state = results_by_id[edge["source_hypothesis_id"]]["state"]
            evaluation = {
                "edge_id": edge["id"],
                "source_hypothesis_id": edge["source_hypothesis_id"],
                "source_state": source_state,
                "disposition": "WITHHELD_SOURCE_NOT_SUPPORT_LEADING",
            }
            if source_state == "SUPPORT_LEADING":
                unit = f"hypothesis:{edge['source_hypothesis_id']}"
                if edge["polarity"] == "SUPPORTS_IF_SOURCE_SUPPORT_LEADING":
                    conditional_support_units.add(unit)
                    evaluation["disposition"] = "APPLIED_SUPPORT"
                else:
                    conditional_challenge_units.add(unit)
                    evaluation["disposition"] = "APPLIED_CHALLENGE"
            incoming_evaluations.append(evaluation)

        all_support = support_units | conditional_support_units
        all_challenge = challenge_units | conditional_challenge_units
        results_by_id[hypothesis_id] = {
            "hypothesis_id": hypothesis_id,
            "state": _categorical_state(all_support, all_challenge),
            "direct_support_unit_count": len(support_units),
            "direct_challenge_unit_count": len(challenge_units),
            "conditional_support_unit_count": len(conditional_support_units),
            "conditional_challenge_unit_count": len(conditional_challenge_units),
            "conflicted_unit_count": len(all_support.intersection(all_challenge)),
            "input_claim_ids": sorted(input_claim_ids),
            "dependency_group_ids": sorted(dependency_groups),
            "incoming_edge_evaluations": incoming_evaluations,
            "independence_state": (
                "DECLARED_DEPENDENCY_GROUPS_PRESERVED"
                if dependency_groups
                else "INDEPENDENCE_NOT_ESTABLISHED"
            ),
            "interpretation": BELIEF_INTERPRETATION,
        }

    return {
        "graph": {
            "node_count": len(hypotheses),
            "edge_count": len(edges),
            "acyclic": True,
            "topological_order": order,
        },
        "node_results": [results_by_id[item] for item in sorted(results_by_id)],
        "probability_state": "NOT_COMPUTED",
        "uncertainty_state": "NOT_CALIBRATED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "prediction_state": "NOT_REQUESTED",
    }


def execute_belief_revision(
    projection: ReadinProjection,
    asset_entity_id: str,
    hypothesis_ids: Iterable[str] | None = None,
    *,
    revision_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
    deterministic_ids: bool = False,
) -> JsonObject:
    """Create one replay-verifiable belief revision event without computing probabilities."""

    if asset_entity_id not in projection.assets:
        raise BeliefRuntimeError(f"unknown tracked asset: {asset_entity_id}")
    snapshot = build_belief_snapshot(projection, asset_entity_id, hypothesis_ids)
    components = compute_belief_components(snapshot)
    selected_ids = _execution_ids(
        asset_entity_id,
        snapshot["input_ids"]["hypothesis_ids"],
        revision_id=revision_id,
        receipt_id=receipt_id,
        event_id=event_id,
        deterministic=deterministic_ids,
    )
    event_time = _timestamp(occurred_at)
    outcome_sha256 = canonical_sha256(components)
    receipt = {
        "id": selected_ids["receipt_id"],
        "asset_entity_id": asset_entity_id,
        "asset_state_version": projection.assets[asset_entity_id]["epistemic_state_version"],
        "input_snapshot_sha256": canonical_sha256(snapshot),
        **snapshot["input_ids"],
        "algorithm_id": BELIEF_ALGORITHM_ID,
        "implementation_sha256": belief_implementation_sha256(),
        "outcome_sha256": outcome_sha256,
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "probability_state": "NOT_COMPUTED",
        "prediction_state": "NOT_REQUESTED",
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    revision = {
        "id": selected_ids["revision_id"],
        "asset_entity_id": asset_entity_id,
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_belief_revision_completed(
        revision,
        event_id=selected_ids["event_id"],
        occurred_at=event_time,
    )


def _topological_order(
    hypotheses: Mapping[str, Mapping[str, Any]], edges: Iterable[Mapping[str, Any]]
) -> list[str]:
    indegree = {item: 0 for item in hypotheses}
    children: dict[str, set[str]] = {item: set() for item in hypotheses}
    for edge in edges:
        source = edge["source_hypothesis_id"]
        target = edge["target_hypothesis_id"]
        if source not in hypotheses or target not in hypotheses:
            raise BeliefRuntimeError("belief edge falls outside the selected graph")
        if target not in children[source]:
            children[source].add(target)
            indegree[target] += 1
    ready = sorted(item for item, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if len(order) != len(hypotheses):
        raise BeliefRuntimeError("belief graph contains a cycle")
    return order


def _categorical_state(support_units: set[str], challenge_units: set[str]) -> str:
    if len(support_units) > len(challenge_units):
        return "SUPPORT_LEADING"
    if len(challenge_units) > len(support_units):
        return "CHALLENGE_LEADING"
    if support_units or challenge_units:
        return "CONFLICTED"
    return "UNRESOLVED"


def _link_signal(role: str) -> str | None:
    if role in {"supports", "derives"}:
        return "SUPPORT"
    if role in {"challenges", "contradicts"}:
        return "CHALLENGE"
    return None


def _execution_ids(
    asset_entity_id: str,
    hypothesis_ids: Iterable[str],
    *,
    revision_id: str | UUID | None,
    receipt_id: str | UUID | None,
    event_id: str | UUID | None,
    deterministic: bool,
) -> JsonObject:
    values = {
        "revision_id": str(revision_id or uuid4()),
        "receipt_id": str(receipt_id or uuid4()),
        "event_id": str(event_id or uuid4()),
    }
    if deterministic:
        seed = f"readin:belief:{asset_entity_id}:{','.join(sorted(hypothesis_ids))}"
        provided = {
            "revision_id": revision_id,
            "receipt_id": receipt_id,
            "event_id": event_id,
        }
        for key in values:
            if provided[key] is None:
                values[key] = str(uuid5(NAMESPACE_URL, f"{seed}:{key}"))
    return values


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BeliefRuntimeError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
