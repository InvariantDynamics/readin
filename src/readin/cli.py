"""Command-line interface for the local READIN Phase 0 through Phase 3 runtime."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from readin.contracts import ContractViolation
from readin.events import (
    create_cartographic_query_planned,
    create_cartographic_surface_registered,
    create_claim_created,
    create_entity_created,
    create_evidence_dependency_declared,
    create_evidence_linked,
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
    create_relation_created,
    create_resolution_candidate_assessed,
    create_resolution_candidate_recorded,
    create_tracking_started,
)
from readin.projection import ProjectionError
from readin.store import EventLedger, LedgerError

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

    list_parser = subparsers.add_parser("list-assets", help="Replay and list the tracked catalog")
    _add_ledger_argument(list_parser)

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
    if args.command == "list-assets":
        return projection.catalog_view()
    raise AssertionError(f"unhandled command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        _emit(_run(args))
        return 0
    except (ContractViolation, LedgerError, ProjectionError, ValueError) as error:
        print(f"readin: {error}", file=sys.stderr)
        return 2
