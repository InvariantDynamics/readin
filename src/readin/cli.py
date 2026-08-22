"""Command-line interface for the local READIN Phase 0 reference runtime."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from readin.contracts import ContractViolation
from readin.events import (
    create_entity_created,
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
    create_tracking_started,
)
from readin.projection import ProjectionError
from readin.store import EventLedger, LedgerError

ACCESS_POLICIES = ("PUBLIC", "LICENSED", "USER_OWNED", "OTHERWISE_AUTHORIZED")


def _json_object(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
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
        description="READIN Phase 0 local tracked-asset and observation runtime",
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

    show_parser = subparsers.add_parser("show-asset", help="Replay and inspect one tracked asset")
    _add_ledger_argument(show_parser)
    show_parser.add_argument("--asset", required=True)

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

    projection = ledger.projection()
    if args.command == "show-asset":
        return projection.asset_view(args.asset)
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
