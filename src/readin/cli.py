"""Command-line interface for the local READIN Phase 0 through Phase 6 runtime."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from readin.belief import BeliefRuntimeError, execute_belief_revision
from readin.contracts import ContractViolation
from readin.events import (
    create_belief_edge_created,
    create_cartographic_query_planned,
    create_cartographic_surface_registered,
    create_claim_created,
    create_entity_created,
    create_evidence_dependency_declared,
    create_evidence_linked,
    create_evidence_manifested,
    create_hypothesis_created,
    create_observation_admitted,
    create_observer_frame_registered,
    create_relation_created,
    create_resolution_candidate_assessed,
    create_resolution_candidate_recorded,
    create_tracking_started,
)
from readin.fitters import (
    FitterRuntimeError,
    create_reference_fitter_registration,
    execute_reference_fitter_group,
)
from readin.projection import ProjectionError
from readin.scenarios import (
    ScenarioRuntimeError,
    create_bounded_scenario,
    execute_scenario,
)
from readin.store import EventLedger, LedgerError
from readin.workbench import (
    WorkbenchError,
    build_workbench_snapshot,
    serve_workbench,
)

ACCESS_POLICIES = ("PUBLIC", "LICENSED", "USER_OWNED", "OTHERWISE_AUTHORIZED")
RECONSTRUCTION_MODES = ("AS_KNOWN_THEN", "AS_RECONSTRUCTED_NOW")


def _json_object(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
    return parsed


def _json_scalar(value: str) -> str | int | float | bool | None:
    parsed = json.loads(value)
    if isinstance(parsed, (dict, list)):
        raise ValueError("expected a JSON scalar")
    return parsed


def _emit(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _ledger(args: argparse.Namespace) -> EventLedger:
    return EventLedger(Path(args.ledger))


def _add_ledger_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ledger", required=True, help="Path to the local JSONL event ledger")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="readin",
        description="READIN local tracked-asset and inspectable Array runtime",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create an empty local event ledger")
    _add_ledger_argument(init_parser)

    entity_parser = subparsers.add_parser(
        "create-entity", help="Create and optionally track an entity"
    )
    _add_ledger_argument(entity_parser)
    entity_parser.add_argument("--name", required=True)
    entity_parser.add_argument("--type", required=True, dest="entity_type")
    entity_parser.add_argument("--alias", action="append", default=[])
    entity_parser.add_argument("--attributes-json", default="{}")
    entity_parser.add_argument("--entity-id")
    entity_parser.add_argument("--no-track", action="store_true")
    entity_parser.add_argument("--priority", type=float, default=0.5)
    entity_parser.add_argument("--scope", action="append", default=[])

    track_parser = subparsers.add_parser("start-tracking", help="Start tracking an existing entity")
    _add_ledger_argument(track_parser)
    track_parser.add_argument("--entity", required=True)
    track_parser.add_argument("--priority", type=float, default=0.5)
    track_parser.add_argument("--scope", action="append", default=[])

    frame_parser = subparsers.add_parser("register-frame", help="Register an observer frame")
    _add_ledger_argument(frame_parser)
    frame_parser.add_argument("--name", required=True)
    frame_parser.add_argument("--class", required=True, dest="frame_class")
    frame_parser.add_argument("--frame-id")
    frame_parser.add_argument("--access-policy", choices=ACCESS_POLICIES, default="PUBLIC")
    frame_parser.add_argument("--access-description", default="Publicly accessible source")
    frame_parser.add_argument("--blind-region", action="append", default=[])
    frame_parser.add_argument("--validity-condition", action="append", default=[])

    evidence_parser = subparsers.add_parser(
        "manifest-evidence", help="Register immutable evidence identity and source policy"
    )
    _add_ledger_argument(evidence_parser)
    evidence_parser.add_argument("--sha256", required=True)
    evidence_parser.add_argument("--media-type", required=True)
    evidence_parser.add_argument("--size", required=True, type=int)
    evidence_parser.add_argument("--source-label", required=True)
    evidence_parser.add_argument("--source-uri")
    evidence_parser.add_argument("--license")
    evidence_parser.add_argument("--access-policy", choices=ACCESS_POLICIES, default="PUBLIC")
    evidence_parser.add_argument("--artifact-id")

    observation_parser = subparsers.add_parser(
        "admit-observation", help="Admit an immutable observation for a tracked asset"
    )
    _add_ledger_argument(observation_parser)
    observation_parser.add_argument("--asset", required=True, action="append")
    observation_parser.add_argument("--frame", required=True)
    observation_parser.add_argument("--artifact", required=True)
    observation_parser.add_argument("--type", required=True, dest="observation_type")
    observation_parser.add_argument("--payload-json", required=True)
    observation_parser.add_argument("--observed-at", required=True)
    observation_parser.add_argument("--source-uri")
    observation_parser.add_argument("--source-policy", choices=ACCESS_POLICIES, default="PUBLIC")
    observation_parser.add_argument("--missingness", default="OBSERVED")
    observation_parser.add_argument("--uncertainty-json", default="{}")
    observation_parser.add_argument("--observation-id")
    observation_parser.add_argument("--supersedes")

    dependency_parser = subparsers.add_parser(
        "declare-dependency", help="Declare provenance-preserving evidence ancestry"
    )
    _add_ledger_argument(dependency_parser)
    dependency_parser.add_argument("--group", required=True)
    dependency_parser.add_argument("--ancestor", required=True)
    dependency_parser.add_argument("--descendant", required=True)
    dependency_parser.add_argument(
        "--relationship",
        required=True,
        choices=(
            "DERIVED_FROM",
            "CITES",
            "SUMMARIZES",
            "REPRODUCES",
            "TRANSFORMS",
            "UNKNOWN_SHARED_ANCESTRY",
        ),
    )
    dependency_parser.add_argument(
        "--verification-status",
        choices=("ASSERTED_NOT_VERIFIED", "VERIFIED_FROM_MANIFEST"),
        default="ASSERTED_NOT_VERIFIED",
    )
    dependency_parser.add_argument(
        "--basis-method",
        choices=(
            "MANIFEST_TRANSFORMATION",
            "EXPLICIT_CITATION",
            "CONTENT_LINEAGE",
            "SOURCE_DISCLOSURE",
            "USER_ASSERTED",
        ),
        default="USER_ASSERTED",
    )
    dependency_parser.add_argument(
        "--basis-notes", default="Dependency asserted by the recording user"
    )
    dependency_parser.add_argument("--dependency-id")

    claim_parser = subparsers.add_parser(
        "create-claim", help="Create an unresolved claim derived from admitted observations"
    )
    _add_ledger_argument(claim_parser)
    claim_parser.add_argument("--subject", required=True)
    claim_parser.add_argument("--predicate", required=True)
    claim_object = claim_parser.add_mutually_exclusive_group(required=True)
    claim_object.add_argument("--object-entity")
    claim_object.add_argument("--object-literal-json")
    claim_parser.add_argument("--derived-from", required=True, action="append")
    claim_parser.add_argument(
        "--modality",
        choices=(
            "asserted",
            "inferred",
            "predicted",
            "hypothetical",
            "counterfactual",
            "disputed",
        ),
        default="asserted",
    )
    claim_parser.add_argument("--valid-from")
    claim_parser.add_argument("--valid-until")
    claim_parser.add_argument("--invalidation-condition", action="append", default=[])
    claim_parser.add_argument("--claim-id")

    link_parser = subparsers.add_parser(
        "link-evidence", help="Attach evidence, polarity, warrant, and appraisal to a claim"
    )
    _add_ledger_argument(link_parser)
    link_parser.add_argument("--evidence", required=True)
    link_parser.add_argument("--claim", required=True)
    link_parser.add_argument(
        "--role",
        required=True,
        choices=(
            "supports",
            "challenges",
            "contextualizes",
            "constrains",
            "derives",
            "contradicts",
        ),
    )
    link_parser.add_argument("--dependency-group")
    link_parser.add_argument("--warrant-statement")
    link_parser.add_argument(
        "--warrant-basis",
        choices=(
            "DIRECT_SOURCE_REPORT",
            "DOCUMENTARY_RECORD",
            "INFERENTIAL_CHAIN",
            "CONTEXTUAL_CONSTRAINT",
        ),
    )
    link_parser.add_argument(
        "--appraisal-status", choices=("NOT_APPRAISED", "APPRAISED"), default="NOT_APPRAISED"
    )
    link_parser.add_argument("--appraisal-method")
    link_parser.add_argument("--appraisal-notes")
    link_parser.add_argument("--strength", choices=("WEAK", "MODERATE", "STRONG"))
    link_parser.add_argument("--link-id")

    relation_parser = subparsers.add_parser(
        "create-relation", help="Create a typed temporal relation backed by claims"
    )
    _add_ledger_argument(relation_parser)
    relation_parser.add_argument("--source", required=True)
    relation_parser.add_argument("--type", required=True, dest="relation_type")
    relation_parser.add_argument("--target", required=True)
    relation_parser.add_argument("--claim", required=True, action="append")
    relation_parser.add_argument(
        "--semantics",
        choices=("DESCRIPTIVE", "ASSOCIATION", "CAUSAL_HYPOTHESIS"),
        default="DESCRIPTIVE",
    )
    relation_parser.add_argument("--valid-from")
    relation_parser.add_argument("--valid-until")
    relation_parser.add_argument("--relation-id")

    candidate_parser = subparsers.add_parser(
        "record-resolution-candidate",
        help="Record a reversible possible identity match without merging entities",
    )
    _add_ledger_argument(candidate_parser)
    candidate_parser.add_argument("--left", required=True)
    candidate_parser.add_argument("--right", required=True)
    candidate_parser.add_argument(
        "--signal-json",
        required=True,
        action="append",
        help="Closed resolution signal JSON object; repeat for multiple signals",
    )
    candidate_parser.add_argument("--candidate-id")

    assessment_parser = subparsers.add_parser(
        "assess-resolution-candidate",
        help="Record a reversible manual assessment; never merges entities",
    )
    _add_ledger_argument(assessment_parser)
    assessment_parser.add_argument("--candidate", required=True)
    assessment_parser.add_argument(
        "--disposition",
        required=True,
        choices=(
            "POSSIBLE_MATCH",
            "RETAIN_SEPARATE",
            "REJECTED_AS_MATCH",
            "CONFIRMED_MATCH_NOT_MERGED",
        ),
    )
    assessment_parser.add_argument("--rationale", required=True)
    assessment_parser.add_argument("--reviewer", default="local-user")
    assessment_parser.add_argument("--supersedes")
    assessment_parser.add_argument("--assessment-id")

    surface_parser = subparsers.add_parser(
        "register-cartographic-surface",
        help="Register an observer-frame surface with explicit blind-region state",
    )
    _add_ledger_argument(surface_parser)
    surface_parser.add_argument("--name", required=True)
    surface_parser.add_argument("--description", required=True)
    surface_parser.add_argument("--frame", required=True, action="append")
    surface_parser.add_argument(
        "--blind-region-state",
        choices=("DECLARED", "NOT_CHARACTERIZED"),
        default="NOT_CHARACTERIZED",
    )
    surface_parser.add_argument("--blind-region", action="append", default=[])
    surface_parser.add_argument("--validity-condition", action="append", default=[])
    surface_parser.add_argument("--surface-id")

    query_parser = subparsers.add_parser(
        "plan-cartographic-query",
        help="Persist a read-only backward local-ledger query plan",
    )
    _add_ledger_argument(query_parser)
    query_parser.add_argument("--asset", required=True)
    query_parser.add_argument("--surface", required=True, action="append")
    query_parser.add_argument("--mode", choices=RECONSTRUCTION_MODES, default="AS_KNOWN_THEN")
    query_parser.add_argument("--epistemic-cutoff")
    query_parser.add_argument("--max-relation-hops", type=int)
    query_parser.add_argument("--no-relations", action="store_true")
    query_parser.add_argument("--query-id")

    fitter_parser = subparsers.add_parser(
        "register-reference-fitter",
        help="Register a deterministic local Bayesian, graph, or temporal diagnostic fitter",
    )
    _add_ledger_argument(fitter_parser)
    fitter_parser.add_argument(
        "--class",
        required=True,
        choices=("BAYESIAN", "GRAPH", "TEMPORAL"),
        dest="fitter_class",
    )
    fitter_parser.add_argument("--fitter-id")

    run_fitters_parser = subparsers.add_parser(
        "run-fitters",
        help="Run registered reference fitters over one persisted cartographic query",
    )
    _add_ledger_argument(run_fitters_parser)
    run_fitters_parser.add_argument("--query", required=True)
    run_fitters_parser.add_argument("--fitter", required=True, action="append")
    run_fitters_parser.add_argument("--run-group-id")

    hypothesis_parser = subparsers.add_parser(
        "create-hypothesis",
        help="Create an unresolved hypothesis with explicit claim polarity bindings",
    )
    _add_ledger_argument(hypothesis_parser)
    hypothesis_parser.add_argument("--asset", required=True)
    hypothesis_parser.add_argument("--name", required=True)
    hypothesis_parser.add_argument("--statement", required=True)
    hypothesis_parser.add_argument("--target", action="append", default=[])
    hypothesis_parser.add_argument(
        "--claim-binding-json",
        action="append",
        default=[],
        help="Claim binding JSON with claim_id and polarity",
    )
    hypothesis_parser.add_argument("--hypothesis-id")

    belief_edge_parser = subparsers.add_parser(
        "create-belief-edge",
        help="Create one assumption-bound directed edge in the acyclic belief graph",
    )
    _add_ledger_argument(belief_edge_parser)
    belief_edge_parser.add_argument("--source-hypothesis", required=True)
    belief_edge_parser.add_argument("--target-hypothesis", required=True)
    belief_edge_parser.add_argument(
        "--polarity",
        required=True,
        choices=(
            "SUPPORTS_IF_SOURCE_SUPPORT_LEADING",
            "CHALLENGES_IF_SOURCE_SUPPORT_LEADING",
        ),
    )
    belief_edge_parser.add_argument("--assumption", required=True)
    belief_edge_parser.add_argument("--edge-id")

    revise_beliefs_parser = subparsers.add_parser(
        "revise-beliefs",
        help="Run dependency-aware categorical propagation without computing probabilities",
    )
    _add_ledger_argument(revise_beliefs_parser)
    revise_beliefs_parser.add_argument("--asset", required=True)
    revise_beliefs_parser.add_argument("--hypothesis", action="append", default=[])
    revise_beliefs_parser.add_argument("--revision-id")

    scenario_parser = subparsers.add_parser(
        "create-scenario",
        help="Create an assumption-bound conditional scenario with a visible unknown branch",
    )
    _add_ledger_argument(scenario_parser)
    scenario_parser.add_argument("--asset", required=True)
    scenario_parser.add_argument("--name", required=True)
    scenario_parser.add_argument("--belief-revision", required=True)
    scenario_parser.add_argument("--target", action="append", default=[])
    scenario_parser.add_argument("--start-time", required=True)
    scenario_parser.add_argument("--horizon-days", required=True, type=int)
    scenario_parser.add_argument("--assumption-json", required=True, action="append")
    scenario_parser.add_argument("--intervention-json", required=True, action="append")
    scenario_parser.add_argument("--branch-json", required=True, action="append")
    scenario_parser.add_argument("--scenario-id")

    run_scenario_parser = subparsers.add_parser(
        "run-scenario",
        help="Evaluate scenario antecedents without simulating trajectories or likelihoods",
    )
    _add_ledger_argument(run_scenario_parser)
    run_scenario_parser.add_argument("--scenario", required=True)
    run_scenario_parser.add_argument("--run-id")

    show_parser = subparsers.add_parser("show-asset", help="Replay and inspect one tracked asset")
    _add_ledger_argument(show_parser)
    show_parser.add_argument("--asset", required=True)
    show_parser.add_argument("--mode", choices=RECONSTRUCTION_MODES, default="AS_KNOWN_THEN")
    show_parser.add_argument("--epistemic-cutoff")

    timeline_parser = subparsers.add_parser(
        "show-timeline", help="Inspect a hindsight-labeled asset timeline"
    )
    _add_ledger_argument(timeline_parser)
    timeline_parser.add_argument("--asset", required=True)
    timeline_parser.add_argument("--mode", choices=RECONSTRUCTION_MODES, default="AS_KNOWN_THEN")
    timeline_parser.add_argument("--epistemic-cutoff")

    candidate_view_parser = subparsers.add_parser(
        "show-resolution-candidate",
        help="Inspect one candidate and its append-only assessment history",
    )
    _add_ledger_argument(candidate_view_parser)
    candidate_view_parser.add_argument("--candidate", required=True)

    surface_view_parser = subparsers.add_parser(
        "show-cartographic-surface", help="Inspect one registered cartographic surface"
    )
    _add_ledger_argument(surface_view_parser)
    surface_view_parser.add_argument("--surface", required=True)

    query_view_parser = subparsers.add_parser(
        "show-cartographic-query", help="Inspect one persisted cartographic query plan"
    )
    _add_ledger_argument(query_view_parser)
    query_view_parser.add_argument("--query", required=True)

    run_query_parser = subparsers.add_parser(
        "run-cartographic-query",
        help="Execute one plan deterministically against the local ledger",
    )
    _add_ledger_argument(run_query_parser)
    run_query_parser.add_argument("--query", required=True)

    fitter_view_parser = subparsers.add_parser(
        "show-fitter", help="Inspect one fitter descriptor and its retained runs"
    )
    _add_ledger_argument(fitter_view_parser)
    fitter_view_parser.add_argument("--fitter", required=True)

    fitter_run_view_parser = subparsers.add_parser(
        "show-fitter-run", help="Inspect one fitter result or abstention with its receipt"
    )
    _add_ledger_argument(fitter_run_view_parser)
    fitter_run_view_parser.add_argument("--run", required=True)

    multi_fitter_view_parser = subparsers.add_parser(
        "show-multi-fitter-run",
        help="Inspect retained heterogeneous outcomes without computing consensus",
    )
    _add_ledger_argument(multi_fitter_view_parser)
    multi_fitter_view_parser.add_argument("--run-group", required=True)

    hypothesis_view_parser = subparsers.add_parser(
        "show-hypothesis", help="Inspect one hypothesis, its edges, and latest categorical result"
    )
    _add_ledger_argument(hypothesis_view_parser)
    hypothesis_view_parser.add_argument("--hypothesis", required=True)

    belief_revision_view_parser = subparsers.add_parser(
        "show-belief-revision", help="Inspect one dependency-bound belief execution receipt"
    )
    _add_ledger_argument(belief_revision_view_parser)
    belief_revision_view_parser.add_argument("--revision", required=True)

    scenario_view_parser = subparsers.add_parser(
        "show-scenario", help="Inspect one conditional scenario plan and retained unknown branch"
    )
    _add_ledger_argument(scenario_view_parser)
    scenario_view_parser.add_argument("--scenario", required=True)

    scenario_run_view_parser = subparsers.add_parser(
        "show-scenario-run", help="Inspect a structural scenario evaluation and receipt"
    )
    _add_ledger_argument(scenario_run_view_parser)
    scenario_run_view_parser.add_argument("--run", required=True)

    list_parser = subparsers.add_parser("list-assets", help="Replay and list the tracked catalog")
    _add_ledger_argument(list_parser)

    workbench_view_parser = subparsers.add_parser(
        "show-workbench",
        help="Emit the bounded read-only asset-workbench projection as JSON",
    )
    _add_ledger_argument(workbench_view_parser)
    workbench_view_parser.add_argument("--asset")

    workbench_parser = subparsers.add_parser(
        "workbench",
        help="Serve the read-only asset workbench on a loopback interface",
    )
    _add_ledger_argument(workbench_parser)
    workbench_parser.add_argument("--host", default="127.0.0.1")
    workbench_parser.add_argument("--port", type=int, default=4173)

    return parser


def _run(args: argparse.Namespace) -> Any:
    ledger = _ledger(args)
    if args.command == "init":
        ledger.initialize()
        return {
            "ledger": str(ledger.path),
            "status": "initialized",
            "authority_state": "NO_AUTHORITY",
        }

    if args.command == "create-entity":
        entity_event = create_entity_created(
            args.name,
            args.entity_type,
            aliases=args.alias,
            attributes=_json_object(args.attributes_json),
            entity_id=args.entity_id,
        )
        ledger.append(entity_event)
        entity_id = entity_event["payload"]["entity"]["id"]
        events = [entity_event]
        if not args.no_track:
            tracking_event = create_tracking_started(
                entity_id,
                priority=args.priority,
                scopes=args.scope or ("observer_frame", "temporal"),
            )
            ledger.append(tracking_event)
            events.append(tracking_event)
        return {"entity_id": entity_id, "events": events, "authority_state": "NO_AUTHORITY"}

    if args.command == "workbench":
        serve_workbench(ledger.path, host=args.host, port=args.port)
        return {
            "status": "stopped",
            "authority_state": "NO_AUTHORITY",
        }

    if args.command == "start-tracking":
        event = create_tracking_started(
            args.entity,
            priority=args.priority,
            scopes=args.scope or ("observer_frame", "temporal"),
        )
        ledger.append(event)
        return event

    if args.command == "register-frame":
        event = create_observer_frame_registered(
            args.name,
            args.frame_class,
            access_scope=args.access_policy,
            access_description=args.access_description,
            known_blind_regions=args.blind_region,
            validity_conditions=args.validity_condition,
            frame_id=args.frame_id,
        )
        ledger.append(event)
        return event

    if args.command == "manifest-evidence":
        event = create_evidence_manifested(
            args.sha256,
            args.media_type,
            args.size,
            args.source_label,
            source_uri=args.source_uri,
            license_name=args.license,
            access_policy=args.access_policy,
            artifact_id=args.artifact_id,
        )
        ledger.append(event)
        return event

    if args.command == "admit-observation":
        event = create_observation_admitted(
            args.asset,
            args.frame,
            args.artifact,
            args.observation_type,
            _json_object(args.payload_json),
            args.observed_at,
            source_uri=args.source_uri,
            source_policy=args.source_policy,
            missingness_state=args.missingness,
            uncertainty=_json_object(args.uncertainty_json),
            observation_id=args.observation_id,
            supersedes_observation_id=args.supersedes,
        )
        ledger.append(event)
        return event

    if args.command == "declare-dependency":
        event = create_evidence_dependency_declared(
            args.group,
            args.ancestor,
            args.descendant,
            args.relationship,
            verification_status=args.verification_status,
            basis_method=args.basis_method,
            basis_notes=args.basis_notes,
            dependency_id=args.dependency_id,
        )
        ledger.append(event)
        return event

    if args.command == "create-claim":
        claim_object = (
            {"kind": "ENTITY", "entity_id": args.object_entity}
            if args.object_entity
            else {"kind": "LITERAL", "value": _json_scalar(args.object_literal_json)}
        )
        event = create_claim_created(
            args.subject,
            args.predicate,
            claim_object,
            args.derived_from,
            modality=args.modality,
            valid_from=args.valid_from,
            valid_until=args.valid_until,
            invalidation_conditions=args.invalidation_condition,
            claim_id=args.claim_id,
        )
        ledger.append(event)
        return event

    if args.command == "link-evidence":
        event = create_evidence_linked(
            args.evidence,
            args.claim,
            args.role,
            dependency_group=args.dependency_group,
            warrant_statement=args.warrant_statement,
            warrant_basis=args.warrant_basis,
            appraisal_status=args.appraisal_status,
            appraisal_method=args.appraisal_method,
            appraisal_notes=args.appraisal_notes,
            strength_status="ASSESSED" if args.strength else "UNASSESSED",
            strength_ordinal=args.strength,
            link_id=args.link_id,
        )
        ledger.append(event)
        return event

    if args.command == "create-relation":
        event = create_relation_created(
            args.source,
            args.relation_type,
            args.target,
            args.claim,
            relation_semantics=args.semantics,
            valid_from=args.valid_from,
            valid_until=args.valid_until,
            relation_id=args.relation_id,
        )
        ledger.append(event)
        return event

    if args.command == "record-resolution-candidate":
        event = create_resolution_candidate_recorded(
            args.left,
            args.right,
            [_json_object(item) for item in args.signal_json],
            candidate_id=args.candidate_id,
        )
        ledger.append(event)
        return event

    if args.command == "assess-resolution-candidate":
        event = create_resolution_candidate_assessed(
            args.candidate,
            args.disposition,
            args.rationale,
            reviewer_label=args.reviewer,
            supersedes_assessment_id=args.supersedes,
            assessment_id=args.assessment_id,
        )
        ledger.append(event)
        return event

    if args.command == "register-cartographic-surface":
        event = create_cartographic_surface_registered(
            args.name,
            args.description,
            args.frame,
            blind_region_state=args.blind_region_state,
            blind_regions=args.blind_region,
            validity_conditions=args.validity_condition,
            surface_id=args.surface_id,
        )
        ledger.append(event)
        return event

    if args.command == "plan-cartographic-query":
        max_relation_hops = args.max_relation_hops
        if max_relation_hops is None:
            max_relation_hops = 0 if args.no_relations else 1
        event = create_cartographic_query_planned(
            args.asset,
            args.surface,
            reconstruction_mode=args.mode,
            epistemic_cutoff=args.epistemic_cutoff,
            max_relation_hops=max_relation_hops,
            include_relations=not args.no_relations,
            query_id=args.query_id,
        )
        ledger.append(event)
        return event

    if args.command == "register-reference-fitter":
        event = create_reference_fitter_registration(
            args.fitter_class,
            fitter_id=args.fitter_id,
        )
        ledger.append(event)
        return event

    if args.command == "run-fitters":
        projection = ledger.projection()
        events = execute_reference_fitter_group(
            projection,
            args.query,
            args.fitter,
            run_group_id=args.run_group_id,
        )
        for event in events:
            ledger.append(event)
        run_group_id = events[0]["payload"]["fitter_run"]["run_group_id"]
        return ledger.projection().multi_fitter_run_view(run_group_id)

    if args.command == "create-hypothesis":
        event = create_hypothesis_created(
            args.asset,
            args.name,
            args.statement,
            [_json_object(item) for item in args.claim_binding_json],
            target_entity_ids=args.target,
            hypothesis_id=args.hypothesis_id,
        )
        ledger.append(event)
        return event

    if args.command == "create-belief-edge":
        event = create_belief_edge_created(
            args.source_hypothesis,
            args.target_hypothesis,
            args.polarity,
            args.assumption,
            edge_id=args.edge_id,
        )
        ledger.append(event)
        return event

    if args.command == "revise-beliefs":
        projection = ledger.projection()
        event = execute_belief_revision(
            projection,
            args.asset,
            args.hypothesis or None,
            revision_id=args.revision_id,
        )
        ledger.append(event)
        revision_id = event["payload"]["belief_revision"]["id"]
        return ledger.projection().belief_revision_view(revision_id)

    if args.command == "create-scenario":
        projection = ledger.projection()
        event = create_bounded_scenario(
            projection,
            args.asset,
            args.name,
            args.belief_revision,
            args.target or [args.asset],
            [_json_object(item) for item in args.assumption_json],
            [_json_object(item) for item in args.intervention_json],
            [_json_object(item) for item in args.branch_json],
            start_time=args.start_time,
            horizon_days=args.horizon_days,
            scenario_id=args.scenario_id,
        )
        ledger.append(event)
        return event

    if args.command == "run-scenario":
        projection = ledger.projection()
        event = execute_scenario(
            projection,
            args.scenario,
            run_id=args.run_id,
        )
        ledger.append(event)
        run_id = event["payload"]["scenario_run"]["id"]
        return ledger.projection().scenario_run_view(run_id)

    projection = ledger.projection()
    if args.command == "show-asset":
        return projection.asset_view_at(
            args.asset,
            mode=args.mode,
            epistemic_cutoff=args.epistemic_cutoff,
        )
    if args.command == "show-timeline":
        return projection.timeline_view(
            args.asset,
            mode=args.mode,
            epistemic_cutoff=args.epistemic_cutoff,
        )
    if args.command == "show-resolution-candidate":
        return projection.resolution_candidate_view(args.candidate)
    if args.command == "show-cartographic-surface":
        return projection.cartographic_surface_view(args.surface)
    if args.command == "show-cartographic-query":
        return projection.cartographic_query_plan_view(args.query)
    if args.command == "run-cartographic-query":
        return projection.execute_cartographic_query(args.query)
    if args.command == "show-fitter":
        return projection.fitter_view(args.fitter)
    if args.command == "show-fitter-run":
        return projection.fitter_run_view(args.run)
    if args.command == "show-multi-fitter-run":
        return projection.multi_fitter_run_view(args.run_group)
    if args.command == "show-hypothesis":
        return projection.hypothesis_view(args.hypothesis)
    if args.command == "show-belief-revision":
        return projection.belief_revision_view(args.revision)
    if args.command == "show-scenario":
        return projection.scenario_view(args.scenario)
    if args.command == "show-scenario-run":
        return projection.scenario_run_view(args.run)
    if args.command == "list-assets":
        return projection.catalog_view()
    if args.command == "show-workbench":
        return build_workbench_snapshot(projection, args.asset)
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _emit(_run(args))
        return 0
    except (
        ContractViolation,
        BeliefRuntimeError,
        FitterRuntimeError,
        KeyError,
        LedgerError,
        ProjectionError,
        ScenarioRuntimeError,
        WorkbenchError,
        ValueError,
    ) as error:
        print(f"readin: {error}", file=sys.stderr)
        return 2
