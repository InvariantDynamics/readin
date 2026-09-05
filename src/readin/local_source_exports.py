"""Grant-bound admission of prepared, local profile observations (H3)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from readin.connector_grants import (
    CONNECTOR_GRANT_OBSERVATION_TYPE,
    ConnectorGrantError,
    _absolute_local_path,
    _reject_git_checkout_path,
    _reject_symlink_components,
    _utc_timestamp,
    load_connector_grant_source_schema,
    validate_connector_grant_source,
)
from readin.events import (
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
)
from readin.projection import ReadinProjection
from readin.store import EventLedger, LedgerMissing

JsonObject = dict[str, Any]
LOCAL_SOURCE_EXPORT_SCHEMA_VERSION = "readin.local-source-export.v0.1"
LOCAL_SOURCE_EXPORT_ADAPTER = "local-source-export-batch"
MAX_LOCAL_SOURCE_EXPORT_BYTES = 1_048_576


class LocalSourceExportError(ConnectorGrantError):
    """The local batch cannot be admitted under the recorded grant."""


@lru_cache(maxsize=1)
def load_local_source_export_schema() -> JsonObject:
    resource = files("readin").joinpath("schemas/v0.1/local-source-export.schema.json")
    if resource.is_file():
        return json.loads(resource.read_text(encoding="utf-8"))
    path = Path(__file__).resolve().parents[2] / "schemas/v0.1/local-source-export.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _time(value: str) -> datetime:
    return datetime.fromisoformat(_utc_timestamp(value).replace("Z", "+00:00"))


def validate_local_source_export(source: JsonObject) -> None:
    validator = Draft202012Validator(
        load_local_source_export_schema(), format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(source))
    if errors:
        # Do not echo rejected data: it could contain credentials or private content.
        location = ".".join(str(p) for p in errors[0].absolute_path) or "root"
        raise LocalSourceExportError(f"invalid local export at {location} ({errors[0].validator})")
    keys = [row["record_key"] for row in source["observations"]]
    if len(keys) != len(set(keys)):
        raise LocalSourceExportError("duplicate record_key in local export")
    for row in source["observations"]:
        if _time(row["observed_at"]) > _time(source["prepared_at"]):
            raise LocalSourceExportError("observed_at must not follow prepared_at")
        url = row["structured_payload"].get("profile_url")
        if url:
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise LocalSourceExportError(
                    "profile_url must be HTTPS without credentials, query, or fragment"
                )


def _strict_object(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise LocalSourceExportError("duplicate JSON key in local export")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise LocalSourceExportError("non-finite JSON values are prohibited")


def read_private_source_bytes(
    path: str | Path, *, max_bytes: int = MAX_LOCAL_SOURCE_EXPORT_BYTES
) -> bytes:
    """Read one bounded private source, without interpreting or retaining its path."""
    path = _absolute_local_path(path)
    _reject_symlink_components(path, "local export")
    _reject_git_checkout_path(path, "local export")
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise LocalSourceExportError("local export must be a regular file")
        if stat.S_IMODE(before.st_mode) & 0o077 or before.st_uid != os.geteuid():
            raise LocalSourceExportError("local export must be owner-only and owned by this user")
        if before.st_size > max_bytes:
            raise LocalSourceExportError(f"local export exceeds {max_bytes} bytes")
        flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or not stat.S_ISREG(opened.st_mode)
                or stat.S_IMODE(opened.st_mode) & 0o077
                or opened.st_uid != os.geteuid()
            ):
                raise LocalSourceExportError("local export changed while opening")
            raw = stream.read(max_bytes + 1)
            after = os.fstat(stream.fileno())
            if (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns) != (
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise LocalSourceExportError("local export changed while reading")
    except OSError as error:
        raise LocalSourceExportError("could not read private local export") from error
    if len(raw) > max_bytes:
        raise LocalSourceExportError(f"local export exceeds {max_bytes} bytes")
    return raw


def load_local_source_export(path: str | Path) -> tuple[JsonObject, str, int]:
    raw = read_private_source_bytes(path)
    try:
        source = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_strict_object, parse_constant=_reject_constant
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise LocalSourceExportError("local export must be valid UTF-8 JSON") from error
    validate_local_source_export(source)
    return source, hashlib.sha256(raw).hexdigest(), len(raw)


def _id(kind: str, *parts: object) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps([LOCAL_SOURCE_EXPORT_SCHEMA_VERSION, kind, *parts])))


def _matching_grant(
    source: JsonObject,
    projection: ReadinProjection,
    *,
    asset_class: str = "SOCIAL_ACCOUNT",
    data_category: str = "ACCOUNT_PROFILE_METADATA",
    observation_type: str = "social.profile_metadata",
    validate_profile: bool = True,
) -> tuple[JsonObject, JsonObject]:
    matches = []
    for observation in projection.observations.values():
        if observation["observation_type"] != CONNECTOR_GRANT_OBSERVATION_TYPE:
            continue
        grant = observation["content"]["structured_payload"].get("connector_grant", {})
        if isinstance(grant, dict) and grant.get("grant_id") == source["grant_id"]:
            matches.append((observation, grant))
    if len(matches) != 1:
        raise LocalSourceExportError("exactly one matching recorded connector grant is required")
    observation, grant = matches[0]
    if grant.get("authority_state") != "NO_AUTHORITY":
        raise LocalSourceExportError("recorded grant authority is incompatible")
    asset_id = source["asset_entity_id"]
    if grant.get("asset_entity_id") != asset_id or observation["subject_entities"] != [asset_id]:
        raise LocalSourceExportError("export asset does not match connector grant")
    if asset_id not in projection.assets:
        raise LocalSourceExportError("export asset is not tracked")
    binding = projection.entities[asset_id]["attributes"].get("asset_catalog_binding", {})
    if not isinstance(binding, dict):
        raise LocalSourceExportError("asset has no valid catalog binding")
    for field in ("catalog_id", "asset_key", "asset_class", "platform", "account_identifier"):
        if grant.get(field) != binding.get(field) or field not in binding:
            raise LocalSourceExportError("grant does not match current catalog binding")
    if binding["asset_class"] != asset_class:
        raise LocalSourceExportError(f"this parser requires a {asset_class} asset")
    if binding["collection_mode"] not in {
        "LOCAL_EXPORT_IMPORT_ONLY",
        "API_CONNECTION_REQUIRES_SEPARATE_GRANT",
    }:
        raise LocalSourceExportError("catalog does not permit local export import")
    definitions = load_connector_grant_source_schema()["$defs"]
    for name, definition in (
        ("grant", "grant"),
        ("provider", "provider"),
        ("retention", "retention"),
    ):
        schema = {"$ref": f"#/$defs/{definition}", "$defs": definitions}
        if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(
            grant.get(name)
        ):
            raise LocalSourceExportError(f"recorded grant has invalid {name} controls")
    controls = grant["grant"]
    reconstructed = {
        key: deepcopy(grant.get(key))
        for key in (
            "schema_version",
            "grant_id",
            "declared_at",
            "provider",
            "purpose",
            "grant",
            "scopes",
            "allowed_observation_types",
            "retention",
            "revocation",
            "audit",
        )
    }
    reconstructed.update(
        {
            "asset": {
                "entity_id": asset_id,
                **{
                    key: binding[key]
                    for key in (
                        "catalog_id",
                        "asset_key",
                        "asset_class",
                        "platform",
                        "account_identifier",
                    )
                },
            },
            "owner": {
                "label": "Recorded asset owner",
                "scope": binding["owner_scope"],
                "attestation": "USER_ATTESTED_NOT_VERIFIED",
            },
            "authority": {
                "state": "NO_AUTHORITY",
                "collection": "NOT_STARTED",
                "external_actions": "PROHIBITED",
                "credential_storage": "PROHIBITED",
                "network_access": False,
                "people_targeting": "PROHIBITED",
            },
            "source": {
                "kind": "USER_DECLARED_LOCAL_GRANT_MANIFEST",
                "network_access": False,
                "credential_material": "ABSENT",
                "path_retention": "NOT_RECORDED_IN_LEDGER",
            },
        }
    )
    try:
        validate_connector_grant_source(reconstructed)
    except ConnectorGrantError as error:
        raise LocalSourceExportError("recorded grant violates its source contract") from error
    for key in (
        "collection_state",
        "credential_material",
        "credential_storage",
        "oauth_state",
        "live_collection_state",
        "network_access",
        "external_action_state",
        "people_targeting",
        "activation_requirement",
    ):
        if grant.get(key) != controls[key]:
            raise LocalSourceExportError("recorded grant controls are inconsistent")
    if (
        controls["grant_kind"] != "LOCAL_EXPORT_ONLY"
        or controls["access_mode"] != "LOCAL_EXPORT_IMPORT_ONLY"
    ):
        raise LocalSourceExportError(
            "a LOCAL_EXPORT_ONLY grant is required; API readiness is insufficient"
        )
    if controls["authorization_basis"] != binding["authorization_basis"]:
        raise LocalSourceExportError("grant authorization basis does not match asset")
    if grant["retention"]["raw_export_retention"] != "USER_MANAGED_NOT_RECORDED":
        raise LocalSourceExportError(
            "this importer requires USER_MANAGED_NOT_RECORDED raw retention"
        )
    eligible_scopes = [
        s
        for s in grant.get("scopes", [])
        if (
            s.get("data_category") == data_category
            and s.get("minimization") == "MINIMUM_NECESSARY"
            and s.get("private_counterparty_data") == "EXCLUDED"
            and s.get("claim_extraction") == "PROHIBITED"
        )
    ]
    outputs = [
        o
        for o in grant.get("allowed_observation_types", [])
        if (
            o.get("observation_type") == observation_type
            and o.get("admission_state") == "CONTRACTED_NOT_ENABLED"
            and o.get("claim_extraction") == "PROHIBITED"
            and o.get("external_action_state") == "PROHIBITED"
        )
    ]
    if not eligible_scopes or len(outputs) != 1:
        raise LocalSourceExportError("grant must contract the parser's metadata scope and output")
    evidence = projection.evidence[observation["source_artifact_id"]]
    frame = projection.frames[observation["observer_frame_id"]]
    expected_uri = (
        f"urn:readin:connector-grant-source:{source['grant_id']}:"
        f"sha256:{grant.get('source_digest_sha256')}"
    )
    if (
        evidence["sha256"] != grant.get("source_digest_sha256")
        or evidence["source"]["uri"] != expected_uri
        or observation["provenance"]["source_uri"] != expected_uri
        or observation["provenance"]["adapter"] != "local-connector-grant-manifest"
        or frame["class"] != "local_connector_grant_manifest"
        or grant.get("catalog_source_digest_sha256") != binding["source_digest_sha256"]
    ):
        raise LocalSourceExportError("grant evidence digest mismatch")
    for row in source["observations"] if validate_profile else []:
        record = row["structured_payload"]
        if any(record[field] != binding[field] for field in ("platform", "account_identifier")):
            raise LocalSourceExportError("profile record does not match the catalog account")
        if "profile_url" in record and record["profile_url"] != binding.get("source_uri"):
            raise LocalSourceExportError("profile_url does not match the catalog source URI")
    return observation, grant


def build_local_source_export_events(
    source: JsonObject,
    *,
    source_sha256: str,
    source_size: int,
    projection: ReadinProjection,
    occurred_at: str | datetime | None = None,
) -> list[JsonObject]:
    """Validate the grant and build a deterministic frame, manifest, and observation batch."""
    validate_local_source_export(source)
    grant_observation, grant = _matching_grant(source, projection)
    event_time = _utc_timestamp(occurred_at)
    if _time(source["prepared_at"]) > _time(event_time) or _time(grant["declared_at"]) > _time(
        event_time
    ):
        raise LocalSourceExportError("import time must follow preparation and grant declaration")
    export_id = source["export_id"]
    prefix = f"urn:readin:local-source-export:{export_id}:sha256:"
    source_uri = prefix + source_sha256
    for artifact in projection.evidence.values():
        uri = artifact["source"]["uri"] or ""
        if uri.startswith(prefix) and artifact["sha256"] != source_sha256:
            raise LocalSourceExportError("export_id already exists with a different source digest")
    frame_id = _id("frame", export_id)
    evidence_id = _id("evidence", export_id, source_sha256)
    receipt = {
        "schema_version": "readin.local-source-export-import.v0.1",
        "export_id": export_id,
        "grant_id": source["grant_id"],
        "grant_observation_id": grant_observation["id"],
        "grant_source_sha256": grant["source_digest_sha256"],
        "asset_entity_id": source["asset_entity_id"],
        "source_sha256": source_sha256,
        "source_size": source_size,
        "observation_count": len(source["observations"]),
        "parser": source["parser"],
        "parser_version": "0.1.0",
        "source_path_recorded_in_ledger": False,
        "raw_export_retention": "USER_MANAGED_NOT_RECORDED",
        "authority_state": "NO_AUTHORITY",
        "network_access": False,
    }
    events = [
        create_observer_frame_registered(
            "Prepared local profile export",
            "local_source_export",
            access_scope="USER_OWNED",
            access_description="One operator-supplied prepared local JSON batch",
            measurement_name="local_prepared_profile_records",
            measurement_description="Copy allowlisted fields from a user-prepared export batch",
            known_blind_regions=(
                "Provider origin, ownership, completeness, and accuracy are unverified",
                "Missing fields are unknown; rows share one source, not independent observers",
            ),
            validity_conditions=(
                "Matching local export grant and catalog account",
                "Operator excludes credentials and counterparty data",
                source_uri,
            ),
            frame_id=frame_id,
            event_id=_id("frame-event", export_id),
            occurred_at=event_time,
        ),
        create_evidence_manifested(
            source_sha256,
            "application/json",
            source_size,
            "Prepared local profile export",
            source_uri=source_uri,
            access_policy="USER_OWNED",
            artifact_id=evidence_id,
            event_id=_id("evidence-event", export_id, source_sha256),
            occurred_at=event_time,
        ),
    ]
    for row in source["observations"]:
        events.append(
            create_observation_admitted(
                (source["asset_entity_id"],),
                frame_id,
                evidence_id,
                row["observation_type"],
                {
                    "source_export": {**receipt, "record_key": row["record_key"]},
                    "record": deepcopy(row["structured_payload"]),
                },
                row["observed_at"],
                source_uri=source_uri,
                source_policy="USER_OWNED",
                collector="readin-local-source-export-import",
                adapter=LOCAL_SOURCE_EXPORT_ADAPTER,
                uncertainty={
                    "source_origin": "USER_SUPPLIED_NOT_VERIFIED",
                    "source_coverage": "NOT_ESTABLISHED",
                    "missing_fields": "UNKNOWN",
                    "claim_extraction": "PROHIBITED",
                    "provider_terms": grant["provider"]["terms_review_state"],
                },
                observation_id=_id("observation", export_id, source_sha256, row["record_key"]),
                event_id=_id("observation-event", export_id, source_sha256, row["record_key"]),
                occurred_at=event_time,
            )
        )
    return events


def import_local_source_export(
    ledger: EventLedger,
    source_path: str | Path,
    *,
    grant_id: str,
    attested: bool = False,
    preview: bool = False,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    """Preview or admit one prepared batch; preview never writes the ledger."""
    if not preview and not attested:
        raise LocalSourceExportError(
            "explicit attestation is required; inspect with --preview first"
        )
    _reject_git_checkout_path(_absolute_local_path(ledger.path), "local export ledger")
    _reject_symlink_components(_absolute_local_path(ledger.path), "local export ledger")
    source, digest, size = load_local_source_export(source_path)
    if source["grant_id"] != grant_id:
        raise LocalSourceExportError("--grant does not match the export grant_id")
    try:
        existing = ledger.read_events()
    except LedgerMissing as error:
        raise LocalSourceExportError(
            "ledger must already contain the catalog and local export grant"
        ) from error
    projection = ReadinProjection.replay(existing)
    events = build_local_source_export_events(
        source,
        source_sha256=digest,
        source_size=size,
        projection=projection,
        occurred_at=occurred_at,
    )
    existing_by_id = {e["event_id"]: e for e in existing}
    original_by_time: dict[str, dict[str, JsonObject]] = {}
    pending = []
    for event in events:
        old = existing_by_id.get(event["event_id"])
        if old is not None:
            # Retry timestamps may differ; compare using the original time.
            old_time = old["occurred_at"]
            if old_time not in original_by_time:
                original_by_time[old_time] = {
                    e["event_id"]: e
                    for e in build_local_source_export_events(
                        source,
                        source_sha256=digest,
                        source_size=size,
                        projection=projection,
                        occurred_at=old_time,
                    )
                }
            expected = original_by_time[old_time][event["event_id"]]
            if old != expected:
                raise LocalSourceExportError("existing export event conflicts with prepared source")
            continue
        projection.apply(event)
        pending.append(event)
    if not preview and pending:
        ledger.append_batch(pending)
    receipt = deepcopy(
        events[-1]["payload"]["observation"]["content"]["structured_payload"]["source_export"]
    )
    receipt.pop("record_key")
    return {
        **receipt,
        "status": "PREVIEW" if preview else "IMPORTED" if pending else "ALREADY_IMPORTED",
        "events_appended": 0 if preview else len(pending),
        "events_to_append": len(pending) if preview else 0,
        "events_skipped_existing": len(events) - len(pending),
        "observation_ids": [e["payload"]["observation"]["id"] for e in events[2:]],
        "observation_types": sorted({r["observation_type"] for r in source["observations"]}),
        "admitted_fields": sorted(
            {k for r in source["observations"] for k in r["structured_payload"]}
        ),
    }
