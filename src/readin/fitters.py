"""Deterministic, local-only reference fitters for the bounded Phase 4 runtime."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from statistics import median
from typing import TYPE_CHECKING, Any
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from readin.events import (
    create_fitter_registered,
    create_fitter_run_completed,
)

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]


class FitterRuntimeError(ValueError):
    """Raised when a reference fitter cannot execute under the bounded runtime contract."""


REFERENCE_FITTER_SPECS: dict[str, JsonObject] = {
    "BAYESIAN": {
        "name": "Dependency-aware claim support diagnostic",
        "algorithm_id": "readin.reference.bayesian.dependency-aware-claim-support.v0.1",
        "target_metric": "DEPENDENCY_AWARE_CLAIM_SUPPORT",
        "minimum_observation_count": 1,
        "minimum_claim_count": 1,
        "maximum_claim_count": 1,
        "requires_relations": False,
        "allows_hindsight_lens": True,
        "requires_dependency_groups": True,
        "assumptions": [
            "Uniform Beta(1,1) diagnostic prior",
            "Evidence links in one dependency group count as one support or challenge unit",
            "The posterior mean is a diagnostic index, not a probability that a claim is true",
        ],
    },
    "GRAPH": {
        "name": "Bounded relation topology diagnostic",
        "algorithm_id": "readin.reference.graph.relation-topology.v0.1",
        "target_metric": "RELATION_TOPOLOGY",
        "minimum_observation_count": 1,
        "minimum_claim_count": 1,
        "maximum_claim_count": None,
        "requires_relations": True,
        "allows_hindsight_lens": True,
        "requires_dependency_groups": False,
        "assumptions": [
            "Relations are directed descriptive edges within the selected query aperture",
            "Topology does not establish influence, causality, importance, or completeness",
        ],
    },
    "TEMPORAL": {
        "name": "Bounded observation cadence diagnostic",
        "algorithm_id": "readin.reference.temporal.observation-cadence.v0.1",
        "target_metric": "OBSERVATION_CADENCE",
        "minimum_observation_count": 2,
        "minimum_claim_count": 0,
        "maximum_claim_count": None,
        "requires_relations": False,
        "allows_hindsight_lens": False,
        "requires_dependency_groups": False,
        "assumptions": [
            "Cadence uses admitted observation timestamps inside the selected query aperture",
            "Cadence does not infer trend, latent state, regime, trajectory, or forecast",
        ],
    },
}

REFERENCE_INVALID_CONDITIONS = [
    "Any use outside the closed local diagnostic runtime",
    "Any interpretation as empirical model validation or world-state truth",
    "Any prediction, causal, targeting, intervention, or action-authority use",
]


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def reference_implementation_sha256(fitter_class: str) -> str:
    spec = reference_fitter_spec(fitter_class)
    implementation = {
        "BAYESIAN": _bayesian_estimate,
        "GRAPH": _graph_estimate,
        "TEMPORAL": _temporal_estimate,
    }[fitter_class.upper()]
    return canonical_sha256(
        {
            "algorithm_id": spec["algorithm_id"],
            "algorithm_source": inspect.getsource(implementation),
            "admissibility_source": inspect.getsource(evaluate_reference_admissibility),
            "input_binding_source": inspect.getsource(_input_ids),
        }
    )


def reference_fitter_spec(fitter_class: str) -> JsonObject:
    normalized = fitter_class.upper()
    if normalized not in REFERENCE_FITTER_SPECS:
        raise FitterRuntimeError(f"unsupported reference fitter class: {fitter_class}")
    return REFERENCE_FITTER_SPECS[normalized]


def create_reference_fitter_registration(
    fitter_class: str,
    *,
    fitter_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    normalized = fitter_class.upper()
    spec = reference_fitter_spec(normalized)
    return create_fitter_registered(
        spec["name"],
        normalized,
        reference_implementation_sha256(normalized),
        spec["target_metric"],
        minimum_observation_count=spec["minimum_observation_count"],
        minimum_claim_count=spec["minimum_claim_count"],
        maximum_claim_count=spec["maximum_claim_count"],
        requires_relations=spec["requires_relations"],
        allows_hindsight_lens=spec["allows_hindsight_lens"],
        requires_dependency_groups=spec["requires_dependency_groups"],
        invalid_conditions=REFERENCE_INVALID_CONDITIONS,
        fitter_id=fitter_id,
        event_id=event_id,
        occurred_at=occurred_at,
    )


def execute_reference_fitter_group(
    projection: ReadinProjection,
    query_plan_id: str,
    fitter_ids: Iterable[str],
    *,
    run_group_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
    deterministic_ids: bool = False,
) -> list[JsonObject]:
    selected_fitter_ids = list(fitter_ids)
    if not selected_fitter_ids:
        raise FitterRuntimeError("at least one fitter is required")
    if len(selected_fitter_ids) != len(set(selected_fitter_ids)):
        raise FitterRuntimeError("a fitter may appear only once in a run group")

    query_result = projection.execute_cartographic_query(query_plan_id)
    asset_id = query_result["query_plan"]["asset_entity_id"]
    input_state_version = projection.assets[asset_id]["epistemic_state_version"]
    input_snapshot_sha256 = canonical_sha256(query_result)
    selected_run_group_id = str(run_group_id or uuid4())
    event_time = _timestamp(occurred_at)

    descriptors: list[JsonObject] = []
    for fitter_id in selected_fitter_ids:
        if fitter_id not in projection.fitters:
            raise FitterRuntimeError(f"unknown registered fitter: {fitter_id}")
        descriptor = projection.fitters[fitter_id]
        validate_reference_descriptor(descriptor)
        descriptors.append(descriptor)
    descriptors.sort(key=lambda item: (item["fitter_class"], item["id"]))

    events: list[JsonObject] = []
    for descriptor in descriptors:
        ids = _run_ids(
            selected_run_group_id,
            descriptor["id"],
            deterministic=deterministic_ids,
        )
        event = _execute_one(
            query_result,
            descriptor,
            run_group_id=selected_run_group_id,
            input_state_version=input_state_version,
            input_snapshot_sha256=input_snapshot_sha256,
            ids=ids,
            event_time=event_time,
            requested_fitter_ids=sorted(selected_fitter_ids),
        )
        events.append(event)
    return events


def validate_reference_descriptor(descriptor: Mapping[str, Any]) -> None:
    fitter_class = descriptor["fitter_class"]
    spec = reference_fitter_spec(fitter_class)
    expected = {
        "name": spec["name"],
        "target_metric": spec["target_metric"],
        "implementation_sha256": reference_implementation_sha256(fitter_class),
        "admissibility_rule": {
            "minimum_observation_count": spec["minimum_observation_count"],
            "minimum_claim_count": spec["minimum_claim_count"],
            "maximum_claim_count": spec["maximum_claim_count"],
            "requires_relations": spec["requires_relations"],
            "allows_hindsight_lens": spec["allows_hindsight_lens"],
            "requires_dependency_groups": spec["requires_dependency_groups"],
        },
    }
    mismatched = [key for key, value in expected.items() if descriptor[key] != value]
    if mismatched:
        raise FitterRuntimeError(
            f"registered fitter does not match the reference implementation: {mismatched}"
        )


def _execute_one(
    query_result: JsonObject,
    descriptor: JsonObject,
    *,
    run_group_id: str,
    input_state_version: str,
    input_snapshot_sha256: str,
    ids: Mapping[str, str],
    event_time: str,
    requested_fitter_ids: list[str],
) -> JsonObject:
    admissibility = evaluate_reference_admissibility(descriptor, query_result)
    outcome = {
        "ADMISSIBLE": "FIT",
        "INADMISSIBLE": "ABSTAINED",
        "INVALID": "INVALID",
    }[admissibility["status"]]
    assumptions = list(REFERENCE_FITTER_SPECS[descriptor["fitter_class"]]["assumptions"])
    fit_result = None
    if outcome == "FIT":
        fit_result = _fit_result(
            descriptor,
            query_result,
            result_id=ids["result_id"],
            receipt_id=ids["receipt_id"],
            assumptions=assumptions,
        )

    outcome_sha256 = canonical_sha256(
        {"outcome": outcome, "admissibility": admissibility, "fit_result": fit_result}
    )
    input_ids = _input_ids(query_result)
    receipt = {
        "id": ids["receipt_id"],
        "run_group_id": run_group_id,
        "query_plan_id": query_result["query_plan"]["id"],
        "asset_state_version": input_state_version,
        "input_snapshot_sha256": input_snapshot_sha256,
        **input_ids,
        "excluded_observation_ids": list(
            query_result["aperture"]["excluded_asset_observation_ids"]
        ),
        "requested_fitter_ids": requested_fitter_ids,
        "fitter_id": descriptor["id"],
        "fitter_version": descriptor["version"],
        "implementation_sha256": descriptor["implementation_sha256"],
        "assumptions": assumptions,
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "consensus_policy": "PRESERVE_DISAGREEMENT",
        "prediction_state": "NOT_REQUESTED",
        "outcome_sha256": outcome_sha256,
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    fitter_run = {
        "id": ids["run_id"],
        "run_group_id": run_group_id,
        "query_plan_id": query_result["query_plan"]["id"],
        "fitter_id": descriptor["id"],
        "outcome": outcome,
        "admissibility": admissibility,
        "fit_result": fit_result,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_fitter_run_completed(
        fitter_run,
        event_id=ids["event_id"],
        occurred_at=event_time,
    )


def evaluate_reference_admissibility(
    descriptor: JsonObject, query_result: JsonObject
) -> JsonObject:
    rule = descriptor["admissibility_rule"]
    counts = {
        "minimum_observation_count": len(query_result["observations"]),
        "minimum_claim_count": len(query_result["claims"]),
    }
    evaluated_conditions = [
        {
            "condition": f"observation_count >= {rule['minimum_observation_count']}",
            "satisfied": counts["minimum_observation_count"] >= rule["minimum_observation_count"],
        },
        {
            "condition": f"claim_count >= {rule['minimum_claim_count']}",
            "satisfied": counts["minimum_claim_count"] >= rule["minimum_claim_count"],
        },
        {
            "condition": "claim_count is within the fitter maximum when declared",
            "satisfied": rule["maximum_claim_count"] is None
            or counts["minimum_claim_count"] <= rule["maximum_claim_count"],
        },
        {
            "condition": "relation_count >= 1 when relations are required",
            "satisfied": not rule["requires_relations"] or bool(query_result["relations"]),
        },
        {
            "condition": "hindsight query lens is allowed by the fitter",
            "satisfied": rule["allows_hindsight_lens"]
            or not query_result["query_lens"]["hindsight_in_query_lens"],
        },
        {
            "condition": "all claim evidence links have declared dependency groups",
            "satisfied": not rule["requires_dependency_groups"]
            or all(
                link["dependency_group"] is not None
                for claim in query_result["claims"]
                for link in claim["evidence_links"]
            ),
        },
    ]
    reasons = [item["condition"] for item in evaluated_conditions if not item["satisfied"]]
    hindsight_invalid = not evaluated_conditions[-2]["satisfied"]
    return {
        "status": (
            "INVALID" if hindsight_invalid else "ADMISSIBLE" if not reasons else "INADMISSIBLE"
        ),
        "reasons": reasons,
        "evaluated_conditions": evaluated_conditions,
    }


def _fit_result(
    descriptor: JsonObject,
    query_result: JsonObject,
    *,
    result_id: str,
    receipt_id: str,
    assumptions: list[str],
) -> JsonObject:
    components = reference_fit_components(descriptor, query_result)

    return {
        "id": result_id,
        "fitter_id": descriptor["id"],
        "fitter_version": descriptor["version"],
        "query_plan_id": query_result["query_plan"]["id"],
        "asset_entity_id": query_result["query_plan"]["asset_entity_id"],
        "target_metric": descriptor["target_metric"],
        "estimate": components["estimate"],
        "distribution": components["distribution"],
        **_input_ids(query_result),
        "assumptions": assumptions,
        "residuals": {"status": "NOT_AVAILABLE", "values": {}},
        "uncertainty": {"status": "NOT_CALIBRATED", "interval": None},
        "validity": {
            "status": "NOT_ESTABLISHED",
            "domain": "CLOSED_SYNTHETIC_LEDGER_ONLY",
            "boundary_proximity": None,
            "invalid_conditions": list(descriptor["declared_validity"]["invalid_conditions"]),
        },
        "execution_receipt_id": receipt_id,
    }


def reference_fit_components(descriptor: JsonObject, query_result: JsonObject) -> JsonObject:
    fitter_class = descriptor["fitter_class"]
    if fitter_class == "BAYESIAN":
        estimate, distribution = _bayesian_estimate(query_result)
    elif fitter_class == "GRAPH":
        estimate, distribution = _graph_estimate(query_result), None
    elif fitter_class == "TEMPORAL":
        estimate, distribution = _temporal_estimate(query_result), None
    else:  # pragma: no cover - descriptor validation closes this path
        raise FitterRuntimeError(f"unsupported fitter class: {fitter_class}")
    return {
        "estimate": estimate,
        "distribution": distribution,
        "assumptions": list(REFERENCE_FITTER_SPECS[fitter_class]["assumptions"]),
    }


def _bayesian_estimate(query_result: JsonObject) -> tuple[JsonObject, JsonObject]:
    support_units: set[str] = set()
    challenge_units: set[str] = set()
    dependent_source_count = 0
    dependency_groups: set[str] = set()
    for claim_view in query_result["claims"]:
        for link in claim_view["evidence_links"]:
            group = link["dependency_group"]
            unit = f"dependency:{group}" if group else f"ungrouped:{link['evidence_id']}"
            if group:
                dependency_groups.add(group)
            if link["role"] in {"supports", "derives"}:
                if unit in support_units:
                    dependent_source_count += 1
                support_units.add(unit)
            elif link["role"] in {"challenges", "contradicts"}:
                if unit in challenge_units:
                    dependent_source_count += 1
                challenge_units.add(unit)
    alpha = 1.0 + len(support_units)
    beta = 1.0 + len(challenge_units)
    estimate = {
        "kind": "DEPENDENCY_AWARE_CLAIM_SUPPORT",
        "posterior_mean": alpha / (alpha + beta),
        "alpha": alpha,
        "beta": beta,
        "support_units": len(support_units),
        "challenge_units": len(challenge_units),
        "conflicted_unit_count": len(support_units.intersection(challenge_units)),
        "dependent_source_count": dependent_source_count,
        "independence_status": (
            "DEPENDENT_EVIDENCE_PRESENT" if dependency_groups else "INDEPENDENCE_NOT_ESTABLISHED"
        ),
    }
    distribution = {
        "family": "BETA_DIAGNOSTIC",
        "alpha": alpha,
        "beta": beta,
        "interpretation": "DIAGNOSTIC_INDEX_NOT_TRUTH_PROBABILITY",
    }
    return estimate, distribution


def _graph_estimate(query_result: JsonObject) -> JsonObject:
    entity_count = len(query_result["entities"])
    relation_count = len(query_result["relations"])
    unique_directed_edges = {
        (relation["source_entity"], relation["target_entity"])
        for relation in query_result["relations"]
    }
    possible_directed_edges = entity_count * (entity_count - 1)
    asset_id = query_result["query_plan"]["asset_entity_id"]
    return {
        "kind": "RELATION_TOPOLOGY",
        "directed_density": (
            len(unique_directed_edges) / possible_directed_edges if possible_directed_edges else 0.0
        ),
        "entity_count": entity_count,
        "relation_count": relation_count,
        "asset_out_degree": sum(
            relation["source_entity"] == asset_id for relation in query_result["relations"]
        ),
        "dependency_edge_count": len(query_result["evidence_dependencies"]),
    }


def _temporal_estimate(query_result: JsonObject) -> JsonObject:
    observed_times = sorted(
        _parse_timestamp(observation["observed_at"]) for observation in query_result["observations"]
    )
    gaps = [
        (right - left).total_seconds()
        for left, right in zip(observed_times, observed_times[1:], strict=False)
    ]
    return {
        "kind": "OBSERVATION_CADENCE",
        "observation_count": len(observed_times),
        "distinct_timestamp_count": len(set(observed_times)),
        "span_seconds": (observed_times[-1] - observed_times[0]).total_seconds(),
        "median_gap_seconds": float(median(gaps)),
    }


def _input_ids(query_result: JsonObject) -> JsonObject:
    return {
        "input_observation_ids": sorted(item["id"] for item in query_result["observations"]),
        "input_claim_ids": sorted(item["claim"]["id"] for item in query_result["claims"]),
        "input_relation_ids": sorted(item["id"] for item in query_result["relations"]),
        "input_evidence_manifest_ids": sorted(
            item["id"] for item in query_result["evidence_manifests"]
        ),
    }


def _run_ids(run_group_id: str, fitter_id: str, *, deterministic: bool) -> JsonObject:
    if not deterministic:
        return {
            "run_id": str(uuid4()),
            "result_id": str(uuid4()),
            "receipt_id": str(uuid4()),
            "event_id": str(uuid4()),
        }
    return {
        key: str(uuid5(NAMESPACE_URL, f"readin:{run_group_id}:{fitter_id}:{key}"))
        for key in ("run_id", "result_id", "receipt_id", "event_id")
    }


def _timestamp(value: str | datetime | None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = _parse_timestamp(value)
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FitterRuntimeError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
