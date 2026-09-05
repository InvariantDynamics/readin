"""Connector grant manifests for pre-collection READIN source setup."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import stat
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from readin.events import (
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.store import EventLedger, LedgerMissing

JsonObject = dict[str, Any]

CONNECTOR_GRANT_SCHEMA_VERSION = "readin.connector-grant-source.v0.1"
CONNECTOR_GRANT_IMPORT_VERSION = "readin.connector-grant-import.v0.1"
CONNECTOR_GRANT_ADAPTER_VERSION = "0.1.0"
CONNECTOR_GRANT_OBSERVATION_TYPE = "asset_connector.grant_declared"
MAX_CONNECTOR_GRANT_SOURCE_BYTES = 131_072

_GRANT_KIND_TO_ACCESS_MODE = {
    "MANUAL_ENTRY_ONLY": "MANUAL_ENTRY_ONLY",
    "LOCAL_EXPORT_ONLY": "LOCAL_EXPORT_IMPORT_ONLY",
    "OAUTH_API_REQUIRES_SEPARATE_TOKEN_FLOW": "API_CONNECTION_REQUIRES_SEPARATE_TOKEN_FLOW",
    "PUBLIC_ENDPOINT_REQUIRES_SEPARATE_POLICY": "PUBLIC_ENDPOINT_POLICY_REQUIRED",
}

_LOCAL_EXPORT_CONNECTORS = {
    "LOCAL_EXPORT",
    "GOOGLE_TAKEOUT",
    "SOCIAL_EXPORT",
    "BROKERAGE_EXPORT",
    "EMAIL_EXPORT",
    "CALENDAR_EXPORT",
}


class ConnectorGrantError(RuntimeError):
    """Raised when a connector grant manifest cannot be admitted safely."""


class ConnectorGrantContractError(ConnectorGrantError):
    """Raised when a grant manifest violates the closed source contract."""


def _development_schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "v0.1"
        / "connector-grant-source.schema.json"
    )


@lru_cache(maxsize=1)
def load_connector_grant_source_schema() -> JsonObject:
    """Return the closed local manifest schema for connector grant setup."""

    packaged = files("readin").joinpath("schemas/v0.1/connector-grant-source.schema.json")
    if packaged.is_file():
        return json.loads(packaged.read_text(encoding="utf-8"))
    path = _development_schema_path()
    if not path.is_file():
        raise ConnectorGrantContractError(f"connector grant source schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _connector_grant_validator() -> Draft202012Validator:
    schema = load_connector_grant_source_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _format_schema_errors(errors: list[Any]) -> str:
    messages = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return "; ".join(messages)


def validate_connector_grant_source(source: JsonObject) -> None:
    """Validate a closed connector grant source and its cross-field invariants."""

    errors = sorted(
        _connector_grant_validator().iter_errors(source),
        key=lambda error: list(error.path),
    )
    if errors:
        raise ConnectorGrantContractError(_format_schema_errors(errors))

    provider = source["provider"]
    grant = source["grant"]
    asset = source["asset"]
    if provider["platform"] != asset["platform"]:
        raise ConnectorGrantContractError("provider.platform must match asset.platform")

    expected_access_mode = _GRANT_KIND_TO_ACCESS_MODE[grant["grant_kind"]]
    if grant["access_mode"] != expected_access_mode:
        raise ConnectorGrantContractError(
            f"grant.access_mode must be {expected_access_mode} for {grant['grant_kind']}"
        )

    connector_kind = provider["connector_kind"]
    grant_kind = grant["grant_kind"]
    if grant_kind == "MANUAL_ENTRY_ONLY" and connector_kind != "MANUAL":
        raise ConnectorGrantContractError("manual grants must use the MANUAL connector kind")
    if grant_kind == "LOCAL_EXPORT_ONLY" and connector_kind not in _LOCAL_EXPORT_CONNECTORS:
        raise ConnectorGrantContractError("local export grants must use an export connector kind")
    if grant_kind == "OAUTH_API_REQUIRES_SEPARATE_TOKEN_FLOW" and connector_kind != "OAUTH_API":
        raise ConnectorGrantContractError("OAuth API grants must use the OAUTH_API connector kind")
    if grant_kind == "PUBLIC_ENDPOINT_REQUIRES_SEPARATE_POLICY" and connector_kind not in {
        "PUBLIC_WEB",
        "GITHUB_PUBLIC",
    }:
        raise ConnectorGrantContractError(
            "public endpoint grants must use PUBLIC_WEB or GITHUB_PUBLIC"
        )
    if connector_kind == "OAUTH_API" and grant["oauth_state"] != "NOT_REQUESTED":
        raise ConnectorGrantContractError("OAUTH_API grant must keep oauth_state NOT_REQUESTED")
    if connector_kind != "OAUTH_API" and grant["oauth_state"] != "NOT_REQUIRED":
        raise ConnectorGrantContractError("non-OAuth grant must keep oauth_state NOT_REQUIRED")

    seen_scopes: set[str] = set()
    for index, scope in enumerate(source["scopes"], start=1):
        scope_name = scope["scope_name"]
        if scope_name in seen_scopes:
            raise ConnectorGrantContractError(f"scopes.{index}: duplicate scope: {scope_name}")
        seen_scopes.add(scope_name)

    seen_observation_types: set[str] = set()
    for index, output in enumerate(source["allowed_observation_types"], start=1):
        observation_type = output["observation_type"]
        if observation_type in seen_observation_types:
            raise ConnectorGrantContractError(
                f"allowed_observation_types.{index}: duplicate observation type: {observation_type}"
            )
        seen_observation_types.add(observation_type)


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
            raise ConnectorGrantError(f"{label} path contains a symbolic link: {component}")


def _reject_git_checkout_path(path: Path, label: str) -> None:
    cursor = path if path.exists() and path.is_dir() else path.parent
    for parent in (cursor, *cursor.parents):
        if (parent / ".git").exists():
            raise ConnectorGrantError(f"{label} must be stored outside Git checkouts")


def _source_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_private_manifest(path: Path) -> tuple[JsonObject, str, int]:
    _reject_symlink_components(path, "connector grant source")
    _reject_git_checkout_path(path, "connector grant source")
    try:
        before = path.lstat()
    except FileNotFoundError as error:
        raise ConnectorGrantError(f"connector grant source is missing: {path}") from error
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise ConnectorGrantError(f"connector grant source must be a private regular file: {path}")
    if stat.S_IMODE(before.st_mode) & 0o077:
        raise ConnectorGrantError(f"connector grant source is not owner-only: {path}")
    if before.st_uid != os.geteuid():
        raise ConnectorGrantError(
            f"connector grant source is not owned by the current user: {path}"
        )
    if before.st_size > MAX_CONNECTOR_GRANT_SOURCE_BYTES:
        raise ConnectorGrantError(
            f"connector grant source exceeds {MAX_CONNECTOR_GRANT_SOURCE_BYTES} bytes: {path}"
        )

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ConnectorGrantError(
                f"connector grant source must not be a symlink: {path}"
            ) from error
        raise ConnectorGrantError(f"could not open connector grant source: {path}") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ConnectorGrantError(f"connector grant source must be a regular file: {path}")
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ConnectorGrantError(f"connector grant source changed while opening: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(MAX_CONNECTOR_GRANT_SOURCE_BYTES + 1)
    finally:
        os.close(descriptor)

    if len(raw) > MAX_CONNECTOR_GRANT_SOURCE_BYTES:
        raise ConnectorGrantError(
            f"connector grant source exceeds {MAX_CONNECTOR_GRANT_SOURCE_BYTES} bytes: {path}"
        )
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ConnectorGrantError("connector grant source must be UTF-8 JSON") from error
    except json.JSONDecodeError as error:
        raise ConnectorGrantError(
            f"connector grant source is not valid JSON: {error.msg}"
        ) from error
    if not isinstance(parsed, dict):
        raise ConnectorGrantError("connector grant source must be a JSON object")
    validate_connector_grant_source(parsed)
    return parsed, _source_digest(raw), len(raw)


def load_connector_grant_source(path: str | Path) -> tuple[JsonObject, str, int]:
    """Read and validate one private local connector grant source."""

    return _read_private_manifest(_absolute_local_path(path))


def _stable_uuid(kind: str, *parts: object) -> str:
    value = json.dumps([kind, *parts], sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return str(uuid5(NAMESPACE_URL, f"readin.connector-grant.v0.1:{value}"))


def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ConnectorGrantError(f"invalid timestamp: {value}") from error
    return value


def _utc_timestamp(value: str | datetime | None = None) -> str:
    selected = _parse_timestamp(value) if value is not None else datetime.now(UTC)
    if selected.tzinfo is None or selected.utcoffset() is None:
        raise ConnectorGrantError("timestamps must include a UTC offset")
    return selected.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _source_uri(grant_id: str, source_sha256: str) -> str:
    return f"urn:readin:connector-grant-source:{grant_id}:sha256:{source_sha256}"


def _catalog_binding_for_source(
    source: Mapping[str, Any],
    projection: ReadinProjection,
) -> JsonObject:
    asset = source["asset"]
    entity_id = asset["entity_id"]
    if entity_id not in projection.assets:
        raise ConnectorGrantError(f"connector grant references an untracked asset: {entity_id}")
    entity = projection.entities.get(entity_id)
    if entity is None:
        raise ConnectorGrantError(f"connector grant references an unknown entity: {entity_id}")
    binding = entity["attributes"].get("asset_catalog_binding")
    if not isinstance(binding, dict):
        raise ConnectorGrantError(
            f"connector grant asset was not imported from an asset catalog: {entity_id}"
        )
    mismatches = []
    for field in ("catalog_id", "asset_key", "asset_class", "platform", "account_identifier"):
        if binding.get(field) != asset[field]:
            mismatches.append(f"{field}: expected {binding.get(field)!r}, got {asset[field]!r}")
    if mismatches:
        raise ConnectorGrantError(
            "connector grant asset reference does not match catalog binding: "
            + "; ".join(mismatches)
        )
    if source["owner"]["scope"] != binding["owner_scope"]:
        raise ConnectorGrantError(
            "connector grant owner scope does not match asset catalog binding"
        )
    if source["grant"]["authorization_basis"] != binding["authorization_basis"]:
        raise ConnectorGrantError(
            "connector grant authorization basis does not match asset catalog binding"
        )

    asset_collection_mode = binding["collection_mode"]
    grant_access_mode = source["grant"]["access_mode"]
    allowed = {
        "MANUAL_ENTRY_ONLY": {"MANUAL_ENTRY_ONLY"},
        "LOCAL_EXPORT_IMPORT_ONLY": {"LOCAL_EXPORT_IMPORT_ONLY", "MANUAL_ENTRY_ONLY"},
        "API_CONNECTION_REQUIRES_SEPARATE_GRANT": {
            "API_CONNECTION_REQUIRES_SEPARATE_TOKEN_FLOW",
            "LOCAL_EXPORT_IMPORT_ONLY",
            "MANUAL_ENTRY_ONLY",
        },
    }
    if grant_access_mode not in allowed[asset_collection_mode]:
        raise ConnectorGrantError(
            f"connector grant access mode {grant_access_mode} is not compatible with "
            f"asset collection mode {asset_collection_mode}"
        )
    return binding


def _grant_payload(
    source: Mapping[str, Any],
    *,
    source_sha256: str,
    source_size: int,
    asset_binding: Mapping[str, Any],
) -> JsonObject:
    provider = source["provider"]
    grant = source["grant"]
    asset = source["asset"]
    return {
        "connector_grant": {
            "schema_version": CONNECTOR_GRANT_SCHEMA_VERSION,
            "grant_id": source["grant_id"],
            "declared_at": source["declared_at"],
            "asset_entity_id": asset["entity_id"],
            "catalog_id": asset["catalog_id"],
            "asset_key": asset["asset_key"],
            "asset_class": asset["asset_class"],
            "platform": asset["platform"],
            "account_identifier": asset["account_identifier"],
            "catalog_source_digest_sha256": asset_binding["source_digest_sha256"],
            "source_digest_sha256": source_sha256,
            "source_size": source_size,
            "provider": deepcopy(provider),
            "purpose": deepcopy(source["purpose"]),
            "grant": deepcopy(grant),
            "scopes": deepcopy(source["scopes"]),
            "allowed_observation_types": deepcopy(source["allowed_observation_types"]),
            "retention": deepcopy(source["retention"]),
            "revocation": deepcopy(source["revocation"]),
            "audit": deepcopy(source["audit"]),
            "authority_state": "NO_AUTHORITY",
            "collection_state": grant["collection_state"],
            "credential_material": grant["credential_material"],
            "credential_storage": grant["credential_storage"],
            "oauth_state": grant["oauth_state"],
            "live_collection_state": grant["live_collection_state"],
            "network_access": grant["network_access"],
            "external_action_state": grant["external_action_state"],
            "people_targeting": grant["people_targeting"],
            "activation_requirement": grant["activation_requirement"],
        }
    }


def build_connector_grant_events(
    source: Mapping[str, Any],
    *,
    source_sha256: str,
    source_size: int,
    asset_binding: Mapping[str, Any],
    occurred_at: str | datetime | None = None,
) -> list[JsonObject]:
    """Build deterministic ledger events for one connector grant source."""

    if not isinstance(source, dict):
        raise ConnectorGrantError("connector grant source must be a JSON object")
    validate_connector_grant_source(source)
    event_time = _utc_timestamp(occurred_at) if occurred_at else source["declared_at"]
    grant_id = source["grant_id"]
    asset = source["asset"]
    provider = source["provider"]
    manifest_uri = _source_uri(grant_id, source_sha256)
    frame_id = _stable_uuid("observer-frame", grant_id)
    evidence_id = _stable_uuid("evidence", grant_id, source_sha256)
    observation_id = _stable_uuid("observation", grant_id, source_sha256)
    return [
        create_observer_frame_registered(
            f"Local connector grant manifest: {provider['platform']} {provider['connector_name']}",
            "local_connector_grant_manifest",
            access_scope="USER_OWNED",
            access_description=(
                "One private user-declared connector grant manifest; no account provider "
                "was contacted"
            ),
            measurement_name="user_declared_connector_grant",
            measurement_description=(
                "The operator declared source-readiness and authority limits for one "
                "already tracked asset"
            ),
            granularity_name="one_asset_connector_grant",
            granularity_description="One grant manifest bound to one existing catalog asset",
            interpretation_name="connector_grant_recorded_without_live_collection",
            interpretation_description=(
                "Records scope, minimization, retention, revocation, and disabled "
                "collection controls before any connector can execute"
            ),
            latency_class="UNKNOWN",
            known_blind_regions=(
                "No OAuth token, API session, local export file, account content, private "
                "messages, contacts, social graph, or third-party profile was collected",
                "Provider terms compatibility, source completeness, and account ownership "
                "remain user-attested and not independently verified",
            ),
            validity_conditions=(
                "Asset already exists in the local catalog ledger",
                "Manifest was supplied from a private local regular file",
                "Credentials, OAuth grants, live collection, person targeting, and external "
                "action are absent",
            ),
            frame_id=frame_id,
            event_id=_stable_uuid("event", "observer_frame.registered", grant_id),
            occurred_at=event_time,
        ),
        create_evidence_manifested(
            source_sha256,
            "application/json",
            source_size,
            f"Local connector grant manifest: {provider['platform']} {asset['account_identifier']}",
            source_uri=manifest_uri,
            license_name=None,
            access_policy="USER_OWNED",
            artifact_id=evidence_id,
            acquired_at=event_time,
            event_id=_stable_uuid("event", "evidence.manifested", grant_id, source_sha256),
            occurred_at=event_time,
        ),
        create_observation_admitted(
            (asset["entity_id"],),
            frame_id,
            evidence_id,
            CONNECTOR_GRANT_OBSERVATION_TYPE,
            _grant_payload(
                source,
                source_sha256=source_sha256,
                source_size=source_size,
                asset_binding=asset_binding,
            ),
            source["declared_at"],
            source_uri=manifest_uri,
            source_policy="USER_OWNED",
            collector="readin-connector-grant-import",
            adapter="local-connector-grant-manifest",
            adapter_version=CONNECTOR_GRANT_ADAPTER_VERSION,
            acquisition_time=event_time,
            uncertainty={
                "ownership_verification": "USER_ATTESTED_NOT_VERIFIED",
                "provider_terms": provider["terms_review_state"],
                "connector_execution": "NOT_ENABLED",
                "source_coverage": "NOT_ESTABLISHED",
            },
            missingness_state="OBSERVED",
            observation_id=observation_id,
            event_id=_stable_uuid("event", "observation.admitted", grant_id, source_sha256),
            occurred_at=event_time,
        ),
    ]


def _connector_grant_payload(observation: Mapping[str, Any]) -> JsonObject | None:
    if observation["observation_type"] != CONNECTOR_GRANT_OBSERVATION_TYPE:
        return None
    payload = observation["content"]["structured_payload"]
    grant = payload.get("connector_grant") if isinstance(payload, dict) else None
    return grant if isinstance(grant, dict) else None


def _assert_grant_id_not_reused(
    source: Mapping[str, Any],
    source_sha256: str,
    projection: ReadinProjection,
) -> None:
    grant_id = source["grant_id"]
    for observation in projection.observations.values():
        grant = _connector_grant_payload(observation)
        if grant is None or grant.get("grant_id") != grant_id:
            continue
        if grant.get("source_digest_sha256") != source_sha256:
            raise ConnectorGrantError(
                f"connector grant id already exists with a different source digest: {grant_id}"
            )


def _event_already_present(event: Mapping[str, Any], projection: ReadinProjection) -> bool:
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
            raise ConnectorGrantError(
                f"connector grant source digest is already manifested as {matching[0]['id']}"
            )
        return True
    if event_type == "observation.admitted":
        return payload["observation"]["id"] in projection.observations
    return event["event_id"] in projection.event_ids


def import_connector_grant_source(
    ledger: EventLedger,
    manifest_path: str | Path,
    *,
    attested: bool,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Import a connector grant manifest for an existing catalog asset."""

    if not attested:
        raise ConnectorGrantError(
            "explicit attestation is required for self/controlled assets and "
            "no-live-collection connector limits"
        )
    _reject_git_checkout_path(_absolute_local_path(ledger.path), "connector grant ledger")
    source, source_sha256, source_size = load_connector_grant_source(manifest_path)
    try:
        existing_events = ledger.read_events()
    except LedgerMissing as error:
        raise ConnectorGrantError(
            "connector grant ledger must already contain an asset catalog"
        ) from error
    projection = ReadinProjection.replay(existing_events)
    asset_binding = _catalog_binding_for_source(source, projection)
    _assert_grant_id_not_reused(source, source_sha256, projection)

    candidate_events = build_connector_grant_events(
        source,
        source_sha256=source_sha256,
        source_size=source_size,
        asset_binding=asset_binding,
        occurred_at=occurred_at,
    )
    append_events: list[JsonObject] = []
    for event in candidate_events:
        if _event_already_present(event, projection):
            continue
        try:
            projection.apply(event)
        except ProjectionError as error:
            raise ConnectorGrantError(
                f"connector grant import would violate ledger semantics: {error}"
            ) from error
        append_events.append(event)
    for event in append_events:
        ledger.append(event)

    provider = source["provider"]
    grant = source["grant"]
    return {
        "schema_version": CONNECTOR_GRANT_IMPORT_VERSION,
        "ledger": str(ledger.path),
        "grant_id": source["grant_id"],
        "asset_entity_id": source["asset"]["entity_id"],
        "asset_key": source["asset"]["asset_key"],
        "platform": provider["platform"],
        "connector_kind": provider["connector_kind"],
        "connector_name": provider["connector_name"],
        "grant_kind": grant["grant_kind"],
        "grant_state": grant["grant_state"],
        "access_mode": grant["access_mode"],
        "source_sha256": source_sha256,
        "source_size": source_size,
        "source_path_recorded_in_ledger": False,
        "scope_count": len(source["scopes"]),
        "allowed_observation_type_count": len(source["allowed_observation_types"]),
        "events_appended": len(append_events),
        "events_skipped_existing": len(candidate_events) - len(append_events),
        "authority": {
            "state": "NO_AUTHORITY",
            "collection": grant["collection_state"],
            "network_access": grant["network_access"],
            "credential_material": grant["credential_material"],
            "credential_storage": grant["credential_storage"],
            "oauth_state": grant["oauth_state"],
            "live_collection_state": grant["live_collection_state"],
            "external_actions": grant["external_action_state"],
            "people_targeting": grant["people_targeting"],
            "activation_requirement": grant["activation_requirement"],
        },
    }
