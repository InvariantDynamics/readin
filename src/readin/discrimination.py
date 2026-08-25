"""Deterministic Phase 7 discriminating-observation planning without collection."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from itertools import combinations
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from readin.events import (
    create_collection_discrimination_plan_created,
    create_collection_discrimination_run_completed,
)
from readin.fitters import canonical_sha256

if TYPE_CHECKING:
    from readin.projection import ReadinProjection

JsonObject = dict[str, Any]

DISCRIMINATION_ALGORITHM_ID = "readin.reference.collection.structural-discrimination-ordinal.v0.1"
RANKING_POLICY = "STRUCTURAL_DISCRIMINATION_ORDINAL_V0_1"


class DiscriminationRuntimeError(ValueError):
    """Raised when a bounded discrimination plan cannot be created or executed."""


def _timestamp(value: str | datetime | None = None) -> str:
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        parsed = value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DiscriminationRuntimeError("timestamps must include a UTC offset")
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def discrimination_implementation_sha256() -> str:
    """Bind receipts to the exact deterministic planning implementation."""

    return canonical_sha256(
        {
            "algorithm_id": DISCRIMINATION_ALGORITHM_ID,
            "snapshot_source": inspect.getsource(build_discrimination_snapshot),
            "components_source": inspect.getsource(compute_discrimination_components),
            "candidate_source": inspect.getsource(_score_candidate),
            "effect_source": inspect.getsource(_effect_separation_units),
        }
    )


def create_bounded_discrimination_plan(
    projection: ReadinProjection,
    asset_entity_id: str,
    name: str,
    ambiguity_statement: str,
    belief_revision_id: str,
    query_plan_id: str,
    target_hypothesis_ids: Iterable[str],
    candidates: Iterable[Mapping[str, Any]],
    *,
    plan_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Create a manual, local-only observation discrimination plan."""

    if asset_entity_id not in projection.assets:
        raise DiscriminationRuntimeError(f"unknown tracked asset: {asset_entity_id}")
    if belief_revision_id not in projection.belief_revisions:
        raise DiscriminationRuntimeError(f"unknown belief revision: {belief_revision_id}")
    if query_plan_id not in projection.cartographic_query_plans:
        raise DiscriminationRuntimeError(f"unknown cartographic query plan: {query_plan_id}")

    hypothesis_ids = list(target_hypothesis_ids)
    if len(hypothesis_ids) != len(set(hypothesis_ids)):
        raise DiscriminationRuntimeError("target hypotheses must be unique")
    hypothesis_ids.sort()
    if len(hypothesis_ids) < 2:
        raise DiscriminationRuntimeError("at least two target hypotheses are required")

    normalized_candidates = [
        _normalize_candidate(projection, item, hypothesis_ids) for item in candidates
    ]
    if not normalized_candidates:
        raise DiscriminationRuntimeError("at least one observation candidate is required")
    event_time = _timestamp(occurred_at)
    plan = {
        "id": str(plan_id or uuid4()),
        "asset_entity_id": asset_entity_id,
        "name": name,
        "ambiguity_statement": ambiguity_statement,
        "initial_state_version": projection.assets[asset_entity_id]["epistemic_state_version"],
        "belief_revision_id": belief_revision_id,
        "query_plan_id": query_plan_id,
        "target_hypothesis_ids": hypothesis_ids,
        "candidates": normalized_candidates,
        "ranking_policy": RANKING_POLICY,
        "policy_context": {
            "source_policy": "PUBLIC_LICENSED_OWNED_OR_AUTHORIZED_ONLY",
            "human_entity_policy": "AUTHORIZED_SOURCES_ONLY",
            "collection_authority": "NOT_GRANTED",
        },
        "collection_state": "NOT_STARTED",
        "execution_state": "PLANNED_LOCAL_ONLY",
        "created_at": event_time,
    }
    return create_collection_discrimination_plan_created(
        plan,
        event_id=event_id,
        occurred_at=event_time,
    )


def _normalize_candidate(
    projection: ReadinProjection,
    candidate: Mapping[str, Any],
    hypothesis_ids: list[str],
) -> JsonObject:
    candidate_id = str(candidate.get("id") or uuid4())
    frame_id = str(candidate["observer_frame_id"])
    if frame_id not in projection.frames:
        raise DiscriminationRuntimeError(f"unknown observer frame: {frame_id}")
    outcomes = []
    for outcome in candidate["expected_outcomes"]:
        effects = sorted(
            (
                {
                    "hypothesis_id": str(effect["hypothesis_id"]),
                    "effect": effect["effect"],
                }
                for effect in outcome["hypothesis_effects"]
            ),
            key=lambda item: item["hypothesis_id"],
        )
        outcomes.append(
            {
                "label": outcome["label"],
                "hypothesis_effects": effects,
                "assumption_state": "USER_SUPPLIED_NOT_VALIDATED",
            }
        )
    return {
        "id": candidate_id,
        "name": candidate["name"],
        "observer_frame_id": frame_id,
        "observation_type": candidate["observation_type"],
        "question": candidate["question"],
        "declared_blind_region_targets": sorted(
            set(candidate.get("declared_blind_region_targets", []))
        ),
        "expected_outcomes": outcomes,
        "effort": candidate.get("effort", "NOT_EVALUATED"),
        "access_scope_snapshot": projection.frames[frame_id]["access_projection"]["scope"],
        "feasibility_state": "USER_SUPPLIED_NOT_VALIDATED",
        "source_independence_state": "NOT_ESTABLISHED",
        "acquisition_state": "NOT_STARTED",
        "target_hypothesis_ids": hypothesis_ids,
    }


def build_discrimination_snapshot(projection: ReadinProjection, plan_id: str) -> JsonObject:
    """Bind one plan to its immutable belief and cartographic ambiguity context."""

    if plan_id not in projection.discrimination_plans:
        raise DiscriminationRuntimeError(f"unknown discrimination plan: {plan_id}")
    plan = deepcopy(projection.discrimination_plans[plan_id])
    belief_revision = deepcopy(projection.belief_revisions[plan["belief_revision_id"]])
    query_result = projection.execute_cartographic_query(plan["query_plan_id"])
    return {
        "plan": plan,
        "belief_revision": belief_revision,
        "query_context": {
            "query_plan_id": plan["query_plan_id"],
            "known_blind_regions": deepcopy(query_result["blind_regions"]["known"]),
            "uncharacterized_surface_ids": deepcopy(
                query_result["blind_regions"]["uncharacterized_surface_ids"]
            ),
            "coverage_state": query_result["aperture"]["coverage_state"],
            "completeness_claim": query_result["aperture"]["completeness_claim"],
            "query_result_sha256": canonical_sha256(query_result),
        },
    }


def _effect_separation_units(left: str, right: str) -> int:
    if "UNKNOWN" in {left, right} or left == right:
        return 0
    directional = {"SUPPORTS_HYPOTHESIS", "CHALLENGES_HYPOTHESIS"}
    if {left, right} == directional:
        return 2
    if (left in directional) != (right in directional):
        return 1
    return 0


def _score_candidate(candidate: Mapping[str, Any]) -> JsonObject:
    target_ids = candidate["target_hypothesis_ids"]
    total_separation = 0
    discriminating_outcomes = 0
    pair_count = 0
    for outcome in candidate["expected_outcomes"]:
        effects = {item["hypothesis_id"]: item["effect"] for item in outcome["hypothesis_effects"]}
        outcome_units = 0
        for left_id, right_id in combinations(target_ids, 2):
            units = _effect_separation_units(effects[left_id], effects[right_id])
            outcome_units += units
            pair_count += int(units > 0)
        total_separation += outcome_units
        discriminating_outcomes += int(outcome_units > 0)
    return {
        "candidate_id": candidate["id"],
        "rank": None,
        "tie_state": "NOT_RANKED",
        "discrimination_state": (
            "DISCRIMINATING" if total_separation > 0 else "NON_DISCRIMINATING"
        ),
        "directional_separation_units": total_separation,
        "distinguished_hypothesis_pair_units": pair_count,
        "discriminating_outcome_count": discriminating_outcomes,
        "blind_region_alignment_count": len(candidate["declared_blind_region_targets"]),
        "source_independence_state": candidate["source_independence_state"],
        "feasibility_state": candidate["feasibility_state"],
        "acquisition_state": candidate["acquisition_state"],
        "interpretation": "STRUCTURAL_ORDINAL_HEURISTIC_NOT_EXPECTED_INFORMATION_GAIN",
    }


def compute_discrimination_components(snapshot: Mapping[str, Any]) -> JsonObject:
    """Rank structurally discriminating candidates while retaining ties and abstention."""

    scores = [_score_candidate(candidate) for candidate in snapshot["plan"]["candidates"]]
    discriminating = [item for item in scores if item["discrimination_state"] == "DISCRIMINATING"]
    rank_keys = sorted(
        {
            (
                item["directional_separation_units"],
                item["distinguished_hypothesis_pair_units"],
                item["discriminating_outcome_count"],
                item["blind_region_alignment_count"],
            )
            for item in discriminating
        },
        reverse=True,
    )
    key_to_rank = {key: index + 1 for index, key in enumerate(rank_keys)}
    rank_counts: dict[int, int] = {}
    for item in discriminating:
        key = (
            item["directional_separation_units"],
            item["distinguished_hypothesis_pair_units"],
            item["discriminating_outcome_count"],
            item["blind_region_alignment_count"],
        )
        item["rank"] = key_to_rank[key]
        rank_counts[item["rank"]] = rank_counts.get(item["rank"], 0) + 1
    for item in discriminating:
        item["tie_state"] = "TIED_AT_RANK" if rank_counts[item["rank"]] > 1 else "UNIQUE_AT_RANK"
    scores.sort(
        key=lambda item: (
            item["rank"] is None,
            item["rank"] or 10_000,
            item["candidate_id"],
        )
    )
    top_candidate_ids = sorted(item["candidate_id"] for item in scores if item["rank"] == 1)
    return {
        "recommendation_state": (
            "RANKED_STRUCTURAL_CANDIDATES"
            if top_candidate_ids
            else "ABSTAINED_NO_DISCRIMINATING_CANDIDATE"
        ),
        "candidate_scores": scores,
        "top_candidate_ids": top_candidate_ids,
        "ranking_policy": RANKING_POLICY,
        "collection_state": "NOT_STARTED",
        "acquisition_state": "NOT_ATTEMPTED",
        "expected_information_gain_state": "NOT_COMPUTED",
        "probability_state": "NOT_COMPUTED",
        "empirical_validity_state": "NOT_ESTABLISHED",
    }


def execute_discrimination_plan(
    projection: ReadinProjection,
    plan_id: str,
    *,
    run_id: str | UUID | None = None,
    receipt_id: str | UUID | None = None,
    event_id: str | UUID | None = None,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Execute one local ranking pass without acquiring any observation."""

    snapshot = build_discrimination_snapshot(projection, plan_id)
    plan = snapshot["plan"]
    components = compute_discrimination_components(snapshot)
    event_time = _timestamp(occurred_at)
    selected_receipt_id = str(receipt_id or uuid4())
    receipt = {
        "id": selected_receipt_id,
        "plan_id": plan_id,
        "asset_entity_id": plan["asset_entity_id"],
        "asset_state_version": projection.assets[plan["asset_entity_id"]][
            "epistemic_state_version"
        ],
        "plan_sha256": canonical_sha256(plan),
        "belief_revision_id": plan["belief_revision_id"],
        "belief_revision_sha256": canonical_sha256(snapshot["belief_revision"]),
        "query_plan_id": plan["query_plan_id"],
        "query_result_sha256": snapshot["query_context"]["query_result_sha256"],
        "candidate_ids": sorted(item["id"] for item in plan["candidates"]),
        "target_hypothesis_ids": deepcopy(plan["target_hypothesis_ids"]),
        "algorithm_id": DISCRIMINATION_ALGORITHM_ID,
        "implementation_sha256": discrimination_implementation_sha256(),
        "outcome_sha256": canonical_sha256(components),
        "runtime": "LOCAL_DETERMINISTIC_REFERENCE",
        "network_access": False,
        "collection_state": "NOT_STARTED",
        "source_independence_state": "NOT_ESTABLISHED",
        "executed_at": event_time,
        "authority_state": "NO_AUTHORITY",
    }
    run = {
        "id": str(run_id or uuid4()),
        "plan_id": plan_id,
        "asset_entity_id": plan["asset_entity_id"],
        **components,
        "execution_receipt": receipt,
        "recorded_at": event_time,
    }
    return create_collection_discrimination_run_completed(
        run,
        event_id=event_id,
        occurred_at=event_time,
    )
