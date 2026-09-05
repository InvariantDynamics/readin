"""Native local export parsers and grant-bound admission, without provider requests."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import stat
import unicodedata
import zipfile
import zlib
from copy import deepcopy
from datetime import datetime
from functools import lru_cache
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from jsonschema import Draft202012Validator, FormatChecker

from readin.connector_grants import (
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
from readin.github_public import GitHubPublicError, parse_public_repository_response
from readin.local_source_exports import (
    LocalSourceExportError,
    _matching_grant,
    _time,
    read_private_source_bytes,
)
from readin.projection import ReadinProjection
from readin.store import EventLedger, LedgerMissing

JsonObject = dict[str, Any]
NATIVE_SOURCE_ADAPTER = "native-local-source-export"
PARSER_VERSION = "0.1.0"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 1024 * 1024
MAX_ARCHIVE_ENTRIES = 2048
PARSERS = {
    "LINKEDIN_PROFILE_CSV": {
        "label": "LinkedIn Profile.csv",
        "asset_class": "SOCIAL_ACCOUNT",
        "platform": "LinkedIn",
        "data_category": "ACCOUNT_PROFILE_METADATA",
        "observation_type": "social.profile_metadata",
        "media_type": "text/csv",
        "max_bytes": MAX_MEMBER_BYTES,
    },
    "LINKEDIN_PROFILE_ZIP": {
        "label": "LinkedIn ZIP (Profile.csv only)",
        "asset_class": "SOCIAL_ACCOUNT",
        "platform": "LinkedIn",
        "data_category": "ACCOUNT_PROFILE_METADATA",
        "observation_type": "social.profile_metadata",
        "media_type": "application/zip",
        "max_bytes": MAX_ARCHIVE_BYTES,
    },
    "GITHUB_REPOSITORY_JSON": {
        "label": "Saved GitHub public repository JSON",
        "asset_class": "SOFTWARE_REPOSITORY",
        "platform": "GitHub",
        "data_category": "OWNED_REPOSITORY_METADATA",
        "observation_type": "github.public_repository_metadata.imported",
        "media_type": "application/json",
        "max_bytes": MAX_MEMBER_BYTES,
    },
    "DOCUMENT_COLLECTION_ZIP": {
        "label": "Document ZIP inventory (metadata only)",
        "asset_class": "DOCUMENT_COLLECTION",
        "platform": None,
        "data_category": "OWNED_DOCUMENT_METADATA",
        "observation_type": "document.inventory_metadata.imported",
        "media_type": "application/zip",
        "max_bytes": MAX_ARCHIVE_BYTES,
    },
    "LOCAL_FILE_COLLECTION_ZIP": {
        "label": "Local-file ZIP inventory (metadata only)",
        "asset_class": "LOCAL_FILE_COLLECTION",
        "platform": None,
        "data_category": "OWNED_DOCUMENT_METADATA",
        "observation_type": "file.inventory_metadata.imported",
        "media_type": "application/zip",
        "max_bytes": MAX_ARCHIVE_BYTES,
    },
}
INVENTORY_PARSERS = frozenset({"DOCUMENT_COLLECTION_ZIP", "LOCAL_FILE_COLLECTION_ZIP"})
INVENTORY_EXCLUDED_FIELDS = (
    "date_time",
    "compress_type",
    "compress_size",
    "external_attr",
    "internal_attr",
    "comment",
    "extra",
)


class NativeSourceExportError(LocalSourceExportError):
    """A native file cannot be imported under the selected parser and grant."""


@lru_cache(maxsize=1)
def load_native_source_record_schema() -> JsonObject:
    resource = files("readin").joinpath("schemas/v0.1/native-source-record.schema.json")
    if resource.is_file():
        return json.loads(resource.read_text(encoding="utf-8"))
    return json.loads(
        (
            Path(__file__).resolve().parents[2] / "schemas/v0.1/native-source-record.schema.json"
        ).read_text(encoding="utf-8")
    )


def validate_native_source_record(record: JsonObject) -> None:
    validator = Draft202012Validator(
        load_native_source_record_schema(), format_checker=FormatChecker()
    )
    if not validator.is_valid(record):
        raise NativeSourceExportError("native parser output violates the closed record contract")
    if record["parser"] in INVENTORY_PARSERS:
        inventory = record["record"]
        entries = inventory["entries"]
        names = [row["entry_name"] for row in entries]
        keys = [unicodedata.normalize("NFC", name).casefold() for name in names]
        if (
            inventory["file_count"] != len(entries)
            or inventory["total_declared_bytes"] != sum(row["size_bytes"] for row in entries)
            or len(set(keys)) != len(keys)
            or any(not _safe_inventory_name(name) or name.endswith("/") for name in names)
            or any(
                "/".join(key.split("/")[:i]) in keys
                for key in keys
                for i in range(1, len(key.split("/")))
            )
            or record["excluded_field_count"] != len(entries) * len(INVENTORY_EXCLUDED_FIELDS)
            or len(entries) + record["archive_entries_skipped"] > MAX_ARCHIVE_ENTRIES
        ):
            raise NativeSourceExportError("inventory record has inconsistent names or counts")


def parser_spec(parser: str) -> JsonObject:
    if parser not in PARSERS:
        raise NativeSourceExportError("unsupported native parser; use list-source-capabilities")
    return deepcopy(PARSERS[parser])


def prepare_native_source_grant(
    projection: ReadinProjection,
    asset_id: str,
    parser: str,
    *,
    declared_at: str | datetime | None = None,
) -> JsonObject:
    """Print-ready H2 manifest; no file creation, ledger write, or implied terms approval."""
    spec = parser_spec(parser)
    if asset_id not in projection.assets:
        raise NativeSourceExportError("grant template requires a tracked catalog asset")
    binding = projection.entities[asset_id]["attributes"].get("asset_catalog_binding", {})
    if (
        binding.get("asset_class") != spec["asset_class"]
        or (
            spec["platform"] is not None
            and binding.get("platform", "").casefold() != spec["platform"].casefold()
        )
        or binding.get("collection_mode")
        not in {"LOCAL_EXPORT_IMPORT_ONLY", "API_CONNECTION_REQUIRES_SEPARATE_GRANT"}
    ):
        raise NativeSourceExportError("catalog asset does not support this local-export parser")
    definitions = load_connector_grant_source_schema()["$defs"]

    def fixed(name: str) -> JsonObject:
        return {
            key: deepcopy(value["const"])
            for key, value in definitions[name]["properties"].items()
            if "const" in value
        }

    manifest = {
        "schema_version": "readin.connector-grant-source.v0.1",
        "grant_id": str(uuid4()),
        "declared_at": _utc_timestamp(declared_at),
        "owner": {**fixed("owner"), "label": "Local operator"},
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
        "provider": {
            "platform": binding["platform"],
            "connector_kind": "LOCAL_EXPORT",
            "connector_name": spec["label"],
            "connector_version": PARSER_VERSION,
            "terms_review_state": "REQUIRES_REVIEW",
            "terms_reference_uri": None,
        },
        "purpose": {
            **fixed("purpose"),
            "kind": "LOCAL_EXPORT_IMPORT_PREP",
            "statement": f"Import selected metadata through {parser}.",
        },
        "grant": {
            **fixed("grant"),
            "grant_kind": "LOCAL_EXPORT_ONLY",
            "authorization_basis": binding["authorization_basis"],
            "access_mode": "LOCAL_EXPORT_IMPORT_ONLY",
            "oauth_state": "NOT_REQUIRED",
        },
        "authority": fixed("authority"),
        "source": fixed("source"),
        "scopes": [
            {
                **fixed("scope"),
                "scope_name": spec["data_category"].lower(),
                "source_surface": spec["label"],
                "data_category": spec["data_category"],
                "access_intent": "LOCAL_EXPORT_PARSE_ONLY",
            }
        ],
        "allowed_observation_types": [
            {**fixed("allowedObservationType"), "observation_type": spec["observation_type"]}
        ],
        "retention": {
            **fixed("retention"),
            "local_retention_days": 30,
            "raw_export_retention": "USER_MANAGED_NOT_RECORDED",
        },
        "revocation": {
            **fixed("revocation"),
            "state": "MANUAL_REVOCATION_REQUIRED_IF_ACTIVATED",
            "operator_action": (
                "Stop invoking the importer. Admitted observations remain in the ledger."
            ),
        },
        "audit": fixed("audit"),
    }
    validate_connector_grant_source(manifest)
    return manifest


def _profile_csv(raw: bytes) -> tuple[JsonObject, int]:
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        if "\x00" in text:
            raise NativeSourceExportError("Profile.csv contains a NUL byte")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        header = next(reader, None)
        if header is None or len(header) > 128 or len(set(header)) != len(header):
            raise NativeSourceExportError("Profile.csv requires unique column headers")
        if not {"First Name", "Last Name"}.issubset(header):
            raise NativeSourceExportError(
                "unsupported Profile.csv layout: First Name and Last Name required"
            )
        rows = [row for row in reader if row]
        if len(rows) != 1 or len(rows[0]) != len(header):
            raise NativeSourceExportError(
                "Profile.csv must contain exactly one complete profile row"
            )
        names = [rows[0][header.index(field)].strip() for field in ("First Name", "Last Name")]
        display_name = " ".join(part for part in names if part)
        if not display_name or len(display_name) > 160 or any(ord(c) < 32 for c in display_name):
            raise NativeSourceExportError("Profile.csv has an invalid display name")
        return {"display_name": display_name}, len(header) - 2
    except (UnicodeError, csv.Error) as error:
        raise NativeSourceExportError("Profile.csv must be well-formed UTF-8 CSV") from error


def _profile_from_zip(raw: bytes) -> tuple[bytes, int]:
    """Read exactly one Profile.csv in memory; never extract or read unrelated members."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_ARCHIVE_ENTRIES:
                raise NativeSourceExportError("archive exceeds 2048 entries")
            profiles = []
            for entry in entries:
                path = PurePosixPath(entry.filename)
                mode = entry.external_attr >> 16
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or "\\" in entry.filename
                    or ":" in entry.filename
                    or "\x00" in entry.orig_filename
                    or stat.S_ISLNK(mode)
                ):
                    raise NativeSourceExportError(
                        "archive contains an unsafe member path or symlink"
                    )
                if path.name.casefold() == "profile.csv" and not entry.is_dir():
                    profiles.append(entry)
            if len(profiles) != 1:
                raise NativeSourceExportError("archive must contain exactly one Profile.csv")
            entry = profiles[0]
            if (
                entry.flag_bits & 1
                or entry.file_size > MAX_MEMBER_BYTES
                or entry.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                or entry.file_size > max(entry.compress_size, 1) * 100
            ):
                raise NativeSourceExportError(
                    "Profile.csv is encrypted, oversized, or over-compressed"
                )
            with archive.open(entry) as stream:
                selected = stream.read(MAX_MEMBER_BYTES + 1)
            if len(selected) > MAX_MEMBER_BYTES or len(selected) != entry.file_size:
                raise NativeSourceExportError("Profile.csv exceeds its declared size")
            return selected, len(entries) - 1
    except (
        zipfile.BadZipFile,
        NotImplementedError,
        RuntimeError,
        EOFError,
        OSError,
        zlib.error,
    ) as error:
        if isinstance(error, NativeSourceExportError):
            raise
        raise NativeSourceExportError(
            "could not read the bounded Profile.csv archive member"
        ) from error


def _safe_inventory_name(name: str) -> bool:
    return (
        bool(name)
        and len(name) <= 512
        and not (
            any(part in {"", ".", ".."} for part in name.removesuffix("/").split("/"))
            or "\\" in name
            or ":" in name
            or any(unicodedata.category(c).startswith("C") for c in name)
        )
    )


def _zip_inventory(raw: bytes) -> tuple[JsonObject, int]:
    """Inventory central-directory metadata only. Never open/decompress a member."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_ENTRIES:
                raise NativeSourceExportError("inventory archive exceeds 2048 entries")
            rows = []
            seen = set()
            directories = 0
            for entry in members:
                name = entry.orig_filename
                mode = entry.external_attr >> 16
                if (
                    not _safe_inventory_name(name)
                    or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}
                    or (stat.S_ISDIR(mode) and not entry.is_dir())
                    or (stat.S_ISREG(mode) and entry.is_dir())
                ):
                    raise NativeSourceExportError("inventory contains an unsafe entry name or type")
                # Case/Unicode aliases are ambiguous across common Mac filesystems.
                key = unicodedata.normalize("NFC", name.removesuffix("/")).casefold()
                if key in seen:
                    raise NativeSourceExportError(
                        "inventory contains duplicate or ambiguous entries"
                    )
                seen.add(key)
                if entry.flag_bits & 1:
                    raise NativeSourceExportError("encrypted inventory entries are unsupported")
                if entry.is_dir():
                    if entry.file_size != 0:
                        raise NativeSourceExportError("inventory directory declares file content")
                    directories += 1
                    continue
                rows.append(
                    {
                        "entry_name": name,
                        "size_bytes": entry.file_size,
                        "crc32": f"{entry.CRC:08x}",
                    }
                )
            if not rows:
                raise NativeSourceExportError("inventory requires at least one file entry")
            file_keys = {unicodedata.normalize("NFC", row["entry_name"]).casefold() for row in rows}
            for key in seen:
                parts = key.split("/")
                if any("/".join(parts[:i]) in file_keys for i in range(1, len(parts))):
                    raise NativeSourceExportError("inventory file conflicts with a directory path")
            return {
                "inventory_kind": "ZIP_CENTRAL_DIRECTORY_METADATA",
                "content_verification": "NOT_PERFORMED",
                "file_count": len(rows),
                "total_declared_bytes": sum(row["size_bytes"] for row in rows),
                "entries": sorted(rows, key=lambda row: row["entry_name"]),
            }, directories
    except (zipfile.BadZipFile, UnicodeError, OSError, EOFError, ValueError) as error:
        if isinstance(error, NativeSourceExportError):
            raise
        raise NativeSourceExportError("could not read inventory ZIP metadata") from error


def parse_native_source(raw: bytes, parser: str, binding: JsonObject) -> JsonObject:
    spec = parser_spec(parser)
    if binding.get("asset_class") != spec["asset_class"] or (
        spec["platform"] is not None
        and binding.get("platform", "").casefold() != spec["platform"].casefold()
    ):
        raise NativeSourceExportError("parser does not match catalog asset class and platform")
    if len(raw) > spec["max_bytes"]:
        raise NativeSourceExportError("native source exceeds parser byte limit")
    result = {
        "schema_version": "readin.native-source-record.v0.1",
        "parser": parser,
        "archive_entries_skipped": 0,
        "selected_member_sha256": None,
    }
    if parser.startswith("LINKEDIN_PROFILE_"):
        selected = raw
        if parser == "LINKEDIN_PROFILE_ZIP":
            selected, result["archive_entries_skipped"] = _profile_from_zip(raw)
            result["selected_member_sha256"] = hashlib.sha256(selected).hexdigest()
        result["record"], result["excluded_field_count"] = _profile_csv(selected)
        result["selected_source_fields"] = ["First Name", "Last Name"]
        result["identity_binding"] = "USER_ATTESTED_CATALOG_ASSOCIATION"
    elif parser == "GITHUB_REPOSITORY_JSON":
        parts = binding.get("account_identifier", "").split("/")
        if len(parts) != 2:
            raise NativeSourceExportError(
                "GitHub catalog account_identifier must be owner/repository"
            )
        try:
            payload, normalized = parse_public_repository_response(raw, *parts)
        except GitHubPublicError as error:
            raise NativeSourceExportError(str(error)) from error
        if binding.get("source_uri") != payload["html_url"]:
            raise NativeSourceExportError("repository URL does not match catalog source URI")
        fields = load_native_source_record_schema()["$defs"]["repository"]["properties"]
        result["record"] = {
            key: value for key, value in normalized["repository"].items() if key in fields
        }
        result["selected_source_fields"] = sorted(result["record"])
        result["excluded_field_count"] = len(payload) - len(result["record"])
        result["identity_binding"] = "SOURCE_IDENTIFIER_MATCHED_NOT_AUTHENTICATED"
    elif parser in INVENTORY_PARSERS:
        result["record"], result["archive_entries_skipped"] = _zip_inventory(raw)
        result["selected_source_fields"] = ["filename", "file_size", "CRC"]
        # Count these named exclusions, not every ZIP-format field or excluded byte.
        result["excluded_field_count"] = result["record"]["file_count"] * len(
            INVENTORY_EXCLUDED_FIELDS
        )
        result["identity_binding"] = "USER_ATTESTED_CATALOG_ASSOCIATION"
    validate_native_source_record(result)
    return result


def _id(kind: str, *parts: Any) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            json.dumps(["readin.native-source-import.v0.1", kind, *parts], sort_keys=True),
        )
    )


def _build_events(
    parsed: JsonObject,
    grant_observation: JsonObject,
    grant: JsonObject,
    *,
    source_sha256: str,
    source_size: int,
    observed_at: str,
    occurred_at: str,
) -> list[JsonObject]:
    parser = parsed["parser"]
    spec = parser_spec(parser)
    # Same file under this grant/parser is one import, even if retried with a changed timestamp.
    export_id = _id("export", grant_observation["id"], parser, source_sha256)
    uri = f"urn:readin:native-source-export:{export_id}:sha256:{source_sha256}"
    frame_id, evidence_id = _id("frame", export_id), _id("evidence", export_id)
    receipt = {
        "schema_version": "readin.native-source-import.v0.1",
        "export_id": export_id,
        "grant_id": grant["grant_id"],
        "grant_observation_id": grant_observation["id"],
        "grant_source_sha256": grant["source_digest_sha256"],
        "asset_entity_id": grant["asset_entity_id"],
        "source_sha256": source_sha256,
        "source_size": source_size,
        "observation_count": 1,
        "parser": parser,
        "parser_version": PARSER_VERSION,
        "source_path_recorded_in_ledger": False,
        "raw_export_retention": "USER_MANAGED_NOT_RECORDED",
        "authority_state": "NO_AUTHORITY",
        "network_access": False,
        "identity_binding": parsed["identity_binding"],
        "observed_time_basis": "USER_DECLARED_EXPORT_TIME",
        "selected_source_fields": parsed["selected_source_fields"],
        "excluded_field_count": parsed["excluded_field_count"],
        "archive_entries_skipped": parsed["archive_entries_skipped"],
        "selected_member_sha256": parsed["selected_member_sha256"],
    }
    inventory = parser in INVENTORY_PARSERS
    if inventory:
        receipt.update(
            {
                "archive_entry_names_recorded": True,
                "file_entry_count": parsed["record"]["file_count"],
                "member_content_read": False,
                "content_verification": "NOT_PERFORMED",
                "excluded_field_count_basis": "SEVEN_UNSELECTED_ZIPINFO_FIELDS_PER_FILE",
                "excluded_source_fields": list(INVENTORY_EXCLUDED_FIELDS),
            }
        )
    return [
        create_observer_frame_registered(
            spec["label"],
            "native_local_source_export",
            access_scope="USER_OWNED",
            access_description="One user-selected local export; no provider request",
            measurement_name=parser.lower(),
            measurement_description="Select contracted fields from native export bytes",
            interpretation_name="source_reported_metadata",
            interpretation_description="Record source values with explicit catalog association",
            known_blind_regions=(
                "Provider origin and ownership are not independently authenticated",
                "Unselected fields and archive members provide no coverage",
                "Observation time is supplied by the operator",
            )
            + (
                ("ZIP sizes and CRC32 are archive-declared, not verified file contents",)
                if inventory
                else ()
            ),
            validity_conditions=(uri, parsed["identity_binding"]),
            frame_id=frame_id,
            event_id=_id("frame-event", export_id),
            occurred_at=occurred_at,
        ),
        create_evidence_manifested(
            source_sha256,
            spec["media_type"],
            source_size,
            spec["label"],
            source_uri=uri,
            access_policy="USER_OWNED",
            artifact_id=evidence_id,
            event_id=_id("evidence-event", export_id),
            occurred_at=occurred_at,
        ),
        create_observation_admitted(
            (grant["asset_entity_id"],),
            frame_id,
            evidence_id,
            spec["observation_type"],
            {"source_export": receipt, "record": deepcopy(parsed["record"])},
            observed_at,
            source_uri=uri,
            source_policy="USER_OWNED",
            collector="readin-native-source-import",
            adapter=NATIVE_SOURCE_ADAPTER,
            adapter_version=PARSER_VERSION,
            uncertainty={
                "source_origin": "USER_SUPPLIED_NOT_AUTHENTICATED",
                "source_coverage": "SELECTED_FIELDS_ONLY",
                "identity_binding": parsed["identity_binding"],
                "observed_time_basis": "USER_DECLARED_EXPORT_TIME",
                "missing_fields": "UNKNOWN",
                "claim_extraction": "PROHIBITED",
            },
            observation_id=_id("observation", export_id),
            event_id=_id("observation-event", export_id),
            occurred_at=occurred_at,
        ),
    ]


def native_grant(
    projection: ReadinProjection, grant_id: str, asset_id: str, parser: str
) -> tuple[JsonObject, JsonObject]:
    spec = parser_spec(parser)
    observation, grant = _matching_grant(
        {"grant_id": grant_id, "asset_entity_id": asset_id},
        projection,
        asset_class=spec["asset_class"],
        data_category=spec["data_category"],
        observation_type=spec["observation_type"],
        validate_profile=False,
    )
    if spec["platform"] is not None and grant["platform"].casefold() != spec["platform"].casefold():
        raise NativeSourceExportError("parser platform does not match grant")
    return observation, grant


def import_native_source_export(
    ledger: EventLedger,
    source_path: str | Path,
    *,
    parser: str,
    asset_id: str,
    grant_id: str,
    observed_at: str,
    preview: bool = False,
    attested: bool = False,
    occurred_at: str | datetime | None = None,
) -> JsonObject:
    if not preview and not attested:
        raise NativeSourceExportError(
            "explicit attestation is required; inspect with --preview first"
        )
    spec = parser_spec(parser)
    _reject_git_checkout_path(_absolute_local_path(ledger.path), "native export ledger")
    _reject_symlink_components(_absolute_local_path(ledger.path), "native export ledger")
    try:
        existing = ledger.read_events()
    except LedgerMissing as error:
        raise NativeSourceExportError(
            "ledger must already contain a catalog and local export grant"
        ) from error
    projection = ReadinProjection.replay(existing)
    grant_observation, grant = native_grant(projection, grant_id, asset_id, parser)
    event_time, observed_at = _utc_timestamp(occurred_at), _utc_timestamp(observed_at)
    if _time(observed_at) > _time(event_time) or _time(grant["declared_at"]) > _time(event_time):
        raise NativeSourceExportError("import must follow observed time and grant declaration")
    raw = read_private_source_bytes(source_path, max_bytes=spec["max_bytes"])
    digest = hashlib.sha256(raw).hexdigest()
    binding = projection.entities[asset_id]["attributes"]["asset_catalog_binding"]
    parsed = parse_native_source(raw, parser, binding)
    events = _build_events(
        parsed,
        grant_observation,
        grant,
        source_sha256=digest,
        source_size=len(raw),
        observed_at=observed_at,
        occurred_at=event_time,
    )
    existing_by_id = {e["event_id"]: e for e in existing}
    pending = []
    for event in events:
        old = existing_by_id.get(event["event_id"])
        if old is not None:
            original = _build_events(
                parsed,
                grant_observation,
                grant,
                source_sha256=digest,
                source_size=len(raw),
                observed_at=observed_at,
                occurred_at=old["occurred_at"],
            )
            expected = next(e for e in original if e["event_id"] == old["event_id"])
            if expected != old:
                raise NativeSourceExportError(
                    "existing import conflicts; preserve the original observed time"
                )
            continue
        projection.apply(event)
        pending.append(event)
    if pending and not preview:
        ledger.append_batch(pending)
    receipt = deepcopy(
        events[-1]["payload"]["observation"]["content"]["structured_payload"]["source_export"]
    )
    return {
        **receipt,
        "status": "PREVIEW" if preview else "IMPORTED" if pending else "ALREADY_IMPORTED",
        "events_appended": len(pending) if not preview else 0,
        "events_to_append": len(pending) if preview else 0,
        "events_skipped_existing": len(events) - len(pending),
        "observation_ids": [events[-1]["payload"]["observation"]["id"]],
        "record_preview": deepcopy(parsed["record"]),
    }
