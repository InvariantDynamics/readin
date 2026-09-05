from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from readin.asset_catalog import (
    AssetCatalogContractError,
    AssetCatalogError,
    build_asset_catalog_events,
    import_asset_catalog_source,
    load_asset_catalog_source_schema,
    validate_asset_catalog_source,
)
from readin.cli import main
from readin.projection import ReadinProjection
from readin.store import EventLedger
from readin.workbench import build_workbench_snapshot


def _catalog_source() -> dict[str, object]:
    return {
        "schema_version": "readin.asset-catalog-source.v0.1",
        "catalog_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "catalog_name": "Operator personal surface",
        "declared_at": "2026-09-04T12:00:00Z",
        "owner": {
            "label": "Local operator",
            "attestation": "USER_ATTESTED_NOT_VERIFIED",
            "scope": "SELF_OR_CONTROLLED_ASSETS_ONLY",
        },
        "purpose": {
            "kind": "PERSONAL_ASSET_CATALOG",
            "statement": (
                "Build a local inventory of accounts and assets before any live connector."
            ),
            "secondary_use": "PROHIBITED",
        },
        "authority": {
            "state": "NO_AUTHORITY",
            "collection": "NOT_GRANTED",
            "external_actions": "PROHIBITED",
            "credential_storage": "PROHIBITED",
            "network_access": False,
            "people_targeting": "PROHIBITED",
        },
        "source": {
            "kind": "USER_DECLARED_LOCAL_MANIFEST",
            "network_access": False,
            "credential_material": "ABSENT",
            "path_retention": "NOT_RECORDED_IN_LEDGER",
        },
        "assets": [
            {
                "asset_class": "SOCIAL_ACCOUNT",
                "display_name": "Example LinkedIn account",
                "platform": "LinkedIn",
                "account_identifier": "operator",
                "source_uri": "https://www.linkedin.com/in/operator/",
                "authorization_basis": "USER_OWNED_ACCOUNT_ATTESTED",
                "collection_mode": "API_CONNECTION_REQUIRES_SEPARATE_GRANT",
                "connector_intent": {
                    "connector_kind": "OAUTH_API",
                    "connection_state": "OAUTH_REQUIRED_NOT_REQUESTED",
                    "credential_state": "NONE",
                    "oauth_state": "NOT_REQUESTED",
                    "live_collection_state": "DISABLED",
                    "external_action_state": "PROHIBITED",
                    "terms_review_state": "REQUIRES_REVIEW",
                },
            },
            {
                "asset_class": "WEB_PROPERTY",
                "display_name": "Example public website",
                "platform": "HTTPS",
                "account_identifier": "example.com",
                "source_uri": "https://example.com/",
                "authorization_basis": "USER_ADMINISTERED_ASSET_ATTESTED",
                "collection_mode": "LOCAL_EXPORT_IMPORT_ONLY",
                "connector_intent": {
                    "connector_kind": "PUBLIC_WEB",
                    "connection_state": "EXPORT_IMPORT_READY",
                    "credential_state": "NONE",
                    "oauth_state": "NOT_REQUIRED",
                    "live_collection_state": "DISABLED",
                    "external_action_state": "PROHIBITED",
                    "terms_review_state": "USER_ATTESTED_ALLOWED",
                },
            },
        ],
    }


def _write_private_manifest(path: Path, source: dict[str, object]) -> Path:
    path.write_text(json.dumps(source, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)
    return path


def test_asset_catalog_source_schema_is_closed_and_rejects_live_collection() -> None:
    source = _catalog_source()

    validate_asset_catalog_source(source)
    assert load_asset_catalog_source_schema()["additionalProperties"] is False

    promoted = deepcopy(source)
    promoted["assets"][0]["connector_intent"]["live_collection_state"] = "ENABLED"  # type: ignore[index]
    with pytest.raises(AssetCatalogContractError, match="DISABLED"):
        validate_asset_catalog_source(promoted)

    connected = deepcopy(source)
    connected["assets"][0]["connector_intent"]["connection_state"] = "OAUTH_CONNECTED"  # type: ignore[index]
    with pytest.raises(AssetCatalogContractError, match="OAUTH_CONNECTED"):
        validate_asset_catalog_source(connected)


def test_asset_catalog_source_rejects_duplicate_asset_keys() -> None:
    source = _catalog_source()
    source["assets"].append(deepcopy(source["assets"][0]))  # type: ignore[union-attr,index]

    with pytest.raises(AssetCatalogContractError, match="duplicate asset declaration"):
        validate_asset_catalog_source(source)


def test_asset_catalog_source_rejects_oauth_state_without_separate_grant() -> None:
    source = _catalog_source()
    source["assets"][0]["collection_mode"] = "LOCAL_EXPORT_IMPORT_ONLY"  # type: ignore[index]

    with pytest.raises(AssetCatalogContractError, match="requires API connection mode"):
        validate_asset_catalog_source(source)


def test_asset_catalog_import_initializes_ledger_and_admits_profiles(tmp_path: Path) -> None:
    manifest = _write_private_manifest(tmp_path / "source.json", _catalog_source())
    ledger = EventLedger(tmp_path / "catalog" / "events.jsonl")

    result = import_asset_catalog_source(ledger, manifest, attested=True)
    events = ledger.read_events()
    projection = ledger.projection()
    first_asset = result["assets"][0]
    asset_view = projection.asset_view(first_asset["entity_id"])

    assert result["ledger_status"] == "initialized"
    assert result["events_appended"] == 8
    assert result["asset_class_counts"] == {"SOCIAL_ACCOUNT": 1, "WEB_PROPERTY": 1}
    assert result["connection_state_counts"] == {
        "EXPORT_IMPORT_READY": 1,
        "OAUTH_REQUIRED_NOT_REQUESTED": 1,
    }
    assert result["authority"]["network_access"] is False
    assert [event["authority_state"] for event in events] == ["NO_AUTHORITY"] * 8
    assert len(projection.catalog_view()) == 2
    assert len(projection.frames) == 1
    assert len(projection.evidence) == 1
    assert len(projection.observations) == 2
    assert (
        asset_view["entity"]["attributes"]["asset_catalog_binding"]["connector_intent"][
            "live_collection_state"
        ]
        == "DISABLED"
    )
    assert asset_view["observations"][0]["observation_type"] == (
        "asset_catalog.user_declared_profile"
    )
    assert asset_view["observations"][0]["provenance"]["adapter"] == (
        "local-asset-catalog-manifest"
    )


def test_asset_catalog_import_is_idempotent_for_existing_manifest(tmp_path: Path) -> None:
    manifest = _write_private_manifest(tmp_path / "source.json", _catalog_source())
    ledger = EventLedger(tmp_path / "catalog" / "events.jsonl")

    first = import_asset_catalog_source(ledger, manifest, attested=True)
    second = import_asset_catalog_source(ledger, manifest, attested=True)

    assert first["events_appended"] == 8
    assert second["events_appended"] == 0
    assert second["events_skipped_existing"] == 8
    assert len(ledger.read_events()) == 8


def test_asset_catalog_import_requires_attestation_and_private_source(tmp_path: Path) -> None:
    manifest = tmp_path / "source.json"
    manifest.write_text(json.dumps(_catalog_source()), encoding="utf-8")

    with pytest.raises(AssetCatalogError, match="explicit attestation is required"):
        import_asset_catalog_source(
            EventLedger(tmp_path / "events.jsonl"), manifest, attested=False
        )

    with pytest.raises(AssetCatalogError, match="not owner-only"):
        import_asset_catalog_source(EventLedger(tmp_path / "events.jsonl"), manifest, attested=True)


def test_asset_catalog_events_replay_without_collection_authority() -> None:
    source = _catalog_source()
    events = build_asset_catalog_events(
        source,
        source_sha256="0" * 64,
        source_size=2048,
    )

    projection = ReadinProjection.replay(events)

    assert len(events) == 8
    assert len(projection.catalog_view()) == 2
    assert all(event["authority_state"] == "NO_AUTHORITY" for event in events)
    assert all(
        event["payload"]["observation"]["provenance"]["source_policy"] == "USER_OWNED"
        for event in events
        if event["event_type"] == "observation.admitted"
    )


def test_workbench_exposes_asset_catalog_setup_without_live_collection(tmp_path: Path) -> None:
    manifest = _write_private_manifest(tmp_path / "source.json", _catalog_source())
    ledger = EventLedger(tmp_path / "catalog" / "events.jsonl")
    result = import_asset_catalog_source(ledger, manifest, attested=True)

    snapshot = build_workbench_snapshot(ledger.projection(), result["assets"][0]["entity_id"])
    setup = snapshot["selected_asset"]["governance"]["source_setup"]

    assert snapshot["asset_catalog"]["state"] == "LOCAL_MANIFEST_ASSET_CATALOG_PRESENT"
    assert snapshot["asset_catalog"]["network_access"] is False
    assert setup["connection_state"] == "OAUTH_REQUIRED_NOT_REQUESTED"
    assert setup["credential_state"] == "NONE"
    assert setup["live_collection_state"] == "DISABLED"
    assert setup["external_action_state"] == "PROHIBITED"
    assert setup["people_targeting"] == "PROHIBITED"


def test_cli_imports_asset_catalog_and_requires_attestation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _write_private_manifest(tmp_path / "source.json", _catalog_source())
    ledger = tmp_path / "catalog" / "events.jsonl"

    missing_attestation = main(
        ["import-asset-catalog", "--ledger", str(ledger), "--manifest", str(manifest)]
    )
    captured = capsys.readouterr()
    assert missing_attestation == 2
    assert "explicit attestation is required" in captured.err

    result = main(
        [
            "import-asset-catalog",
            "--ledger",
            str(ledger),
            "--manifest",
            str(manifest),
            "--attest",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output["ledger_status"] == "initialized"
    assert output["events_appended"] == 8
    assert output["assets_declared"] == 2
    assert output["authority"]["network_access"] is False


def test_cli_import_refuses_policy_bound_case_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    manifest = _write_private_manifest(tmp_path / "source.json", _catalog_source())
    case_dir = tmp_path / "protected-case"
    assert (
        main(
            [
                "init-github-public-repository-case",
                "--case-dir",
                str(case_dir),
                "--owner",
                "InvariantDynamics",
                "--repository",
                "readin",
                "--purpose",
                "Verify asset catalog imports cannot bypass the case connector.",
                "--attest",
            ]
        )
        == 0
    )
    capsys.readouterr()

    result = main(
        [
            "import-asset-catalog",
            "--ledger",
            str(case_dir / "events.jsonl"),
            "--manifest",
            str(manifest),
            "--attest",
        ]
    )
    captured = capsys.readouterr()

    assert result == 2
    assert "accept writes only through their declared case connector" in captured.err
    assert len(EventLedger(case_dir / "events.jsonl").read_events()) == 3
