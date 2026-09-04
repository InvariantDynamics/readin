from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from readin.asset_catalog import import_asset_catalog_source
from readin.cli import main
from readin.connector_grants import (
    CONNECTOR_GRANT_OBSERVATION_TYPE,
    ConnectorGrantContractError,
    ConnectorGrantError,
    build_connector_grant_events,
    import_connector_grant_source,
    load_connector_grant_source_schema,
    validate_connector_grant_source,
)
from readin.contracts import validate_event
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
            "statement": "Build a local inventory before any live connector.",
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
            }
        ],
    }


def _write_private_manifest(path: Path, source: dict[str, object]) -> Path:
    path.write_text(json.dumps(source, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    path.chmod(0o600)
    return path


def _connector_grant_source(catalog_result: dict[str, object]) -> dict[str, object]:
    asset = catalog_result["assets"][0]  # type: ignore[index]
    return {
        "schema_version": "readin.connector-grant-source.v0.1",
        "grant_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        "declared_at": "2026-09-04T12:05:00Z",
        "owner": {
            "label": "Local operator",
            "attestation": "USER_ATTESTED_NOT_VERIFIED",
            "scope": "SELF_OR_CONTROLLED_ASSETS_ONLY",
        },
        "asset": {
            "entity_id": asset["entity_id"],
            "catalog_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "asset_key": asset["asset_key"],
            "asset_class": "SOCIAL_ACCOUNT",
            "platform": "LinkedIn",
            "account_identifier": "operator",
        },
        "provider": {
            "platform": "LinkedIn",
            "connector_kind": "OAUTH_API",
            "connector_name": "LinkedIn read-only profile setup",
            "connector_version": "0.0.0-contract-only",
            "terms_review_state": "REQUIRES_REVIEW",
            "terms_reference_uri": "https://www.linkedin.com/legal/user-agreement",
        },
        "purpose": {
            "kind": "CONNECTOR_READINESS_ASSESSMENT",
            "statement": "Record a future read-only connector boundary for the operator account.",
            "secondary_use": "PROHIBITED",
        },
        "grant": {
            "grant_kind": "OAUTH_API_REQUIRES_SEPARATE_TOKEN_FLOW",
            "grant_state": "RECORDED_NOT_ACTIVE",
            "authorization_basis": "USER_OWNED_ACCOUNT_ATTESTED",
            "access_mode": "API_CONNECTION_REQUIRES_SEPARATE_TOKEN_FLOW",
            "collection_state": "NOT_STARTED",
            "credential_material": "ABSENT",
            "credential_storage": "PROHIBITED",
            "oauth_state": "NOT_REQUESTED",
            "live_collection_state": "DISABLED",
            "network_access": False,
            "external_action_state": "PROHIBITED",
            "people_targeting": "PROHIBITED",
            "activation_requirement": "SEPARATE_EXPLICIT_CONNECTOR_GRANT_REQUIRED",
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
        "scopes": [
            {
                "scope_name": "profile_metadata",
                "source_surface": "Self profile metadata",
                "data_category": "ACCOUNT_PROFILE_METADATA",
                "access_intent": "READ_ONLY_IF_SEPARATELY_ENABLED",
                "minimization": "MINIMUM_NECESSARY",
                "private_counterparty_data": "EXCLUDED",
                "claim_extraction": "PROHIBITED",
            }
        ],
        "allowed_observation_types": [
            {
                "observation_type": "social.profile_metadata",
                "admission_state": "CONTRACTED_NOT_ENABLED",
                "claim_extraction": "PROHIBITED",
                "external_action_state": "PROHIBITED",
            }
        ],
        "retention": {
            "local_retention_days": 30,
            "raw_export_retention": "NOT_APPLICABLE",
            "path_retention": "NOT_RECORDED_IN_LEDGER",
        },
        "revocation": {
            "state": "MANUAL_REVOCATION_REQUIRED_IF_ACTIVATED",
            "operator_action": (
                "If later activated, revoke access at the provider and remove local token material."
            ),
        },
        "audit": {
            "receipt_required": True,
            "path_retention": "NOT_RECORDED_IN_LEDGER",
            "token_storage": "PROHIBITED",
            "execution_log": "REQUIRED_BEFORE_COLLECTION",
            "redaction_policy": "REQUIRED_BEFORE_COUNTERPARTY_DATA",
        },
    }


def _catalog_import(tmp_path: Path) -> tuple[EventLedger, dict[str, object]]:
    manifest = _write_private_manifest(tmp_path / "catalog-source.json", _catalog_source())
    ledger = EventLedger(tmp_path / "catalog" / "events.jsonl")
    return ledger, import_asset_catalog_source(ledger, manifest, attested=True)


def test_connector_grant_schema_is_closed_and_rejects_active_collection(tmp_path: Path) -> None:
    _, catalog = _catalog_import(tmp_path)
    source = _connector_grant_source(catalog)

    validate_connector_grant_source(source)
    assert load_connector_grant_source_schema()["additionalProperties"] is False

    active = deepcopy(source)
    active["grant"]["grant_state"] = "ACTIVE"  # type: ignore[index]
    with pytest.raises(ConnectorGrantContractError, match="RECORDED_NOT_ACTIVE"):
        validate_connector_grant_source(active)

    promoted_network = deepcopy(source)
    promoted_network["grant"]["network_access"] = True  # type: ignore[index]
    with pytest.raises(ConnectorGrantContractError, match="False"):
        validate_connector_grant_source(promoted_network)

    token_present = deepcopy(source)
    token_present["grant"]["credential_material"] = "PRESENT"  # type: ignore[index]
    with pytest.raises(ConnectorGrantContractError, match="ABSENT"):
        validate_connector_grant_source(token_present)


def test_connector_grant_rejects_incompatible_oauth_shape(tmp_path: Path) -> None:
    _, catalog = _catalog_import(tmp_path)
    source = _connector_grant_source(catalog)
    source["provider"]["connector_kind"] = "LOCAL_EXPORT"  # type: ignore[index]

    with pytest.raises(ConnectorGrantContractError, match="OAuth API"):
        validate_connector_grant_source(source)


def test_connector_grant_rejects_duplicate_scopes_and_outputs(tmp_path: Path) -> None:
    _, catalog = _catalog_import(tmp_path)
    source = _connector_grant_source(catalog)
    source["scopes"].append(deepcopy(source["scopes"][0]))  # type: ignore[union-attr,index]
    with pytest.raises(ConnectorGrantContractError, match="duplicate scope"):
        validate_connector_grant_source(source)

    source = _connector_grant_source(catalog)
    source["allowed_observation_types"].append(  # type: ignore[union-attr,index]
        deepcopy(source["allowed_observation_types"][0])  # type: ignore[index]
    )
    with pytest.raises(ConnectorGrantContractError, match="duplicate observation type"):
        validate_connector_grant_source(source)


def test_connector_grant_import_records_grant_observation(tmp_path: Path) -> None:
    ledger, catalog = _catalog_import(tmp_path)
    grant_manifest = _write_private_manifest(
        tmp_path / "grant-source.json",
        _connector_grant_source(catalog),
    )

    result = import_connector_grant_source(ledger, grant_manifest, attested=True)
    events = ledger.read_events()
    projection = ledger.projection()
    asset_id = result["asset_entity_id"]
    asset_view = projection.asset_view(asset_id)
    grant_observations = [
        observation
        for observation in asset_view["observations"]
        if observation["observation_type"] == CONNECTOR_GRANT_OBSERVATION_TYPE
    ]

    assert result["events_appended"] == 3
    assert result["events_skipped_existing"] == 0
    assert result["grant_state"] == "RECORDED_NOT_ACTIVE"
    assert result["authority"]["network_access"] is False
    assert result["authority"]["credential_material"] == "ABSENT"
    assert len(events) == 8
    assert all(event["authority_state"] == "NO_AUTHORITY" for event in events)
    assert len(grant_observations) == 1
    assert (
        grant_observations[0]["content"]["structured_payload"]["connector_grant"][
            "live_collection_state"
        ]
        == "DISABLED"
    )


def test_connector_grant_events_validate_and_replay(tmp_path: Path) -> None:
    ledger, catalog = _catalog_import(tmp_path)
    source = _connector_grant_source(catalog)
    binding = ledger.projection().entities[source["asset"]["entity_id"]]["attributes"][  # type: ignore[index]
        "asset_catalog_binding"
    ]
    events = build_connector_grant_events(
        source,
        source_sha256="1" * 64,
        source_size=2048,
        asset_binding=binding,
    )

    for event in events:
        validate_event(event)
    projection = ReadinProjection.replay([*ledger.read_events(), *events])

    assert len(events) == 3
    assert any(
        observation["observation_type"] == CONNECTOR_GRANT_OBSERVATION_TYPE
        for observation in projection.observations.values()
    )


def test_connector_grant_import_is_idempotent_and_rejects_reused_grant_id(
    tmp_path: Path,
) -> None:
    ledger, catalog = _catalog_import(tmp_path)
    source = _connector_grant_source(catalog)
    grant_manifest = _write_private_manifest(tmp_path / "grant-source.json", source)

    first = import_connector_grant_source(ledger, grant_manifest, attested=True)
    second = import_connector_grant_source(ledger, grant_manifest, attested=True)

    assert first["events_appended"] == 3
    assert second["events_appended"] == 0
    assert second["events_skipped_existing"] == 3

    changed = _connector_grant_source(catalog)
    changed["retention"]["local_retention_days"] = 60  # type: ignore[index]
    changed_manifest = _write_private_manifest(tmp_path / "changed-grant-source.json", changed)
    with pytest.raises(ConnectorGrantError, match="different source digest"):
        import_connector_grant_source(ledger, changed_manifest, attested=True)


def test_connector_grant_requires_private_attested_existing_catalog_asset(
    tmp_path: Path,
) -> None:
    ledger, catalog = _catalog_import(tmp_path)
    grant_manifest = _write_private_manifest(
        tmp_path / "grant-source.json",
        _connector_grant_source(catalog),
    )

    with pytest.raises(ConnectorGrantError, match="explicit attestation is required"):
        import_connector_grant_source(ledger, grant_manifest, attested=False)

    untracked_source = _connector_grant_source(catalog)
    untracked_source["asset"]["entity_id"] = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"  # type: ignore[index]
    untracked_manifest = _write_private_manifest(
        tmp_path / "untracked-grant.json", untracked_source
    )
    with pytest.raises(ConnectorGrantError, match="untracked asset"):
        import_connector_grant_source(ledger, untracked_manifest, attested=True)

    public_manifest = tmp_path / "public-grant.json"
    public_manifest.write_text(json.dumps(_connector_grant_source(catalog)), encoding="utf-8")
    with pytest.raises(ConnectorGrantError, match="not owner-only"):
        import_connector_grant_source(ledger, public_manifest, attested=True)


def test_workbench_exposes_recorded_connector_grant_without_live_collection(
    tmp_path: Path,
) -> None:
    ledger, catalog = _catalog_import(tmp_path)
    grant_manifest = _write_private_manifest(
        tmp_path / "grant-source.json",
        _connector_grant_source(catalog),
    )
    result = import_connector_grant_source(ledger, grant_manifest, attested=True)

    snapshot = build_workbench_snapshot(ledger.projection(), result["asset_entity_id"])
    setup = snapshot["selected_asset"]["governance"]["source_setup"]
    grant = snapshot["selected_asset"]["governance"]["connector_grant"]

    assert setup["connector_grant_state"] == "RECORDED_NOT_ACTIVE"
    assert setup["connector_grant_access_mode"] == "API_CONNECTION_REQUIRES_SEPARATE_TOKEN_FLOW"
    assert grant["grant_id"] == result["grant_id"]
    assert grant["collection_state"] == "NOT_STARTED"
    assert grant["credential_material"] == "ABSENT"
    assert grant["live_collection_state"] == "DISABLED"
    assert grant["people_targeting"] == "PROHIBITED"
    assert grant["scopes"][0]["private_counterparty_data"] == "EXCLUDED"


def test_cli_records_connector_grant(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ledger, catalog = _catalog_import(tmp_path)
    manifest = _write_private_manifest(
        tmp_path / "grant-source.json",
        _connector_grant_source(catalog),
    )

    missing_attestation = main(
        ["record-connector-grant", "--ledger", str(ledger.path), "--manifest", str(manifest)]
    )
    captured = capsys.readouterr()
    assert missing_attestation == 2
    assert "explicit attestation is required" in captured.err

    result = main(
        [
            "record-connector-grant",
            "--ledger",
            str(ledger.path),
            "--manifest",
            str(manifest),
            "--attest",
            "--occurred-at",
            "2026-09-04T13:00:00-05:00",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output["authority"]["network_access"] is False
    assert output["authority"]["live_collection_state"] == "DISABLED"
    assert output["events_appended"] == 3
