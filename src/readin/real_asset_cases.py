"""Policy-bound, owner-local cases for bounded real-asset acquisition."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator, FormatChecker

from readin.events import (
    create_entity_created,
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
    create_tracking_started,
)
from readin.evidence_vault import EvidenceVault, VaultError
from readin.github_public import (
    GitHubPublicError,
    fetch_public_repository,
    parse_public_repository_response,
    validate_public_repository_target,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.store import EventLedger

JsonObject = dict[str, Any]

POLICY_FILENAME = "policy.json"
LEDGER_FILENAME = "events.jsonl"
NETWORK_ATTEMPT_FILENAME = "network-attempt.json"
POLICY_SCHEMA_VERSION = "readin.real-asset-case-policy.v0.1"
ENVELOPE_SCHEMA_VERSION = "readin.real-asset-case-envelope.v0.1"
DEFAULT_MAX_RESPONSE_BYTES = 524_288
MAX_POLICY_BYTES = 131_072


class RealAssetCaseError(RuntimeError):
    """Base error for bounded real-asset cases."""


class RealAssetCaseExists(RealAssetCaseError):
    """Raised when case initialization would reuse an existing path."""


class RealAssetPolicyError(RealAssetCaseError):
    """Raised when a case policy is invalid, altered, or expired."""


class RealAssetAcquisitionError(RealAssetCaseError):
    """Raised when a live acquisition cannot be safely admitted."""


def _utc_timestamp(value: datetime | None = None) -> str:
    selected = value or datetime.now(UTC)
    if selected.tzinfo is None or selected.utcoffset() is None:
        raise ValueError("timestamps must include a UTC offset")
    return selected.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _trusted_utc_now() -> datetime:
    """Read the local process clock for an authorization decision."""

    return datetime.now(UTC)


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise RealAssetPolicyError("policy contains an invalid timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RealAssetPolicyError("policy contains an invalid timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RealAssetPolicyError("policy timestamps must include a UTC offset")
    return parsed.astimezone(UTC)


def _canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _policy_digest(policy: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_bytes(policy)).hexdigest()


def _development_policy_schema_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "schemas"
        / "v0.1"
        / "real-asset-case-policy.schema.json"
    )


@lru_cache(maxsize=1)
def _load_policy_schema() -> JsonObject:
    packaged = files("readin").joinpath("schemas/v0.1/real-asset-case-policy.schema.json")
    if packaged.is_file():
        return json.loads(packaged.read_text(encoding="utf-8"))
    path = _development_policy_schema_path()
    if not path.is_file():
        raise RealAssetPolicyError(f"real-asset policy schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_real_asset_policy_schema() -> JsonObject:
    """Return the closed policy schema used by bounded real-asset cases."""

    return _load_policy_schema()


@lru_cache(maxsize=1)
def _policy_validator() -> Draft202012Validator:
    schema = _load_policy_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_policy(policy: JsonObject) -> None:
    errors = sorted(_policy_validator().iter_errors(policy), key=lambda error: list(error.path))
    if errors:
        messages = []
        for error in errors:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            messages.append(f"{location}: {error.message}")
        raise RealAssetPolicyError("; ".join(messages))

    target = policy["target"]
    github = target["github"]
    try:
        validate_public_repository_target(github["owner"], github["repository"])
    except GitHubPublicError as error:
        raise RealAssetPolicyError(str(error)) from error
    expected_url = f"https://api.github.com/repos/{github['owner']}/{github['repository']}"
    if github["request_url"] != expected_url:
        raise RealAssetPolicyError("policy request URL does not match its exact GitHub target")

    declared_at = _parse_timestamp(policy["declared_at"])
    not_before = _parse_timestamp(policy["budgets"]["collection_not_before"])
    not_after = _parse_timestamp(policy["budgets"]["collection_not_after"])
    delete_at = _parse_timestamp(policy["retention"]["delete_at"])
    if not_before != declared_at:
        raise RealAssetPolicyError("collection window must begin when the policy is declared")
    if not_after <= not_before or not_after - not_before > timedelta(hours=24):
        raise RealAssetPolicyError("collection window must be positive and no longer than 24 hours")
    if delete_at <= declared_at:
        raise RealAssetPolicyError("retention deadline must follow policy declaration")
    if delete_at - declared_at > timedelta(days=policy["retention"]["max_days"]):
        raise RealAssetPolicyError("retention deadline exceeds the declared maximum")


def validate_real_asset_case_policy(policy: JsonObject) -> None:
    """Validate a policy's closed contract and cross-field semantics."""

    _validate_policy(policy)


def _absolute_case_path(case_dir: str | Path) -> Path:
    return Path(case_dir).expanduser().absolute()


def _reject_symlink_components(path: Path) -> None:
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
            raise RealAssetPolicyError(f"case path contains a symbolic link: {component}")


def _ensure_private_case_parent(path: Path) -> None:
    missing: list[Path] = []
    cursor = path
    while True:
        try:
            current = cursor.lstat()
        except FileNotFoundError as error:
            missing.append(cursor)
            if cursor.parent == cursor:
                raise RealAssetPolicyError(
                    f"case parent cannot be created safely: {path}"
                ) from error
            cursor = cursor.parent
            continue
        if stat.S_ISLNK(current.st_mode) or not stat.S_ISDIR(current.st_mode):
            raise RealAssetPolicyError(f"case parent must be a real directory: {cursor}")
        break
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            current = directory.lstat()
            if stat.S_ISLNK(current.st_mode) or not stat.S_ISDIR(current.st_mode):
                raise RealAssetPolicyError(
                    f"case parent must be a real directory: {directory}"
                ) from None
        else:
            os.chmod(directory, 0o700, follow_symlinks=False)


def _reject_git_checkout_path(path: Path) -> None:
    for parent in (path, *path.parents):
        if (parent / ".git").exists():
            raise RealAssetPolicyError("real evidence cases must be stored outside Git checkouts")


def _write_new_private_json(path: Path, value: Mapping[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    encoded = _canonical_bytes(value) + b"\n"
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError as error:
        raise RealAssetCaseExists(f"case file already exists: {path}") from error
    except OSError as error:
        raise RealAssetPolicyError(f"could not create private case file: {path}") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise RealAssetPolicyError(f"case file is not regular: {path}")
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _read_private_json(path: Path, *, label: str = "case policy") -> JsonObject:
    try:
        before = path.lstat()
    except FileNotFoundError as error:
        raise RealAssetPolicyError(f"{label} is missing: {path}") from error
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode):
        raise RealAssetPolicyError(f"{label} must be a regular file: {path}")
    if stat.S_IMODE(before.st_mode) & 0o077:
        raise RealAssetPolicyError(f"{label} is not owner-only: {path}")
    if before.st_uid != os.geteuid():
        raise RealAssetPolicyError(f"{label} is not owned by the current user: {path}")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise RealAssetPolicyError(f"{label} changed while opening: {path}")
        chunks: list[bytes] = []
        total = 0
        while total <= MAX_POLICY_BYTES:
            chunk = os.read(descriptor, min(65_536, MAX_POLICY_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        body = b"".join(chunks)
    finally:
        os.close(descriptor)
    if len(body) > MAX_POLICY_BYTES:
        raise RealAssetPolicyError(f"{label} exceeds the size limit")
    try:
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RealAssetPolicyError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise RealAssetPolicyError(f"{label} must be a JSON object")
    return value


def _case_envelope(policy: JsonObject) -> JsonObject:
    return {
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "policy_sha256": _policy_digest(policy),
        "policy": policy,
    }


def build_github_public_repository_policy(
    owner: str,
    repository: str,
    purpose_statement: str,
    *,
    purpose_kind: str = "SYSTEM_CAPABILITY_EVALUATION",
    subject_class: str = "PUBLIC_ORGANIZATION_ASSET",
    retention_days: int = 30,
    declared_at: datetime | None = None,
    policy_id: str | UUID | None = None,
    case_id: str | UUID | None = None,
    target_id: str | UUID | None = None,
    entity_id: str | UUID | None = None,
    observer_frame_id: str | UUID | None = None,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
) -> JsonObject:
    """Build and validate the fixed H0 public-repository collection policy."""

    try:
        validate_public_repository_target(owner, repository)
    except GitHubPublicError as error:
        raise RealAssetPolicyError(str(error)) from error
    start = declared_at or datetime.now(UTC)
    if start.tzinfo is None or start.utcoffset() is None:
        raise ValueError("declared_at must include a UTC offset")
    if not 1 <= retention_days <= 30:
        raise ValueError("retention_days must be between 1 and 30")
    authorization_basis = (
        "OWNERSHIP_ATTESTED" if subject_class == "USER_OWNED_ASSET" else "PUBLIC_RESOURCE_SCOPE"
    )
    ownership_claim = (
        "USER_ATTESTED_NOT_VERIFIED" if subject_class == "USER_OWNED_ASSET" else "NOT_MADE"
    )
    policy = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_id": str(policy_id or uuid4()),
        "case_id": str(case_id or uuid4()),
        "declared_at": _utc_timestamp(start),
        "purpose": {
            "kind": purpose_kind,
            "statement": purpose_statement,
            "secondary_use": "PROHIBITED",
        },
        "target": {
            "target_id": str(target_id or uuid4()),
            "entity_id": str(entity_id or uuid4()),
            "observer_frame_id": str(observer_frame_id or uuid4()),
            "subject_class": subject_class,
            "asset_type": "SOFTWARE_REPOSITORY",
            "authorization_basis": authorization_basis,
            "ownership_claim": ownership_claim,
            "github": {
                "owner": owner,
                "repository": repository,
                "request_url": f"https://api.github.com/repos/{owner}/{repository}",
            },
        },
        "source": {
            "connector": "GITHUB_PUBLIC_REPOSITORY_V0_1",
            "access_policy": "PUBLIC",
            "allowed_host": "api.github.com",
            "exact_target_only": True,
            "authentication_mode": "NONE",
            "read_only": True,
            "redirect_policy": "DENY",
            "proxy_policy": "DISABLED",
        },
        "budgets": {
            "collection_not_before": _utc_timestamp(start),
            "collection_not_after": _utc_timestamp(start + timedelta(hours=24)),
            "max_network_requests": 1,
            "max_response_bytes": max_response_bytes,
            "max_artifacts": 1,
            "max_relation_hops": 0,
        },
        "retention": {
            "delete_at": _utc_timestamp(start + timedelta(days=retention_days)),
            "max_days": retention_days,
            "auto_extend": False,
            "review_required": True,
        },
        "minimization": {
            "repository_metadata_only": True,
            "contributors": "EXCLUDED",
            "commit_authors": "EXCLUDED",
            "organization_members": "EXCLUDED",
            "issues_and_pull_requests": "EXCLUDED",
            "automatic_external_url_following": "PROHIBITED",
            "coverage_state": "BOUNDED",
            "completeness_claim": "NOT_MADE",
        },
        "authority": {
            "record_authority": "NO_AUTHORITY",
            "collection": "READ_ONLY_EXACT_TARGET",
            "account_mutation": "NONE",
            "contact": "NONE",
            "publication": "NONE",
            "automated_entity_merge": False,
            "consequential_use": "PROHIBITED",
        },
    }
    _validate_policy(policy)
    return policy


def initialize_github_public_repository_case(
    case_dir: str | Path,
    owner: str,
    repository: str,
    purpose_statement: str,
    *,
    attested: bool,
    purpose_kind: str = "SYSTEM_CAPABILITY_EVALUATION",
    subject_class: str = "PUBLIC_ORGANIZATION_ASSET",
    retention_days: int = 30,
    declared_at: datetime | None = None,
) -> JsonObject:
    """Create a one-target case without contacting GitHub."""

    if not attested:
        raise RealAssetPolicyError(
            "explicit attestation is required for the declared target, purpose, and limits"
        )
    path = _absolute_case_path(case_dir)
    _ensure_private_case_parent(path.parent)
    _reject_symlink_components(path.parent)
    _reject_git_checkout_path(path)
    try:
        path.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError as error:
        raise RealAssetCaseExists(f"case directory already exists: {path}") from error
    os.chmod(path, 0o700)

    try:
        policy = build_github_public_repository_policy(
            owner,
            repository,
            purpose_statement,
            purpose_kind=purpose_kind,
            subject_class=subject_class,
            retention_days=retention_days,
            declared_at=declared_at,
        )
        envelope = _case_envelope(policy)
        _write_new_private_json(path / POLICY_FILENAME, envelope)

        target = policy["target"]
        binding = {
            "case_id": policy["case_id"],
            "policy_id": policy["policy_id"],
            "policy_sha256": envelope["policy_sha256"],
            "target_id": target["target_id"],
            "subject_class": target["subject_class"],
            "authorization_basis": target["authorization_basis"],
            "ownership_claim": target["ownership_claim"],
        }
        occurred_at = policy["declared_at"]
        entity_event = create_entity_created(
            f"{owner}/{repository}",
            "SoftwareRepository",
            external_ids=({"scheme": "github_repository", "value": f"{owner}/{repository}"},),
            attributes={"real_asset_case_binding": binding},
            entity_id=target["entity_id"],
            occurred_at=occurred_at,
        )
        tracking_event = create_tracking_started(
            target["entity_id"],
            collection_profile="github_public_repository_v0_1",
            update_policy="manual",
            scopes=("observer_frame", "topic", "temporal"),
            occurred_at=occurred_at,
        )
        frame_event = create_observer_frame_registered(
            "GitHub public repository REST metadata",
            "public_repository_api",
            access_scope="PUBLIC",
            access_description="One credential-free exact-target GitHub REST response",
            measurement_name="github_public_repository_metadata_response",
            measurement_description=(
                "GitHub returned repository metadata; fields are source-reported observations"
            ),
            granularity_name="one_repository_response",
            granularity_description="One response from GET /repos/{owner}/{repository}",
            interpretation_name="bounded_repository_metadata_projection",
            interpretation_description=(
                "Projects an allowlisted repository-level subset without identity inference"
            ),
            latency_class="UNKNOWN",
            known_blind_regions=(
                "No contributors, commit authors, members, issues, pull requests, or private data",
                "No completeness claim beyond one public REST representation",
            ),
            validity_conditions=(
                "HTTP 200 credential-free response from the exact api.github.com endpoint",
                "Response identifies the requested public repository",
            ),
            frame_id=target["observer_frame_id"],
            occurred_at=occurred_at,
        )
        initial_events = [entity_event, tracking_event, frame_event]
        ReadinProjection.replay(initial_events)
        ledger = EventLedger(path / LEDGER_FILENAME)
        ledger.initialize()
        for event in initial_events:
            ledger.append(event)
        EvidenceVault(path).initialize()
        _fsync_directory(path)
    except (RealAssetCaseError, ValueError):
        shutil.rmtree(path, ignore_errors=True)
        raise
    except (OSError, VaultError) as error:
        shutil.rmtree(path, ignore_errors=True)
        raise RealAssetCaseError(
            f"could not initialize private real-asset case: {error}"
        ) from error
    except Exception:
        shutil.rmtree(path, ignore_errors=True)
        raise

    return {
        "case_dir": str(path),
        "case_id": policy["case_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": envelope["policy_sha256"],
        "target_id": policy["target"]["target_id"],
        "entity_id": policy["target"]["entity_id"],
        "observer_frame_id": policy["target"]["observer_frame_id"],
        "ledger": str(path / LEDGER_FILENAME),
        "network_access": "NOT_ATTEMPTED",
        "authority_state": "NO_AUTHORITY",
    }


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise RealAssetPolicyError(f"could not sync case directory: {path}") from error
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            raise RealAssetPolicyError(f"could not sync case directory: {path}") from error
    finally:
        os.close(descriptor)


def load_real_asset_case_policy(case_dir: str | Path) -> tuple[Path, JsonObject, str]:
    """Load, validate, and digest-check an application-write-once case policy."""

    path = _absolute_case_path(case_dir)
    _reject_symlink_components(path)
    try:
        case_stat = path.lstat()
    except FileNotFoundError as error:
        raise RealAssetPolicyError(f"case directory does not exist: {path}") from error
    if not stat.S_ISDIR(case_stat.st_mode) or stat.S_ISLNK(case_stat.st_mode):
        raise RealAssetPolicyError(f"case path must be a directory: {path}")
    if stat.S_IMODE(case_stat.st_mode) & 0o077:
        raise RealAssetPolicyError(f"case directory is not owner-only: {path}")
    if case_stat.st_uid != os.geteuid():
        raise RealAssetPolicyError(f"case directory is not owned by the current user: {path}")
    _reject_git_checkout_path(path)
    ledger_path = path / LEDGER_FILENAME
    try:
        ledger_stat = ledger_path.lstat()
    except FileNotFoundError as error:
        raise RealAssetPolicyError(f"case ledger is missing: {ledger_path}") from error
    if (
        not stat.S_ISREG(ledger_stat.st_mode)
        or stat.S_ISLNK(ledger_stat.st_mode)
        or stat.S_IMODE(ledger_stat.st_mode) & 0o077
        or ledger_stat.st_uid != os.geteuid()
    ):
        raise RealAssetPolicyError(f"case ledger is not a private regular file: {ledger_path}")
    envelope = _read_private_json(path / POLICY_FILENAME)
    if set(envelope) != {"schema_version", "policy_sha256", "policy"}:
        raise RealAssetPolicyError("case policy envelope contains unknown or missing fields")
    if envelope["schema_version"] != ENVELOPE_SCHEMA_VERSION:
        raise RealAssetPolicyError("unsupported case policy envelope version")
    policy = envelope["policy"]
    if not isinstance(policy, dict):
        raise RealAssetPolicyError("case policy must be a JSON object")
    digest = _policy_digest(policy)
    if envelope["policy_sha256"] != digest:
        raise RealAssetPolicyError("case policy digest does not match its content")
    _validate_policy(policy)
    return path, policy, digest


def _validate_collection_window(policy: JsonObject, now: datetime) -> None:
    selected = now.astimezone(UTC)
    not_before = _parse_timestamp(policy["budgets"]["collection_not_before"])
    not_after = _parse_timestamp(policy["budgets"]["collection_not_after"])
    delete_at = _parse_timestamp(policy["retention"]["delete_at"])
    if selected < not_before:
        raise RealAssetPolicyError("case collection window has not opened")
    if selected >= not_after:
        raise RealAssetPolicyError("case collection window has closed")
    if selected >= delete_at:
        raise RealAssetPolicyError("case retention deadline has passed")


def validate_real_asset_case_read_access(
    case_dir: str | Path,
) -> JsonObject | None:
    """Validate immutable case binding and enforce the retention read gate."""

    case_path, policy, policy_digest = load_real_asset_case_policy(case_dir)
    events = EventLedger(case_path / LEDGER_FILENAME).read_events()
    _validate_case_ledger_binding(
        events,
        policy,
        policy_digest,
        allow_collected=True,
    )
    network_attempt = _load_network_attempt_marker(case_path, policy, policy_digest)
    if len(events) == 5:
        _validate_collected_case_evidence(
            case_path,
            events,
            policy,
            policy_digest,
            network_attempt,
        )
    try:
        ReadinProjection.replay(events)
    except ProjectionError as error:
        raise RealAssetPolicyError("case ledger failed semantic replay") from error
    selected = _trusted_utc_now()
    if selected.tzinfo is None or selected.utcoffset() is None:
        raise RealAssetPolicyError("trusted read-access clock must include a UTC offset")
    if selected.astimezone(UTC) >= _parse_timestamp(policy["retention"]["delete_at"]):
        raise RealAssetPolicyError(
            "case retention deadline has passed; normal read and workbench access is blocked"
        )
    return network_attempt


@contextmanager
def _exclusive_case_lock(case_path: Path) -> Iterator[None]:
    lock_path = case_path / ".collection.lock"
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise RealAssetPolicyError("could not open the private case collection lock") from error
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise RealAssetPolicyError("case collection lock is not a regular file")
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _safe_rate_limit(headers: Mapping[str, str]) -> JsonObject:
    return {
        "limit": headers.get("x-ratelimit-limit"),
        "remaining": headers.get("x-ratelimit-remaining"),
        "used": headers.get("x-ratelimit-used"),
        "reset": headers.get("x-ratelimit-reset"),
        "resource": headers.get("x-ratelimit-resource"),
    }


def _validate_case_ledger_binding(
    events: list[JsonObject],
    policy: JsonObject,
    policy_digest: str,
    *,
    allow_collected: bool,
) -> None:
    initialized_types = [
        "entity.created",
        "asset.tracking_started",
        "observer_frame.registered",
    ]
    collected_types = initialized_types + [
        "evidence.manifested",
        "observation.admitted",
    ]
    event_types = [event.get("event_type") for event in events]
    allowed_sequences = [initialized_types]
    if allow_collected:
        allowed_sequences.append(collected_types)
    if event_types not in allowed_sequences:
        raise RealAssetPolicyError(
            "case ledger does not match an allowed policy-bound H0 event sequence"
        )
    if any(event.get("authority_state") != "NO_AUTHORITY" for event in events):
        raise RealAssetPolicyError("case ledger contains an authority-state mismatch")

    target = policy["target"]
    github = target["github"]
    expected_binding = {
        "case_id": policy["case_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": policy_digest,
        "target_id": target["target_id"],
        "subject_class": target["subject_class"],
        "authorization_basis": target["authorization_basis"],
        "ownership_claim": target["ownership_claim"],
    }
    occurred_at = policy["declared_at"]
    expected_entity_event = create_entity_created(
        f"{github['owner']}/{github['repository']}",
        "SoftwareRepository",
        external_ids=(
            {
                "scheme": "github_repository",
                "value": f"{github['owner']}/{github['repository']}",
            },
        ),
        attributes={"real_asset_case_binding": expected_binding},
        entity_id=target["entity_id"],
        event_id=events[0]["event_id"],
        occurred_at=occurred_at,
    )
    if events[0] != expected_entity_event:
        raise RealAssetPolicyError("case ledger entity does not match its policy binding")

    expected_tracking_event = create_tracking_started(
        target["entity_id"],
        collection_profile="github_public_repository_v0_1",
        update_policy="manual",
        scopes=("observer_frame", "topic", "temporal"),
        event_id=events[1]["event_id"],
        occurred_at=occurred_at,
    )
    if events[1] != expected_tracking_event:
        raise RealAssetPolicyError("case ledger tracking state does not match its policy")

    expected_frame_event = create_observer_frame_registered(
        "GitHub public repository REST metadata",
        "public_repository_api",
        access_scope="PUBLIC",
        access_description="One credential-free exact-target GitHub REST response",
        measurement_name="github_public_repository_metadata_response",
        measurement_description=(
            "GitHub returned repository metadata; fields are source-reported observations"
        ),
        granularity_name="one_repository_response",
        granularity_description="One response from GET /repos/{owner}/{repository}",
        interpretation_name="bounded_repository_metadata_projection",
        interpretation_description=(
            "Projects an allowlisted repository-level subset without identity inference"
        ),
        latency_class="UNKNOWN",
        known_blind_regions=(
            "No contributors, commit authors, members, issues, pull requests, or private data",
            "No completeness claim beyond one public REST representation",
        ),
        validity_conditions=(
            "HTTP 200 credential-free response from the exact api.github.com endpoint",
            "Response identifies the requested public repository",
        ),
        frame_id=target["observer_frame_id"],
        event_id=events[2]["event_id"],
        occurred_at=occurred_at,
    )
    if events[2] != expected_frame_event:
        raise RealAssetPolicyError("case ledger observer frame does not match its policy")


def _load_network_attempt_marker(
    case_path: Path,
    policy: JsonObject,
    policy_digest: str,
) -> JsonObject | None:
    marker_path = case_path / NETWORK_ATTEMPT_FILENAME
    try:
        marker_path.lstat()
    except FileNotFoundError:
        return None
    marker = _read_private_json(marker_path, label="network-attempt marker")
    expected_keys = {
        "schema_version",
        "case_id",
        "policy_id",
        "policy_sha256",
        "target_id",
        "authorized_at",
        "method",
        "url",
        "authentication_mode",
        "state",
        "authority_state",
    }
    if set(marker) != expected_keys:
        raise RealAssetPolicyError("network-attempt marker contains unknown or missing fields")
    expected_values = {
        "schema_version": "readin.network-attempt.v0.1",
        "case_id": policy["case_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": policy_digest,
        "target_id": policy["target"]["target_id"],
        "method": "GET",
        "url": policy["target"]["github"]["request_url"],
        "authentication_mode": "NONE",
        "state": "RESERVED_BEFORE_REQUEST",
        "authority_state": "NO_AUTHORITY",
    }
    if any(marker.get(key) != value for key, value in expected_values.items()):
        raise RealAssetPolicyError("network-attempt marker does not match its case policy")
    _validate_collection_window(policy, _parse_timestamp(marker["authorized_at"]))
    return marker


def _validate_collected_case_evidence(
    case_path: Path,
    events: list[JsonObject],
    policy: JsonObject,
    policy_digest: str,
    network_attempt: JsonObject | None,
) -> None:
    if network_attempt is None:
        raise RealAssetPolicyError("collected H0 case is missing its network-attempt marker")

    target = policy["target"]
    github = target["github"]
    request_url = github["request_url"]
    manifest_event = events[3]
    observation_event = events[4]
    manifest = manifest_event["payload"]["evidence_manifest"]
    observation = observation_event["payload"]["observation"]
    captured_at = manifest.get("acquired_at")
    captured_moment = _parse_timestamp(captured_at)
    _validate_collection_window(policy, captured_moment)
    if captured_moment < _parse_timestamp(network_attempt["authorized_at"]):
        raise RealAssetPolicyError("collected evidence predates its network-attempt reservation")

    media_type = manifest.get("media_type")
    if (
        manifest_event.get("occurred_at") != captured_at
        or manifest.get("source")
        != {
            "label": f"GitHub public repository metadata: {github['owner']}/{github['repository']}",
            "uri": request_url,
        }
        or manifest.get("access_policy") != "PUBLIC"
        or manifest.get("license") is not None
        or manifest.get("transformations") != []
        or manifest.get("derivative_refs") != []
        or not isinstance(media_type, str)
        or (media_type != "application/json" and not media_type.endswith("+json"))
        or not isinstance(manifest.get("size"), int)
        or isinstance(manifest.get("size"), bool)
        or not 0 <= manifest["size"] <= policy["budgets"]["max_response_bytes"]
    ):
        raise RealAssetPolicyError("collected evidence manifest does not match its H0 policy")

    structured_payload = observation.get("content", {}).get("structured_payload")
    if not isinstance(structured_payload, dict):
        raise RealAssetPolicyError("collected observation has no structured H0 payload")
    case_binding = structured_payload.get("case_binding")
    if not isinstance(case_binding, dict):
        raise RealAssetPolicyError("collected observation has no H0 case binding")
    receipt_id = case_binding.get("acquisition_receipt_id")
    try:
        canonical_receipt_id = str(UUID(receipt_id))
    except (AttributeError, TypeError, ValueError) as error:
        raise RealAssetPolicyError("collected observation has an invalid receipt ID") from error
    if receipt_id != canonical_receipt_id:
        raise RealAssetPolicyError("collected observation has a noncanonical receipt ID")

    receipt_path = case_path / "receipts" / f"{receipt_id}.json"
    receipt = _read_private_json(receipt_path, label="acquisition receipt")
    try:
        receipt_digest = hashlib.sha256(_canonical_bytes(receipt) + b"\n").hexdigest()
    except (TypeError, ValueError) as error:
        raise RealAssetPolicyError("acquisition receipt is not canonical JSON") from error
    expected_binding = {
        "case_id": policy["case_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": policy_digest,
        "target_id": target["target_id"],
        "acquisition_receipt_id": receipt_id,
        "acquisition_receipt_sha256": receipt_digest,
    }
    if case_binding != expected_binding:
        raise RealAssetPolicyError("collected observation receipt binding does not match its case")

    expected_receipt_keys = {
        "receipt_version",
        "receipt_id",
        "case_id",
        "policy_id",
        "policy_sha256",
        "target_id",
        "adapter",
        "adapter_version",
        "request",
        "completed_at",
        "outcome",
        "http_status",
        "response",
        "access_basis",
        "retention_until",
        "coverage_state",
        "completeness_claim",
        "authority_state",
    }
    receipt_response = receipt.get("response")
    if (
        set(receipt) != expected_receipt_keys
        or receipt.get("receipt_version") != "readin.github-public-repository-acquisition.v0.1"
        or receipt.get("receipt_id") != receipt_id
        or receipt.get("case_id") != policy["case_id"]
        or receipt.get("policy_id") != policy["policy_id"]
        or receipt.get("policy_sha256") != policy_digest
        or receipt.get("target_id") != target["target_id"]
        or receipt.get("adapter") != "github_public_repository_metadata"
        or receipt.get("adapter_version") != "0.1.0"
        or receipt.get("request")
        != {
            "method": "GET",
            "url": request_url,
            "api_version": "2026-03-10",
            "credential_state": "NONE",
            "proxy_state": "DISABLED",
            "redirect_count": 0,
        }
        or receipt.get("completed_at") != captured_at
        or receipt.get("outcome") != "ACQUIRED_NEW"
        or receipt.get("http_status") != 200
        or not isinstance(receipt_response, dict)
        or set(receipt_response)
        != {
            "media_type",
            "size",
            "sha256",
            "etag",
            "last_modified",
            "github_request_id",
            "rate_limit",
        }
        or receipt_response.get("media_type") != media_type
        or receipt_response.get("size") != manifest["size"]
        or receipt_response.get("sha256") != manifest.get("sha256")
        or set(receipt_response.get("rate_limit", {}))
        != {"limit", "remaining", "used", "reset", "resource"}
        or receipt.get("access_basis") != "PUBLIC_UNAUTHENTICATED_GITHUB_REST"
        or receipt.get("retention_until") != policy["retention"]["delete_at"]
        or receipt.get("coverage_state") != "BOUNDED"
        or receipt.get("completeness_claim") != "NOT_MADE"
        or receipt.get("authority_state") != "NO_AUTHORITY"
    ):
        raise RealAssetPolicyError("acquisition receipt does not match the collected H0 case")

    vault = EvidenceVault(
        case_path,
        max_artifact_bytes=policy["budgets"]["max_response_bytes"],
    )
    try:
        stored = vault.verify(manifest.get("sha256"))
        body = stored.path.read_bytes()
    except (OSError, VaultError) as error:
        raise RealAssetPolicyError("collected H0 artifact failed vault verification") from error
    if stored.size != manifest["size"] or len(body) != manifest["size"]:
        raise RealAssetPolicyError("collected H0 artifact size does not match its manifest")
    try:
        _, repository_observation = parse_public_repository_response(
            body,
            github["owner"],
            github["repository"],
        )
    except GitHubPublicError as error:
        raise RealAssetPolicyError(
            "stored H0 artifact is not the declared repository response"
        ) from error
    if (
        target["subject_class"] == "PUBLIC_ORGANIZATION_ASSET"
        and repository_observation["owner"]["type"] != "Organization"
    ):
        raise RealAssetPolicyError(
            "stored repository owner type does not match the public-organization policy"
        )

    expected_payload = {
        "case_binding": expected_binding,
        "source_kind": "GITHUB_REST_PUBLIC",
        "authentication_mode": "NONE",
        "repository": repository_observation,
        "coverage_state": "BOUNDED",
        "completeness_claim": "NOT_MADE",
    }
    if (
        observation_event.get("occurred_at") != captured_at
        or observation.get("subject_entities") != [target["entity_id"]]
        or observation.get("observer_frame_id") != target["observer_frame_id"]
        or observation.get("source_artifact_id") != manifest.get("id")
        or observation.get("supersedes_observation_id") is not None
        or observation.get("observed_at") != captured_at
        or observation.get("valid_from") is not None
        or observation.get("valid_until") is not None
        or observation.get("observation_type") != "github.public_repository_metadata.returned"
        or observation.get("content") != {"structured_payload": expected_payload}
        or observation.get("provenance")
        != {
            "collector": "readin-real-asset-case",
            "adapter": "github-public-rest",
            "adapter_version": "0.1.0",
            "source_uri": request_url,
            "source_policy": "PUBLIC",
            "acquisition_time": captured_at,
        }
        or observation.get("epistemic")
        != {
            "resolution": None,
            "uncertainty": {
                "source_reported": True,
                "identity_resolution": "NOT_ATTEMPTED",
                "ownership_inference": "NOT_MADE",
                "completeness": "NOT_ESTABLISHED",
            },
            "access_scope": "PUBLIC",
            "missingness_state": "OBSERVED",
            "dependency_group_ids": [],
        }
        or observation.get("immutable") is not True
    ):
        raise RealAssetPolicyError("collected observation does not match its H0 evidence binding")


def _reserve_network_attempt(
    case_path: Path,
    policy: JsonObject,
    policy_digest: str,
    authorized_at: datetime,
) -> Path:
    marker = {
        "schema_version": "readin.network-attempt.v0.1",
        "case_id": policy["case_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": policy_digest,
        "target_id": policy["target"]["target_id"],
        "authorized_at": _utc_timestamp(authorized_at),
        "method": "GET",
        "url": policy["target"]["github"]["request_url"],
        "authentication_mode": "NONE",
        "state": "RESERVED_BEFORE_REQUEST",
        "authority_state": "NO_AUTHORITY",
    }
    path = case_path / NETWORK_ATTEMPT_FILENAME
    try:
        _write_new_private_json(path, marker)
    except RealAssetCaseExists as error:
        raise RealAssetAcquisitionError(
            "this H0 case already used its one-request network-attempt budget"
        ) from error
    _fsync_directory(case_path)
    return path


def collect_github_public_repository_case(
    case_dir: str | Path,
) -> JsonObject:
    """Perform the one request allowed by an H0 public-repository case."""

    case_path, policy, policy_digest = load_real_asset_case_policy(case_dir)
    with _exclusive_case_lock(case_path):
        case_path, policy, policy_digest = load_real_asset_case_policy(case_path)
        ledger = EventLedger(case_path / LEDGER_FILENAME)
        existing_events = ledger.read_events()
        projection = ReadinProjection.replay(existing_events)
        if projection.evidence or projection.observations:
            raise RealAssetAcquisitionError(
                "this H0 case already used its one-request and one-artifact budget"
            )
        _validate_case_ledger_binding(
            existing_events,
            policy,
            policy_digest,
            allow_collected=False,
        )

        target = policy["target"]
        github = target["github"]
        authorized_at = _trusted_utc_now()
        _validate_collection_window(policy, authorized_at)
        _reserve_network_attempt(case_path, policy, policy_digest, authorized_at)
        _validate_collection_window(policy, _trusted_utc_now())
        try:
            capture = fetch_public_repository(
                github["owner"],
                github["repository"],
                max_bytes=policy["budgets"]["max_response_bytes"],
                wall_clock_deadline=min(
                    _parse_timestamp(policy["budgets"]["collection_not_after"]),
                    _parse_timestamp(policy["retention"]["delete_at"]),
                ),
            )
        except GitHubPublicError as error:
            raise RealAssetAcquisitionError(str(error)) from error

        if capture.request_url != github["request_url"]:
            raise RealAssetAcquisitionError("adapter response escaped the policy-bound endpoint")
        _validate_collection_window(policy, _parse_timestamp(capture.retrieved_at))
        if (
            target["subject_class"] == "PUBLIC_ORGANIZATION_ASSET"
            and capture.observation["owner"]["type"] != "Organization"
        ):
            raise RealAssetAcquisitionError(
                "GitHub response owner type does not match the public-organization policy"
            )
        vault = EvidenceVault(
            case_path,
            max_artifact_bytes=policy["budgets"]["max_response_bytes"],
        )
        try:
            stored = vault.store_bytes(capture.body)
        except VaultError as error:
            raise RealAssetAcquisitionError(str(error)) from error

        receipt_id = str(uuid4())
        receipt = {
            "receipt_version": "readin.github-public-repository-acquisition.v0.1",
            "receipt_id": receipt_id,
            "case_id": policy["case_id"],
            "policy_id": policy["policy_id"],
            "policy_sha256": policy_digest,
            "target_id": target["target_id"],
            "adapter": "github_public_repository_metadata",
            "adapter_version": "0.1.0",
            "request": {
                "method": "GET",
                "url": capture.request_url,
                "api_version": "2026-03-10",
                "credential_state": "NONE",
                "proxy_state": "DISABLED",
                "redirect_count": 0,
            },
            "completed_at": capture.retrieved_at,
            "outcome": "ACQUIRED_NEW",
            "http_status": capture.http_status,
            "response": {
                "media_type": capture.media_type,
                "size": stored.size,
                "sha256": stored.sha256,
                "etag": capture.response_headers.get("etag"),
                "last_modified": capture.response_headers.get("last-modified"),
                "github_request_id": capture.response_headers.get("x-github-request-id"),
                "rate_limit": _safe_rate_limit(capture.response_headers),
            },
            "access_basis": "PUBLIC_UNAUTHENTICATED_GITHUB_REST",
            "retention_until": policy["retention"]["delete_at"],
            "coverage_state": "BOUNDED",
            "completeness_claim": "NOT_MADE",
            "authority_state": "NO_AUTHORITY",
        }
        receipt_digest = hashlib.sha256(_canonical_bytes(receipt) + b"\n").hexdigest()

        binding = {
            "case_id": policy["case_id"],
            "policy_id": policy["policy_id"],
            "policy_sha256": policy_digest,
            "target_id": target["target_id"],
            "acquisition_receipt_id": receipt_id,
            "acquisition_receipt_sha256": receipt_digest,
        }
        artifact_event = create_evidence_manifested(
            stored.sha256,
            capture.media_type,
            stored.size,
            f"GitHub public repository metadata: {github['owner']}/{github['repository']}",
            source_uri=capture.request_url,
            license_name=None,
            access_policy="PUBLIC",
            acquired_at=capture.retrieved_at,
            occurred_at=capture.retrieved_at,
        )
        artifact_id = artifact_event["payload"]["evidence_manifest"]["id"]
        observation_payload = {
            "case_binding": binding,
            "source_kind": "GITHUB_REST_PUBLIC",
            "authentication_mode": "NONE",
            "repository": capture.observation,
            "coverage_state": "BOUNDED",
            "completeness_claim": "NOT_MADE",
        }
        observation_event = create_observation_admitted(
            (target["entity_id"],),
            target["observer_frame_id"],
            artifact_id,
            "github.public_repository_metadata.returned",
            observation_payload,
            capture.retrieved_at,
            source_uri=capture.request_url,
            source_policy="PUBLIC",
            collector="readin-real-asset-case",
            adapter="github-public-rest",
            adapter_version="0.1.0",
            acquisition_time=capture.retrieved_at,
            uncertainty={
                "source_reported": True,
                "identity_resolution": "NOT_ATTEMPTED",
                "ownership_inference": "NOT_MADE",
                "completeness": "NOT_ESTABLISHED",
            },
            occurred_at=capture.retrieved_at,
        )
        ReadinProjection.replay([*existing_events, artifact_event, observation_event])

        try:
            receipt_path = vault.write_receipt(receipt_id, receipt)
            ledger.append(artifact_event)
            ledger.append(observation_event)
            verified = vault.verify(stored.sha256)
        except (VaultError, OSError) as error:
            raise RealAssetAcquisitionError(str(error)) from error

    return {
        "case_dir": str(case_path),
        "case_id": policy["case_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": policy_digest,
        "target_id": target["target_id"],
        "entity_id": target["entity_id"],
        "artifact_id": artifact_id,
        "observation_id": observation_event["payload"]["observation"]["id"],
        "acquisition_receipt_id": receipt_id,
        "acquisition_receipt_sha256": receipt_digest,
        "acquisition_receipt": str(receipt_path),
        "artifact_path": str(verified.path),
        "sha256": verified.sha256,
        "size": verified.size,
        "http_status": capture.http_status,
        "rate_limit": _safe_rate_limit(capture.response_headers),
        "coverage_state": "BOUNDED",
        "completeness_claim": "NOT_MADE",
        "authentication_mode": "NONE",
        "authority_state": "NO_AUTHORITY",
    }
