from __future__ import annotations

import hashlib
import json
import stat
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

import readin.real_asset_cases as real_asset_cases
from readin.github_public import GitHubPublicError, PublicRepositoryCapture
from readin.real_asset_cases import (
    RealAssetAcquisitionError,
    RealAssetPolicyError,
    collect_github_public_repository_case,
    initialize_github_public_repository_case,
    load_real_asset_case_policy,
    validate_real_asset_case_read_access,
)
from readin.store import EventLedger
from readin.workbench import (
    WorkbenchError,
    build_ledger_workbench_snapshot,
    build_workbench_snapshot,
)

DECLARED_AT = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
CAPTURED_AT = datetime(2026, 9, 3, 12, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _fixed_authorization_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("readin.real_asset_cases._trusted_utc_now", lambda: CAPTURED_AT)


def _initialize(case_dir: Path, *, subject_class: str = "PUBLIC_ORGANIZATION_ASSET") -> dict:
    return initialize_github_public_repository_case(
        case_dir,
        "InvariantDynamics",
        "readin",
        "Evaluate one bounded public repository acquisition through READIN.",
        attested=True,
        subject_class=subject_class,
        declared_at=DECLARED_AT,
    )


def _capture() -> PublicRepositoryCapture:
    payload = {
        "id": 123,
        "node_id": "R_readin",
        "name": "readin",
        "full_name": "InvariantDynamics/readin",
        "private": False,
        "visibility": "public",
        "url": "https://api.github.com/repos/InvariantDynamics/readin",
        "html_url": "https://github.com/InvariantDynamics/readin",
        "owner": {"login": "InvariantDynamics", "id": 9876, "type": "Organization"},
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    return PublicRepositoryCapture(
        body=body,
        payload=payload,
        request_url="https://api.github.com/repos/InvariantDynamics/readin",
        retrieved_at="2026-09-03T12:01:00Z",
        http_status=200,
        media_type="application/json",
        response_headers={
            "etag": '"bounded-etag"',
            "x-github-request-id": "request-1",
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "59",
            "x-ratelimit-used": "1",
            "x-ratelimit-reset": "1788440400",
            "x-ratelimit-resource": "core",
        },
        observation={
            "schema_version": "readin.github-public-repository-observation.v0.1",
            "source_kind": "GITHUB_PUBLIC_REPOSITORY_API",
            "target": {"owner": "InvariantDynamics", "repository": "readin"},
            "owner": {"login": "InvariantDynamics", "id": 9876, "type": "Organization"},
            "repository": {
                "id": 123,
                "node_id": "R_readin",
                "name": "readin",
                "full_name": "InvariantDynamics/readin",
                "private": False,
                "visibility": "public",
            },
            "authority_state": "NO_AUTHORITY",
            "verification_state": "CAPTURED_NOT_INDEPENDENTLY_VERIFIED",
            "coverage_state": "SINGLE_ENDPOINT_RESPONSE_ONLY",
        },
    )


def _collect_valid_case(
    case_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    _initialize(case_dir)
    capture = _capture()
    monkeypatch.setattr(
        "readin.real_asset_cases.fetch_public_repository",
        lambda owner, repository, *, max_bytes, wall_clock_deadline: capture,
    )
    return collect_github_public_repository_case(case_dir)


def _rewrite_ledger(path: Path, events: list[dict]) -> None:
    path.write_text(
        "".join(
            json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)


def test_case_initialization_is_private_policy_bound_and_offline(tmp_path: Path) -> None:
    case_dir = tmp_path / "readin-public-repository"

    result = _initialize(case_dir)
    path, policy, digest = load_real_asset_case_policy(case_dir)
    events = EventLedger(case_dir / "events.jsonl").read_events()

    assert result["network_access"] == "NOT_ATTEMPTED"
    assert result["authority_state"] == "NO_AUTHORITY"
    assert path == case_dir
    assert result["policy_sha256"] == digest
    assert policy["source"]["authentication_mode"] == "NONE"
    assert policy["source"]["redirect_policy"] == "DENY"
    assert policy["budgets"]["max_network_requests"] == 1
    assert policy["minimization"]["contributors"] == "EXCLUDED"
    assert len(events) == 3
    assert [event["event_type"] for event in events] == [
        "entity.created",
        "asset.tracking_started",
        "observer_frame.registered",
    ]
    binding = events[0]["payload"]["entity"]["attributes"]["real_asset_case_binding"]
    assert binding["policy_sha256"] == digest
    assert binding["ownership_claim"] == "NOT_MADE"
    assert stat.S_IMODE(case_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE((case_dir / "policy.json").stat().st_mode) == 0o600
    assert stat.S_IMODE((case_dir / "events.jsonl").stat().st_mode) == 0o600


def test_case_initialization_requires_explicit_attestation(tmp_path: Path) -> None:
    case_dir = tmp_path / "unattested"

    with pytest.raises(RealAssetPolicyError, match="explicit attestation"):
        initialize_github_public_repository_case(
            case_dir,
            "InvariantDynamics",
            "readin",
            "Evaluate one exact repository without widening the target scope.",
            attested=False,
            declared_at=DECLARED_AT,
        )

    assert not case_dir.exists()


def test_user_owned_asset_remains_unverified_attestation(tmp_path: Path) -> None:
    case_dir = tmp_path / "owned"
    _initialize(case_dir, subject_class="USER_OWNED_ASSET")

    _, policy, _ = load_real_asset_case_policy(case_dir)

    assert policy["target"]["authorization_basis"] == "OWNERSHIP_ATTESTED"
    assert policy["target"]["ownership_claim"] == "USER_ATTESTED_NOT_VERIFIED"


def test_altered_policy_fails_digest_check(tmp_path: Path) -> None:
    case_dir = tmp_path / "altered"
    _initialize(case_dir)
    policy_path = case_dir / "policy.json"
    envelope = json.loads(policy_path.read_text(encoding="utf-8"))
    envelope["policy"]["purpose"]["statement"] = "A materially different purpose."
    policy_path.write_text(json.dumps(envelope), encoding="utf-8")
    policy_path.chmod(0o600)

    with pytest.raises(RealAssetPolicyError, match="digest does not match"):
        load_real_asset_case_policy(case_dir)


def test_redigested_policy_cannot_promote_collection_authority(tmp_path: Path) -> None:
    case_dir = tmp_path / "promoted"
    _initialize(case_dir)
    policy_path = case_dir / "policy.json"
    envelope = json.loads(policy_path.read_text(encoding="utf-8"))
    envelope["policy"]["authority"]["collection"] = "UNRESTRICTED"
    canonical = json.dumps(
        envelope["policy"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    envelope["policy_sha256"] = hashlib.sha256(canonical).hexdigest()
    policy_path.write_text(json.dumps(envelope), encoding="utf-8")
    policy_path.chmod(0o600)

    with pytest.raises(RealAssetPolicyError, match="READ_ONLY_EXACT_TARGET"):
        load_real_asset_case_policy(case_dir)


def test_collection_persists_exact_bytes_receipt_and_no_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "collected"
    _initialize(case_dir)
    capture = _capture()
    calls: list[tuple[str, str, int, datetime]] = []

    def fake_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> PublicRepositoryCapture:
        calls.append((owner, repository, max_bytes, wall_clock_deadline))
        return capture

    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", fake_fetch)

    result = collect_github_public_repository_case(case_dir)
    network_attempt = validate_real_asset_case_read_access(case_dir)
    events = EventLedger(case_dir / "events.jsonl").read_events()
    ledger_text = (case_dir / "events.jsonl").read_text(encoding="utf-8")
    receipt = json.loads(Path(result["acquisition_receipt"]).read_text(encoding="utf-8"))
    projection = EventLedger(case_dir / "events.jsonl").projection()
    snapshot = build_workbench_snapshot(projection, result["entity_id"])
    case_snapshot = build_ledger_workbench_snapshot(case_dir / "events.jsonl")

    assert calls == [
        (
            "InvariantDynamics",
            "readin",
            524_288,
            datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
        )
    ]
    assert len(events) == 5
    assert events[-2]["event_type"] == "evidence.manifested"
    assert events[-1]["event_type"] == "observation.admitted"
    observation = events[-1]["payload"]["observation"]
    assert observation["provenance"]["adapter"] == "github-public-rest"
    assert observation["epistemic"]["access_scope"] == "PUBLIC"
    assert observation["content"]["structured_payload"]["completeness_claim"] == "NOT_MADE"
    assert result["authentication_mode"] == "NONE"
    assert result["coverage_state"] == "BOUNDED"
    assert result["authority_state"] == "NO_AUTHORITY"
    assert network_attempt is not None
    assert network_attempt["state"] == "RESERVED_BEFORE_REQUEST"
    case_binding = events[-1]["payload"]["observation"]["content"]["structured_payload"][
        "case_binding"
    ]
    assert case_binding["acquisition_receipt_sha256"] == result["acquisition_receipt_sha256"]
    assert Path(result["artifact_path"]).read_bytes() == capture.body
    assert stat.S_IMODE(Path(result["artifact_path"]).stat().st_mode) == 0o600
    assert receipt["request"]["credential_state"] == "NONE"
    assert receipt["request"]["redirect_count"] == 0
    assert receipt["authority_state"] == "NO_AUTHORITY"
    assert capture.body.decode("utf-8").strip() not in ledger_text
    assert snapshot["epistemic_limits"]["collection_state"] == "RECORDED_USER_INVOKED_ONE_SHOT"
    assert snapshot["epistemic_limits"]["acquisition_state"] == (
        "PUBLIC_SOURCE_ARTIFACT_ADMISSION_RECORDED"
    )
    assert snapshot["selected_asset"]["governance"]["state"] == ("REAL_ASSET_CASE_BINDING_DECLARED")
    assert (
        snapshot["selected_asset"]["governance"]["real_asset_case_binding"]["policy_sha256"]
        == result["policy_sha256"]
    )
    case_summary = case_snapshot["case"]
    assert case_summary["state"] == "VALIDATED_ARTIFACT_ADMITTED"
    assert case_summary["purpose"]["kind"] == "SYSTEM_CAPABILITY_EVALUATION"
    assert case_summary["target"]["github"]["request_url"] == (
        "https://api.github.com/repos/InvariantDynamics/readin"
    )
    assert case_summary["budgets"]["network_requests_used"] == 1
    assert case_summary["budgets"]["artifacts_admitted"] == 1
    assert case_summary["collection"]["result"] == "ARTIFACT_ADMITTED"
    assert case_summary["evidence"] == {
        "manifest_id": result["artifact_id"],
        "receipt_id": result["acquisition_receipt_id"],
        "receipt_sha256": result["acquisition_receipt_sha256"],
        "artifact_sha256": result["sha256"],
        "media_type": capture.media_type,
        "size": len(capture.body),
        "acquired_at": capture.retrieved_at,
        "http_status": 200,
    }
    assert case_summary["custody"]["state"] == "FULL_CHAIN_VERIFIED"
    assert [item["state"] for item in case_summary["custody"]["checks"]] == [
        "DIGEST_VERIFIED",
        "REPLAY_VERIFIED",
        "MARKER_VERIFIED",
        "DIGEST_AND_BINDING_VERIFIED",
        "SHA256_VERIFIED",
        "SOURCE_REDERIVED_AND_MATCHED",
    ]
    assert case_summary["audit"]["sequence_state"] == "CLOSED_H0_SEQUENCE_VERIFIED"
    assert case_summary["audit"]["event_count"] == 5
    assert case_summary["audit"]["read_gate"] == "PASSED"
    assert case_summary["audit"]["raw_artifact_preview"] == "NOT_EXPOSED"
    assert case_summary["audit"]["ledger_path"] == str(case_dir / "events.jsonl")
    assert [item["event_type"] for item in case_summary["audit"]["ledger_events"]] == [
        "entity.created",
        "asset.tracking_started",
        "observer_frame.registered",
        "evidence.manifested",
        "observation.admitted",
    ]
    assert case_summary["audit"]["ledger_events"][3]["payload_label"] == (
        "GitHub public repository metadata: InvariantDynamics/readin"
    )
    assert [item["label"] for item in case_summary["audit"]["files"]] == [
        "Case policy",
        "Event ledger",
        "Network-attempt marker",
        "Acquisition receipt",
        "Raw source artifact",
    ]
    assert case_summary["audit"]["files"][0]["sha256"] == result["policy_sha256"]
    assert case_summary["audit"]["files"][-1]["sha256"] == result["sha256"]
    assert case_summary["audit"]["files"][-1]["size"] == len(capture.body)
    case_observation = case_snapshot["selected_asset"]["evidence"]["observations"][0]
    assert (
        case_observation["content"]["structured_payload"]["repository"]["repository"]["full_name"]
        == "InvariantDynamics/readin"
    )


def test_h0_case_refuses_a_second_collection_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "one-shot"
    _initialize(case_dir)
    capture = _capture()
    monkeypatch.setattr(
        "readin.real_asset_cases.fetch_public_repository",
        lambda owner, repository, *, max_bytes, wall_clock_deadline: capture,
    )
    collect_github_public_repository_case(case_dir)

    def unexpected_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> None:
        raise AssertionError("network must not be reached after the one-shot budget is spent")

    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", unexpected_fetch)
    with pytest.raises(RealAssetAcquisitionError, match="one-request"):
        collect_github_public_repository_case(case_dir)


def test_expired_collection_window_fails_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "expired"
    _initialize(case_dir)

    def unexpected_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> None:
        raise AssertionError("network must not be reached for an expired policy")

    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", unexpected_fetch)
    cutoff = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    monkeypatch.setattr("readin.real_asset_cases._trusted_utc_now", lambda: cutoff)
    with pytest.raises(RealAssetPolicyError, match="window has closed"):
        collect_github_public_repository_case(case_dir)


def test_failed_network_attempt_still_consumes_the_one_request_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "failed-attempt"
    _initialize(case_dir)
    calls = 0

    def failed_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> None:
        nonlocal calls
        calls += 1
        raise GitHubPublicError("bounded request failed")

    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", failed_fetch)
    with pytest.raises(RealAssetAcquisitionError, match="bounded request failed"):
        collect_github_public_repository_case(case_dir)
    with pytest.raises(RealAssetAcquisitionError, match="network-attempt budget"):
        collect_github_public_repository_case(case_dir)

    assert calls == 1
    marker = json.loads((case_dir / "network-attempt.json").read_text(encoding="utf-8"))
    assert marker["state"] == "RESERVED_BEFORE_REQUEST"
    assert marker["authentication_mode"] == "NONE"
    assert stat.S_IMODE((case_dir / "network-attempt.json").stat().st_mode) == 0o600
    snapshot = build_ledger_workbench_snapshot(case_dir / "events.jsonl")
    assert snapshot["epistemic_limits"]["collection_state"] == (
        "NETWORK_ATTEMPT_RESERVED_NO_ADMISSION"
    )
    assert snapshot["epistemic_limits"]["acquisition_state"] == "NO_ARTIFACT_ADMITTED"


def test_case_path_inside_git_checkout_is_rejected(tmp_path: Path) -> None:
    checkout = tmp_path / "repo"
    checkout.mkdir()
    (checkout / ".git").write_text("gitdir: elsewhere\n", encoding="utf-8")

    with pytest.raises(RealAssetPolicyError, match="outside Git"):
        _initialize(checkout / "case")


def test_overpermissive_case_is_rejected(tmp_path: Path) -> None:
    case_dir = tmp_path / "overpermissive"
    _initialize(case_dir)
    case_dir.chmod(0o755)

    with pytest.raises(RealAssetPolicyError, match="not owner-only"):
        load_real_asset_case_policy(case_dir)


def test_response_completed_after_window_is_not_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "late-response"
    _initialize(case_dir)
    late_capture = replace(_capture(), retrieved_at="2026-09-04T12:00:01Z")
    monkeypatch.setattr(
        "readin.real_asset_cases.fetch_public_repository",
        lambda owner, repository, *, max_bytes, wall_clock_deadline: late_capture,
    )

    with pytest.raises(RealAssetPolicyError, match="window has closed"):
        collect_github_public_repository_case(case_dir)

    assert not any((case_dir / "evidence" / "sha256").iterdir())
    assert len(EventLedger(case_dir / "events.jsonl").read_events()) == 3


def test_retention_deadline_blocks_normal_case_read_access(tmp_path: Path) -> None:
    case_dir = tmp_path / "retention-expired"
    _initialize(case_dir)
    deadline = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("readin.real_asset_cases._trusted_utc_now", lambda: deadline)

        with pytest.raises(RealAssetPolicyError, match="normal read"):
            validate_real_asset_case_read_access(case_dir)


def test_redigested_policy_cannot_extend_read_retention(tmp_path: Path) -> None:
    case_dir = tmp_path / "redigested-retention-extension"
    _initialize(case_dir)
    policy_path = case_dir / "policy.json"
    envelope = json.loads(policy_path.read_text(encoding="utf-8"))
    shifted_declared_at = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    envelope["policy"]["declared_at"] = shifted_declared_at.isoformat().replace("+00:00", "Z")
    envelope["policy"]["budgets"]["collection_not_before"] = envelope["policy"]["declared_at"]
    envelope["policy"]["budgets"]["collection_not_after"] = (
        shifted_declared_at.replace(hour=13).isoformat().replace("+00:00", "Z")
    )
    envelope["policy"]["retention"]["delete_at"] = "2026-10-04T12:00:00Z"
    canonical = json.dumps(
        envelope["policy"], sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    envelope["policy_sha256"] = hashlib.sha256(canonical).hexdigest()
    policy_path.write_text(json.dumps(envelope), encoding="utf-8")
    policy_path.chmod(0o600)

    with pytest.raises(RealAssetPolicyError, match="entity does not match"):
        validate_real_asset_case_read_access(case_dir)


def test_direct_workbench_read_refuses_bound_ledger_without_policy(tmp_path: Path) -> None:
    case_dir = tmp_path / "workbench-missing-policy"
    _initialize(case_dir)
    (case_dir / "policy.json").unlink()

    with pytest.raises(WorkbenchError, match="missing its required policy"):
        build_ledger_workbench_snapshot(case_dir / "events.jsonl")


def test_direct_workbench_read_refuses_policy_with_removed_ledger_binding(
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / "workbench-removed-binding"
    _initialize(case_dir)
    ledger_path = case_dir / "events.jsonl"
    events = EventLedger(ledger_path).read_events()
    del events[0]["payload"]["entity"]["attributes"]["real_asset_case_binding"]
    _rewrite_ledger(ledger_path, events)

    with pytest.raises(WorkbenchError, match="entity does not match"):
        build_ledger_workbench_snapshot(ledger_path)


def test_direct_workbench_read_refuses_adjacent_noncanonical_ledger(tmp_path: Path) -> None:
    case_dir = tmp_path / "workbench-alternate-ledger"
    _initialize(case_dir)
    events = EventLedger(case_dir / "events.jsonl").read_events()
    events[0]["payload"]["entity"]["canonical_name"] = "Unvalidated/alternate"
    alternate_path = case_dir / "alternate.jsonl"
    _rewrite_ledger(alternate_path, events)

    with pytest.raises(WorkbenchError, match="canonical events.jsonl"):
        build_ledger_workbench_snapshot(alternate_path)


def test_case_read_rejects_observer_frame_boundary_drift(tmp_path: Path) -> None:
    case_dir = tmp_path / "frame-boundary-drift"
    _initialize(case_dir)
    ledger_path = case_dir / "events.jsonl"
    events = EventLedger(ledger_path).read_events()
    events[2]["payload"]["observer_frame"]["known_blind_regions"] = []
    _rewrite_ledger(ledger_path, events)

    with pytest.raises(RealAssetPolicyError, match="observer frame does not match"):
        validate_real_asset_case_read_access(case_dir)


def test_case_read_rejects_duplicate_genesis_event_id(tmp_path: Path) -> None:
    case_dir = tmp_path / "duplicate-genesis-event-id"
    _initialize(case_dir)
    ledger_path = case_dir / "events.jsonl"
    events = EventLedger(ledger_path).read_events()
    events[1]["event_id"] = events[0]["event_id"]
    events[1]["payload"]["tracked_asset"]["epistemic_state_version"] = events[0]["event_id"]
    _rewrite_ledger(ledger_path, events)

    with pytest.raises(RealAssetPolicyError, match="failed semantic replay"):
        validate_real_asset_case_read_access(case_dir)


def test_collection_rejects_ledger_binding_drift_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "binding-drift"
    _initialize(case_dir)
    ledger_path = case_dir / "events.jsonl"
    events = EventLedger(ledger_path).read_events()
    events[0]["payload"]["entity"]["attributes"]["real_asset_case_binding"]["policy_sha256"] = (
        "0" * 64
    )
    ledger_path.write_text(
        "".join(json.dumps(event, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )
    ledger_path.chmod(0o600)

    def unexpected_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> None:
        raise AssertionError("network must not be reached for a mismatched ledger binding")

    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", unexpected_fetch)
    with pytest.raises(RealAssetPolicyError, match="entity does not match"):
        collect_github_public_repository_case(case_dir)

    assert not (case_dir / "network-attempt.json").exists()


def test_public_organization_policy_rejects_personal_account_owner_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "personal-owner"
    _initialize(case_dir)
    capture = _capture()
    personal_observation = deepcopy(capture.observation)
    personal_observation["owner"]["type"] = "User"
    personal_capture = replace(capture, observation=personal_observation)
    monkeypatch.setattr(
        "readin.real_asset_cases.fetch_public_repository",
        lambda owner, repository, *, max_bytes, wall_clock_deadline: personal_capture,
    )

    with pytest.raises(RealAssetAcquisitionError, match="owner type"):
        collect_github_public_repository_case(case_dir)

    assert not any((case_dir / "evidence" / "sha256").iterdir())


def test_collection_rejects_caller_supplied_authorization_time_before_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "caller-time-override"
    _initialize(case_dir)

    def unexpected_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> None:
        raise AssertionError("network must not be reached for a caller-supplied clock")

    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", unexpected_fetch)
    with pytest.raises(TypeError, match="unexpected keyword argument 'now'"):
        collect_github_public_repository_case(case_dir, now=CAPTURED_AT)  # type: ignore[call-arg]

    assert not (case_dir / "network-attempt.json").exists()


def test_collection_rechecks_trusted_time_after_waiting_for_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "lock-delay-expiry"
    _initialize(case_dir)
    clock = {"now": CAPTURED_AT}
    after_window = datetime(2026, 9, 4, 12, 0, 1, tzinfo=UTC)

    @contextmanager
    def delayed_lock(case_path: Path):
        del case_path
        clock["now"] = after_window
        yield

    def unexpected_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> None:
        raise AssertionError("network must not be reached after lock-delay expiry")

    monkeypatch.setattr("readin.real_asset_cases._exclusive_case_lock", delayed_lock)
    monkeypatch.setattr("readin.real_asset_cases._trusted_utc_now", lambda: clock["now"])
    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", unexpected_fetch)

    with pytest.raises(RealAssetPolicyError, match="window has closed"):
        collect_github_public_repository_case(case_dir)

    assert not (case_dir / "network-attempt.json").exists()


def test_collection_rechecks_trusted_time_after_reserving_request_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "reservation-delay-expiry"
    _initialize(case_dir)
    clock = {"now": CAPTURED_AT}
    after_window = datetime(2026, 9, 4, 12, 0, 1, tzinfo=UTC)
    reserve_attempt = real_asset_cases._reserve_network_attempt

    def delayed_reservation(
        case_path: Path,
        policy: dict,
        policy_digest: str,
        authorized_at: datetime,
    ) -> Path:
        marker_path = reserve_attempt(case_path, policy, policy_digest, authorized_at)
        clock["now"] = after_window
        return marker_path

    def unexpected_fetch(
        owner: str,
        repository: str,
        *,
        max_bytes: int,
        wall_clock_deadline: datetime,
    ) -> None:
        raise AssertionError("network must not be reached after reservation-delay expiry")

    monkeypatch.setattr("readin.real_asset_cases._reserve_network_attempt", delayed_reservation)
    monkeypatch.setattr("readin.real_asset_cases._trusted_utc_now", lambda: clock["now"])
    monkeypatch.setattr("readin.real_asset_cases.fetch_public_repository", unexpected_fetch)

    with pytest.raises(RealAssetPolicyError, match="window has closed"):
        collect_github_public_repository_case(case_dir)

    marker = json.loads((case_dir / "network-attempt.json").read_text(encoding="utf-8"))
    assert marker["state"] == "RESERVED_BEFORE_REQUEST"


def test_workbench_reports_reserved_attempt_after_pre_transport_crash(tmp_path: Path) -> None:
    case_dir = tmp_path / "reserved-before-crash"
    _initialize(case_dir)
    _, policy, policy_digest = load_real_asset_case_policy(case_dir)
    real_asset_cases._reserve_network_attempt(case_dir, policy, policy_digest, CAPTURED_AT)

    snapshot = build_ledger_workbench_snapshot(case_dir / "events.jsonl")

    assert snapshot["epistemic_limits"]["collection_state"] == (
        "NETWORK_ATTEMPT_RESERVED_NO_ADMISSION"
    )
    assert snapshot["epistemic_limits"]["acquisition_state"] == "NO_ARTIFACT_ADMITTED"
    assert snapshot["case"]["state"] == "VALIDATED_ATTEMPT_NO_ADMISSION"
    assert snapshot["case"]["collection"]["result"] == "NO_ARTIFACT_ADMITTED"
    assert snapshot["case"]["budgets"]["network_requests_used"] == 1
    assert snapshot["case"]["budgets"]["artifacts_admitted"] == 0
    assert snapshot["case"]["evidence"] is None
    assert snapshot["case"]["audit"]["sequence_state"] == "INITIAL_H0_SEQUENCE_VERIFIED"
    assert snapshot["case"]["audit"]["event_count"] == 3
    assert snapshot["case"]["audit"]["files"][2]["state"] == "PRIVATE_MARKER_VERIFIED"
    assert snapshot["case"]["audit"]["files"][3]["state"] == "NOT_PRESENT"
    assert snapshot["case"]["audit"]["files"][4]["state"] == "NOT_PRESENT"


def test_workbench_rejects_marker_that_does_not_match_case_policy(tmp_path: Path) -> None:
    case_dir = tmp_path / "altered-marker"
    _initialize(case_dir)
    _, policy, policy_digest = load_real_asset_case_policy(case_dir)
    marker_path = real_asset_cases._reserve_network_attempt(
        case_dir, policy, policy_digest, CAPTURED_AT
    )
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    marker["target_id"] = "00000000-0000-4000-8000-000000000000"
    marker_path.write_text(json.dumps(marker), encoding="utf-8")
    marker_path.chmod(0o600)

    with pytest.raises(WorkbenchError, match="marker does not match"):
        build_ledger_workbench_snapshot(case_dir / "events.jsonl")


def test_collected_case_read_requires_network_attempt_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "missing-collected-marker"
    _collect_valid_case(case_dir, monkeypatch)
    (case_dir / "network-attempt.json").unlink()

    with pytest.raises(RealAssetPolicyError, match="missing its network-attempt marker"):
        validate_real_asset_case_read_access(case_dir)


def test_collected_case_read_rehashes_raw_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "corrupt-collected-artifact"
    result = _collect_valid_case(case_dir, monkeypatch)
    artifact_path = Path(result["artifact_path"])
    artifact_path.write_bytes(b"tampered")
    artifact_path.chmod(0o600)

    with pytest.raises(RealAssetPolicyError, match="failed vault verification"):
        validate_real_asset_case_read_access(case_dir)


def test_collected_case_read_requires_bound_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "missing-collected-receipt"
    result = _collect_valid_case(case_dir, monkeypatch)
    Path(result["acquisition_receipt"]).unlink()

    with pytest.raises(RealAssetPolicyError, match="acquisition receipt is missing"):
        validate_real_asset_case_read_access(case_dir)


def test_collected_case_read_rejects_altered_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "altered-collected-receipt"
    result = _collect_valid_case(case_dir, monkeypatch)
    receipt_path = Path(result["acquisition_receipt"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["http_status"] = 201
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_path.chmod(0o600)

    with pytest.raises(RealAssetPolicyError, match="receipt binding does not match"):
        validate_real_asset_case_read_access(case_dir)


def test_collected_case_read_rejects_manifest_source_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "manifest-source-drift"
    _collect_valid_case(case_dir, monkeypatch)
    ledger_path = case_dir / "events.jsonl"
    events = EventLedger(ledger_path).read_events()
    events[3]["payload"]["evidence_manifest"]["source"]["uri"] = (
        "https://api.github.com/repos/SomeoneElse/readin"
    )
    _rewrite_ledger(ledger_path, events)

    with pytest.raises(RealAssetPolicyError, match="manifest does not match"):
        validate_real_asset_case_read_access(case_dir)


def test_collected_case_read_rejects_observation_binding_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = tmp_path / "observation-binding-drift"
    _collect_valid_case(case_dir, monkeypatch)
    ledger_path = case_dir / "events.jsonl"
    events = EventLedger(ledger_path).read_events()
    case_binding = events[4]["payload"]["observation"]["content"]["structured_payload"][
        "case_binding"
    ]
    case_binding["target_id"] = "00000000-0000-4000-8000-000000000000"
    _rewrite_ledger(ledger_path, events)

    with pytest.raises(RealAssetPolicyError, match="receipt binding does not match"):
        validate_real_asset_case_read_access(case_dir)
