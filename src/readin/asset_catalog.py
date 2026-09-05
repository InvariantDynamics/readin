"""Local personal-asset catalog manifests for pre-connector READIN onboarding."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
from collections.abc import Mapping
from datetime import UTC, datetime
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from readin.events import (
    create_entity_created,
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
    create_tracking_started,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.store import EventLedger, LedgerMissing

JsonObject = dict[str, Any]

ASSET_CATALOG_SCHEMA_VERSION = "readin.asset-catalog-source.v0.1"
ASSET_CATALOG_IMPORT_VERSION = "readin.asset-catalog-import.v0.1"
ASSET_CATALOG_ADAPTER_VERSION = "0.1.0"
MAX_ASSET_CATALOG_SOURCE_BYTES = 262_144

ASSET_CLASS_ENTITY_TYPES = {
    "SOCIAL_ACCOUNT": "OnlineAccount",
    "ORGANIZATION_ACCOUNT": "OrganizationAccount",
    "SOFTWARE_REPOSITORY": "SoftwareRepository",
    "WEB_PROPERTY": "WebProperty",
    "DOCUMENT_COLLECTION": "DocumentCollection",
    "EMAIL_ACCOUNT": "CommunicationsAccount",
    "CALENDAR_ACCOUNT": "CalendarAccount",
    "FINANCIAL_ACCOUNT": "FinancialAccount",
    "DEVICE": "Device",
    "LOCAL_FILE_COLLECTION": "LocalFileCollection",
    "OTHER": "Asset",
}


class AssetCatalogError(RuntimeError):
    """Raised when a local asset catalog source cannot be admitted safely."""


class AssetCatalogContractError(AssetCatalogError):
    """Raised when a manifest violates the closed asset-catalog source contract."""


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise AssetCatalogError(f"invalid timestamp: {value}") from error
    return value


def _utc_timestamp(value: str | datetime | None = None) -> str:
    selected = _parse_timestamp(value) if value is not None else datetime.now(UTC)
    if selected.tzinfo is None or selected.utcoffset() is None:
        raise AssetCatalogError("timestamps must include a UTC offset")
    return selected.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _development_schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "v0.1"
        / "asset-catalog-source.schema.json"
    )


@lru_cache(maxsize=1)
def load_asset_catalog_source_schema() -> JsonObject:
    """Return the closed local manifest schema for asset catalog onboarding."""

    packaged = files("readin").joinpath("schemas/v0.1/asset-catalog-source.schema.json")
    if packaged.is_file():
        return json.loads(packaged.read_text(encoding="utf-8"))
    path = _development_schema_path()
    if not path.is_file():
        raise AssetCatalogContractError(f"asset catalog source schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _asset_catalog_validator() -> Draft202012Validator:
    schema = load_asset_catalog_source_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _asset_key(asset: Mapping[str, Any]) -> str:
    return "|".join(
        (
            str(asset["asset_class"]).strip().upper(),
            str(asset["platform"]).strip().casefold(),
            str(asset["account_identifier"]).strip().casefold(),
        )
    )


def _stable_uuid(kind: str, *parts: object) -> str:
    value = json.dumps([kind, *parts], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return str(uuid5(NAMESPACE_URL, f"readin.asset-catalog.v0.1:{value}"))


def _source_uri(catalog_id: str, source_sha256: str) -> str:
    return f"urn:readin:asset-catalog-source:{catalog_id}:sha256:{source_sha256}"


def _catalog_source_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _format_schema_errors(errors: list[Any]) -> str:
    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return "; ".join(messages)


def validate_asset_catalog_source(source: JsonObject) -> None:
    """Validate a closed local asset catalog source and its cross-field invariants."""

    errors = sorted(
        _asset_catalog_validator().iter_errors(source),
        key=lambda error: list(error.path),
    )
    if errors:
        raise AssetCatalogContractError(_format_schema_errors(errors))

    seen: dict[str, str] = {}
    for index, asset in enumerate(source["assets"], start=1):
        key = _asset_key(asset)
        if key in seen:
            raise AssetCatalogContractError(
                f"assets.{index}: duplicate asset declaration matches {seen[key]}: {key}"
            )
        seen[key] = f"assets.{index}"

        connector = asset["connector_intent"]
        connection_state = connector["connection_state"]
        collection_mode = asset["collection_mode"]
        connector_kind = connector["connector_kind"]
        oauth_state = connector["oauth_state"]
        if connection_state == "OAUTH_REQUIRED_NOT_REQUESTED":
            if collection_mode != "API_CONNECTION_REQUIRES_SEPARATE_GRANT":
                raise AssetCatalogContractError(
                    f"assets.{index}: OAuth-required state requires API connection mode"
                )
            if connector_kind != "OAUTH_API" or oauth_state != "NOT_REQUESTED":
                raise AssetCatalogContractError(
                    f"assets.{index}: OAuth-required state must use OAUTH_API/NOT_REQUESTED"
                )
        if connector_kind == "OAUTH_API" and oauth_state != "NOT_REQUESTED":
            raise AssetCatalogContractError(
                f"assets.{index}: OAUTH_API connector intent must keep oauth_state NOT_REQUESTED"
            )


def _absolute_local_path(path: str | Path) -> Path:
    return Path(path).expanduser().absolute()


def _reject_symlink_components(path: Path, label: str) -> None:
    existing: list[Path] = []
    cursor = path
    while True:
        if cursor.exists() or cursor.is_symlink():
            existing.append(cursor)
        if cursor.parent == cursor:
            break
        cursor = cursor.parent
    for component in reversed(existing):
        if component.is_symlink():
            raise AssetCatalogError(f"{label} path contains a symbolic link: {component}")


def _reject_git_checkout_path(path: Path, label: str) -> None:
    cursor = path if path.exists() and path.is_dir() else path.parent
    for parent in (cursor, *cursor.parents):
        if (parent / ".git").exists():
            raise AssetCatalogError(f"{label} must be stored outside Git checkouts")


def _read_private_manifest(path: Path) -> tuple[JsonObject, str, int]:
    _reject_symlink_components(path, "asset catalog source")
    _reject_git_checkout_path(path, "asset catalog source")
    try:
        before = path.lstat()
    except FileNotFoundError as error:
        raise AssetCatalogError(f"asset catalog source is missing: {path}") from error
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise AssetCatalogError(f"asset catalog source must be a private regular file: {path}")
    if stat.S_IMODE(before.st_mode) & 0o077:
        raise AssetCatalogError(f"asset catalog source is not owner-only: {path}")
    if before.st_uid != os.geteuid():
        raise AssetCatalogError(f"asset catalog source is not owned by the current user: {path}")
    if before.st_size > MAX_ASSET_CATALOG_SOURCE_BYTES:
        raise AssetCatalogError(
            f"asset catalog source exceeds {MAX_ASSET_CATALOG_SOURCE_BYTES} bytes: {path}"
        )

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise AssetCatalogError(
                f"asset catalog source must not be a symlink: {path}"
            ) from error
        raise AssetCatalogError(f"could not open asset catalog source: {path}") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise AssetCatalogError(f"asset catalog source must be a regular file: {path}")
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise AssetCatalogError(f"asset catalog source changed while opening: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(MAX_ASSET_CATALOG_SOURCE_BYTES + 1)
    finally:
        os.close(descriptor)

    if len(raw) > MAX_ASSET_CATALOG_SOURCE_BYTES:
        raise AssetCatalogError(
            f"asset catalog source exceeds {MAX_ASSET_CATALOG_SOURCE_BYTES} bytes: {path}"
        )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise AssetCatalogError("asset catalog source must be UTF-8 JSON") from error
    except json.JSONDecodeError as error:
        raise AssetCatalogError(f"asset catalog source is not valid JSON: {error.msg}") from error
    if not isinstance(parsed, dict):
        raise AssetCatalogError("asset catalog source must be a JSON object")
    validate_asset_catalog_source(parsed)
    return parsed, _catalog_source_digest(raw), len(raw)


def load_asset_catalog_source(path: str | Path) -> tuple[JsonObject, str, int]:
    """Read and validate one private local asset catalog source."""

    return _read_private_manifest(_absolute_local_path(path))


def _connector_summary(source: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in source["assets"]:
        state = asset["connector_intent"]["connection_state"]
        counts[state] = counts.get(state, 0) + 1
    return counts


def _class_summary(source: Mapping[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for asset in source["assets"]:
        asset_class = asset["asset_class"]
        counts[asset_class] = counts.get(asset_class, 0) + 1
    return counts


def _binding_for_asset(
    source: Mapping[str, Any],
    asset: Mapping[str, Any],
    *,
    asset_key: str,
    source_sha256: str,
) -> JsonObject:
    connector = dict(asset["connector_intent"])
    return {
        "schema_version": ASSET_CATALOG_SCHEMA_VERSION,
        "catalog_id": source["catalog_id"],
        "catalog_name": source["catalog_name"],
        "asset_key": asset_key,
        "asset_class": asset["asset_class"],
        "platform": asset["platform"],
        "account_identifier": asset["account_identifier"],
        "source_uri": asset["source_uri"],
        "authorization_basis": asset["authorization_basis"],
        "ownership_attestation": source["owner"]["attestation"],
        "owner_scope": source["owner"]["scope"],
        "purpose_kind": source["purpose"]["kind"],
        "source_digest_sha256": source_sha256,
        "source_kind": source["source"]["kind"],
        "collection_mode": asset["collection_mode"],
        "connector_intent": connector,
        "authority": {
            "state": "NO_AUTHORITY",
            "collection": "NOT_GRANTED",
            "network_access": False,
            "external_actions": "PROHIBITED",
            "people_targeting": "PROHIBITED",
        },
    }


def _profile_payload(
    source: Mapping[str, Any],
    asset: Mapping[str, Any],
    *,
    asset_key: str,
    source_sha256: str,
) -> JsonObject:
    return {
        "asset_catalog_profile": {
            "schema_version": ASSET_CATALOG_SCHEMA_VERSION,
            "catalog_id": source["catalog_id"],
            "catalog_name": source["catalog_name"],
            "asset_key": asset_key,
            "asset_class": asset["asset_class"],
            "display_name": asset["display_name"],
            "platform": asset["platform"],
            "account_identifier": asset["account_identifier"],
            "source_uri": asset["source_uri"],
            "authorization_basis": asset["authorization_basis"],
            "collection_mode": asset["collection_mode"],
            "connector_intent": dict(asset["connector_intent"]),
            "source_digest_sha256": source_sha256,
            "source_kind": source["source"]["kind"],
            "owner_attestation": source["owner"]["attestation"],
            "authority_state": "NO_AUTHORITY",
            "network_access": False,
            "live_collection_state": "DISABLED",
            "external_action_state": "PROHIBITED",
            "people_targeting": "PROHIBITED",
        }
    }


def build_asset_catalog_events(
    source: Mapping[str, Any],
    *,
    source_sha256: str,
    source_size: int,
    occurred_at: str | datetime | None = None,
) -> list[JsonObject]:
    """Build deterministic ledger events for a local asset catalog source."""

    if not isinstance(source, dict):
        raise AssetCatalogError("asset catalog source must be a JSON object")
    validate_asset_catalog_source(source)
    event_time = _utc_timestamp(occurred_at) if occurred_at else source["declared_at"]
    catalog_id = source["catalog_id"]
    frame_id = _stable_uuid("observer-frame", catalog_id)
    evidence_id = _stable_uuid("evidence", catalog_id, source_sha256)
    manifest_uri = _source_uri(catalog_id, source_sha256)
    events = [
        create_observer_frame_registered(
            f"Local asset catalog manifest: {source['catalog_name']}",
            "local_asset_catalog_manifest",
            access_scope="USER_OWNED",
            access_description=(
                "One private user-declared local manifest; no external source was contacted"
            ),
            measurement_name="user_declared_asset_profile",
            measurement_description=(
                "The operator declared an owned or otherwise authorized asset profile"
            ),
            granularity_name="one_manifest_entry",
            granularity_description="One manifest row for one declared asset or account",
            interpretation_name="declared_catalog_entry_without_live_collection",
            interpretation_description=(
                "Records connector intent and authorization boundaries without account access"
            ),
            latency_class="UNKNOWN",
            known_blind_regions=(
                "No private messages, followers, contacts, social graph, account content, "
                "or third-party profiles were collected",
                "No source completeness, ownership proof, or platform terms compatibility "
                "is established",
            ),
            validity_conditions=(
                "Manifest was supplied from a private local regular file",
                "Operator explicitly attested the catalog is limited to self or controlled assets",
                "Credentials, OAuth grants, live collection, person targeting, and external "
                "action are absent",
            ),
            frame_id=frame_id,
            event_id=_stable_uuid("event", "observer_frame.registered", catalog_id),
            occurred_at=event_time,
        ),
        create_evidence_manifested(
            source_sha256,
            "application/json",
            source_size,
            f"Local asset catalog manifest: {source['catalog_name']}",
            source_uri=manifest_uri,
            license_name=None,
            access_policy="USER_OWNED",
            artifact_id=evidence_id,
            acquired_at=event_time,
            event_id=_stable_uuid("event", "evidence.manifested", catalog_id, source_sha256),
            occurred_at=event_time,
        ),
    ]
    for asset in source["assets"]:
        asset_key = _asset_key(asset)
        entity_id = _stable_uuid("entity", catalog_id, asset_key)
        entity_event = create_entity_created(
            asset["display_name"],
            ASSET_CLASS_ENTITY_TYPES[asset["asset_class"]],
            aliases=(f"{asset['platform']}:{asset['account_identifier']}",),
            external_ids=(
                {"scheme": "asset_catalog_key", "value": asset_key},
                {
                    "scheme": "platform_account_identifier",
                    "value": f"{asset['platform']}:{asset['account_identifier']}",
                },
            ),
            attributes={
                "asset_catalog_binding": _binding_for_asset(
                    source,
                    asset,
                    asset_key=asset_key,
                    source_sha256=source_sha256,
                )
            },
            entity_id=entity_id,
            created_at=event_time,
            event_id=_stable_uuid("event", "entity.created", catalog_id, asset_key),
            occurred_at=event_time,
        )
        tracking_event = create_tracking_started(
            entity_id,
            priority=0.5,
            collection_profile="asset_catalog_manifest_v0_1",
            update_policy="manual",
            scopes=("observer_frame", "topic", "temporal"),
            event_id=_stable_uuid("event", "asset.tracking_started", catalog_id, asset_key),
            occurred_at=event_time,
        )
        observation_event = create_observation_admitted(
            (entity_id,),
            frame_id,
            evidence_id,
            "asset_catalog.user_declared_profile",
            _profile_payload(
                source,
                asset,
                asset_key=asset_key,
                source_sha256=source_sha256,
            ),
            source["declared_at"],
            source_uri=manifest_uri,
            source_policy="USER_OWNED",
            collector="readin-asset-catalog-import",
            adapter="local-asset-catalog-manifest",
            adapter_version=ASSET_CATALOG_ADAPTER_VERSION,
            acquisition_time=event_time,
            uncertainty={
                "ownership_verification": "USER_ATTESTED_NOT_VERIFIED",
                "source_coverage": "NOT_ESTABLISHED",
                "connector_capability": "DECLARED_NOT_VERIFIED",
            },
            missingness_state="OBSERVED",
            observation_id=_stable_uuid("observation", catalog_id, source_sha256, asset_key),
            event_id=_stable_uuid(
                "event",
                "observation.admitted",
                catalog_id,
                source_sha256,
                asset_key,
            ),
            occurred_at=event_time,
        )
        events.extend((entity_event, tracking_event, observation_event))
    return events


def _event_already_present(
    event: Mapping[str, Any],
    projection: ReadinProjection,
) -> bool:
    event_type = event["event_type"]
    payload = event["payload"]
    if event_type == "observer_frame.registered":
        return payload["observer_frame"]["id"] in projection.frames
    if event_type == "evidence.manifested":
        artifact = payload["evidence_manifest"]
        matching = [
            item for item in projection.evidence.values() if item["sha256"] == artifact["sha256"]
        ]
        if not matching:
            return False
        if matching[0]["id"] != artifact["id"]:
            raise AssetCatalogError(
                f"asset catalog source digest is already manifested as {matching[0]['id']}"
            )
        return True
    if event_type == "entity.created":
        entity = payload["entity"]
        existing = projection.entities.get(entity["id"])
        if existing is None:
            return False
        binding = existing["attributes"].get("asset_catalog_binding")
        expected = entity["attributes"]["asset_catalog_binding"]
        if not isinstance(binding, dict) or (
            binding.get("catalog_id"),
            binding.get("asset_key"),
        ) != (
            expected["catalog_id"],
            expected["asset_key"],
        ):
            raise AssetCatalogError(
                f"entity id already exists for a different asset: {entity['id']}"
            )
        return True
    if event_type == "asset.tracking_started":
        return payload["tracked_asset"]["entity_id"] in projection.assets
    if event_type == "observation.admitted":
        return payload["observation"]["id"] in projection.observations
    return event["event_id"] in projection.event_ids


def _asset_import_summary(
    source: Mapping[str, Any],
    *,
    source_sha256: str,
) -> list[JsonObject]:
    rows = []
    for asset in source["assets"]:
        asset_key = _asset_key(asset)
        entity_id = _stable_uuid("entity", source["catalog_id"], asset_key)
        rows.append(
            {
                "entity_id": entity_id,
                "asset_key": asset_key,
                "display_name": asset["display_name"],
                "asset_class": asset["asset_class"],
                "platform": asset["platform"],
                "account_identifier": asset["account_identifier"],
                "authorization_basis": asset["authorization_basis"],
                "collection_mode": asset["collection_mode"],
                "connection_state": asset["connector_intent"]["connection_state"],
                "connector_kind": asset["connector_intent"]["connector_kind"],
                "credential_state": asset["connector_intent"]["credential_state"],
                "oauth_state": asset["connector_intent"]["oauth_state"],
                "live_collection_state": asset["connector_intent"]["live_collection_state"],
                "observation_id": _stable_uuid(
                    "observation",
                    source["catalog_id"],
                    source_sha256,
                    asset_key,
                ),
                "authority_state": "NO_AUTHORITY",
            }
        )
    return rows


def import_asset_catalog_source(
    ledger: EventLedger,
    manifest_path: str | Path,
    *,
    attested: bool,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Import a private local manifest as tracked assets and user-declared observations."""

    if not attested:
        raise AssetCatalogError(
            "explicit attestation is required for self/controlled assets and "
            "no-live-collection limits"
        )
    _reject_git_checkout_path(_absolute_local_path(ledger.path), "asset catalog ledger")
    source, source_sha256, source_size = load_asset_catalog_source(manifest_path)
    try:
        existing_events = ledger.read_events()
        ledger_status = "existing"
    except LedgerMissing:
        ledger.initialize()
        existing_events = []
        ledger_status = "initialized"
    projection = ReadinProjection.replay(existing_events)
    candidate_events = build_asset_catalog_events(
        source,
        source_sha256=source_sha256,
        source_size=source_size,
        occurred_at=occurred_at,
    )
    append_events: list[JsonObject] = []
    for event in candidate_events:
        if _event_already_present(event, projection):
            continue
        try:
            projection.apply(event)
        except ProjectionError as error:
            raise AssetCatalogError(
                f"asset catalog import would violate ledger semantics: {error}"
            ) from error
        append_events.append(event)
    for event in append_events:
        ledger.append(event)

    return {
        "schema_version": ASSET_CATALOG_IMPORT_VERSION,
        "ledger": str(ledger.path),
        "ledger_status": ledger_status,
        "catalog_id": source["catalog_id"],
        "catalog_name": source["catalog_name"],
        "source_sha256": source_sha256,
        "source_size": source_size,
        "source_path_recorded_in_ledger": False,
        "assets_declared": len(source["assets"]),
        "asset_class_counts": _class_summary(source),
        "connection_state_counts": _connector_summary(source),
        "events_appended": len(append_events),
        "events_skipped_existing": len(candidate_events) - len(append_events),
        "assets": _asset_import_summary(source, source_sha256=source_sha256),
        "authority": {
            "state": "NO_AUTHORITY",
            "collection": "NOT_GRANTED",
            "network_access": False,
            "credential_storage": "PROHIBITED",
            "external_actions": "PROHIBITED",
            "people_targeting": "PROHIBITED",
        },
    }
