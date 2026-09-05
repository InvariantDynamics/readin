from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_connector_grants import _catalog_import, _connector_grant_source, _write_private_manifest

from readin.cli import main
from readin.connector_grants import import_connector_grant_source
from readin.local_source_exports import (
    LocalSourceExportError,
    build_local_source_export_events,
    import_local_source_export,
    load_local_source_export,
    load_local_source_export_schema,
    validate_local_source_export,
)
from readin.projection import ProjectionError
from readin.workbench import build_workbench_snapshot


def _setup(tmp_path: Path, *, local: bool = True, retention: str = "USER_MANAGED_NOT_RECORDED"):
    ledger, catalog = _catalog_import(tmp_path)
    grant = _connector_grant_source(catalog)
    if local:
        grant["provider"]["connector_kind"] = "SOCIAL_EXPORT"
        grant["grant"].update(
            {
                "grant_kind": "LOCAL_EXPORT_ONLY",
                "access_mode": "LOCAL_EXPORT_IMPORT_ONLY",
                "oauth_state": "NOT_REQUIRED",
            }
        )
    grant["retention"]["raw_export_retention"] = retention
    import_connector_grant_source(
        ledger, _write_private_manifest(tmp_path / "grant.json", grant), attested=True
    )
    source = {
        "schema_version": "readin.local-source-export.v0.1",
        "export_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        "grant_id": grant["grant_id"],
        "asset_entity_id": grant["asset"]["entity_id"],
        "prepared_at": "2026-09-04T12:10:00Z",
        "parser": "GENERIC_JSON_OBSERVATION_BATCH",
        "handling": {
            "owner_attestation": "SELF_OR_CONTROLLED_ASSETS_ONLY",
            "private_counterparty_data": "EXCLUDED",
            "credential_material": "ABSENT",
            "network_access": False,
            "raw_export_retention": "USER_MANAGED_NOT_RECORDED",
        },
        "observations": [
            {
                "record_key": "profile-1",
                "observation_type": "social.profile_metadata",
                "observed_at": "2026-09-04T12:00:00Z",
                "structured_payload": {
                    "platform": "LinkedIn",
                    "account_identifier": "operator",
                    "display_name": "Example operator",
                    "profile_url": "https://www.linkedin.com/in/operator/",
                },
            }
        ],
    }
    return ledger, source


def _import(ledger, tmp_path, source, **kwargs):
    path = _write_private_manifest(tmp_path / "export.json", source)
    options = {
        "grant_id": source["grant_id"],
        "attested": True,
        "occurred_at": "2026-09-04T12:15:00Z",
        **kwargs,
    }
    return import_local_source_export(ledger, path, **options)


def test_import_preview_retry_and_workbench(tmp_path):
    ledger, source = _setup(tmp_path)
    before = ledger.path.read_bytes()
    preview = _import(ledger, tmp_path, source, preview=True, attested=False)
    assert preview["events_to_append"] == 3
    assert preview["events_appended"] == 0
    assert ledger.path.read_bytes() == before
    receipt = _import(ledger, tmp_path, source)
    assert receipt["events_appended"] == 3
    after = ledger.path.read_bytes()
    retry = _import(ledger, tmp_path, source, occurred_at="2026-09-05T12:00:00Z")
    assert retry["status"] == "ALREADY_IMPORTED"
    assert retry["events_skipped_existing"] == 3
    assert ledger.path.read_bytes() == after
    projection = ledger.projection()
    observation = projection.observations[receipt["observation_ids"][0]]
    assert (
        observation["content"]["structured_payload"]["record"]["display_name"] == "Example operator"
    )
    assert not projection.claims
    assert str(tmp_path) not in after.decode()
    assert all(event["authority_state"] == "NO_AUTHORITY" for event in ledger.read_events())
    snapshot = build_workbench_snapshot(projection, source["asset_entity_id"])
    imports = snapshot["selected_asset"]["governance"]["source_exports"]
    assert imports[0]["observation_count"] == 1
    assert imports[0]["state"] == "IMPORTED"


@pytest.mark.parametrize("prefix_count", [1, 2])
def test_partial_import_recovers_and_rejects_changed_source(tmp_path, prefix_count):
    ledger, source = _setup(tmp_path)
    path = _write_private_manifest(tmp_path / "export.json", source)
    _, digest, size = load_local_source_export(path)
    events = build_local_source_export_events(
        source,
        source_sha256=digest,
        source_size=size,
        projection=ledger.projection(),
        occurred_at="2026-09-04T12:15:00Z",
    )
    ledger.append_batch(events[:prefix_count])
    before = ledger.path.read_bytes()
    changed = deepcopy(source)
    changed["observations"][0]["structured_payload"]["display_name"] = "Changed name"
    with pytest.raises(LocalSourceExportError, match="different source digest|conflicts"):
        _import(ledger, tmp_path, changed)
    assert ledger.path.read_bytes() == before
    result = _import(ledger, tmp_path, source)
    assert result["events_appended"] == 3 - prefix_count


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s.update(extra="forbidden"),
        lambda s: s["handling"].update(network_access=True),
        lambda s: s["handling"].update(credential_material="PRESENT"),
        lambda s: s["observations"][0]["structured_payload"].update(access_token="secret"),
        lambda s: s["observations"][0]["structured_payload"].update(contacts=[]),
        lambda s: s["observations"][0]["structured_payload"].update(
            profile_url="https://example.com/?token=secret"
        ),
        lambda s: s["observations"][0].update(observation_type="private.message"),
        lambda s: s["observations"].append(deepcopy(s["observations"][0])),
        lambda s: s["observations"][0].update(observed_at="2026-09-05T12:00:00Z"),
    ],
)
def test_closed_schema_rejects_uncontracted_content(tmp_path, mutation):
    ledger, source = _setup(tmp_path)
    assert load_local_source_export_schema()["additionalProperties"] is False
    mutation(source)
    before = ledger.path.read_bytes()
    with pytest.raises(LocalSourceExportError):
        _import(ledger, tmp_path, source)
    assert ledger.path.read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("platform", "Other"),
        ("account_identifier", "counterparty"),
        ("profile_url", "https://example.com/other"),
    ],
)
def test_account_binding(tmp_path, field, value):
    ledger, source = _setup(tmp_path)
    source["observations"][0]["structured_payload"][field] = value
    before = ledger.path.read_bytes()
    with pytest.raises(LocalSourceExportError, match="catalog"):
        _import(ledger, tmp_path, source)
    assert ledger.path.read_bytes() == before


@pytest.mark.parametrize(
    "local,retention",
    [
        (False, "USER_MANAGED_NOT_RECORDED"),
        (True, "DELETE_AFTER_IMPORT_REQUIRED"),
        (True, "NOT_APPLICABLE"),
    ],
)
def test_incompatible_grants(tmp_path, local, retention):
    ledger, source = _setup(tmp_path, local=local, retention=retention)
    before = ledger.path.read_bytes()
    with pytest.raises(LocalSourceExportError, match="LOCAL_EXPORT_ONLY|retention"):
        _import(ledger, tmp_path, source)
    assert ledger.path.read_bytes() == before


def test_missing_grant_and_wrong_explicit_grant(tmp_path):
    ledger, source = _setup(tmp_path)
    with pytest.raises(LocalSourceExportError, match="--grant"):
        _import(ledger, tmp_path, source, grant_id="eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee")
    source["grant_id"] = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    with pytest.raises(LocalSourceExportError, match="exactly one"):
        _import(ledger, tmp_path, source)


def test_reader_rejects_public_symlink_git_and_malformed_files(tmp_path):
    _, source = _setup(tmp_path)
    path = _write_private_manifest(tmp_path / "export.json", source)
    path.chmod(0o644)
    with pytest.raises(LocalSourceExportError, match="owner-only"):
        load_local_source_export(path)
    path.chmod(0o600)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    from readin.connector_grants import ConnectorGrantError

    with pytest.raises(ConnectorGrantError, match="symbolic link"):
        load_local_source_export(link)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    with pytest.raises(ConnectorGrantError, match="Git"):
        load_local_source_export(_write_private_manifest(repo / "export.json", source))
    for raw in ('{"x":1,"x":2}', '{"x":NaN}', "[]", "{invalid", "x" * 1_048_577):
        path.write_text(raw)
        with pytest.raises(LocalSourceExportError):
            load_local_source_export(path)


def test_batch_validation_failure_leaves_ledger_unchanged(tmp_path):
    ledger, source = _setup(tmp_path)
    path = _write_private_manifest(tmp_path / "export.json", source)
    _, digest, size = load_local_source_export(path)
    events = build_local_source_export_events(
        source,
        source_sha256=digest,
        source_size=size,
        projection=ledger.projection(),
        occurred_at="2026-09-04T12:15:00Z",
    )
    events[-1]["payload"]["observation"]["subject_entities"] = [
        "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    ]
    before = ledger.path.read_bytes()
    with pytest.raises(ProjectionError):
        ledger.append_batch(events)
    assert ledger.path.read_bytes() == before


def test_cli_preview_attestation_and_import(tmp_path, capsys):
    ledger, source = _setup(tmp_path)
    path = _write_private_manifest(tmp_path / "export.json", source)
    args = [
        "import-local-source-export",
        "--ledger",
        str(ledger.path),
        "--source",
        str(path),
        "--grant",
        source["grant_id"],
    ]
    assert main(args) == 2
    assert "attestation" in capsys.readouterr().err
    assert main([*args, "--preview"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PREVIEW"
    assert main([*args, "--attest"]) == 0
    assert json.loads(capsys.readouterr().out)["events_appended"] == 3


def test_schema_positive(tmp_path):
    _, source = _setup(tmp_path)
    validate_local_source_export(source)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda g: g["grant"].update(network_access=True),
        lambda g: g["grant"].update(grant_state="ACTIVE"),
        lambda g: g["provider"].update(connector_kind="OAUTH_API"),
        lambda g: g.update(network_access=True),
        lambda g: g.update(source_digest_sha256="0" * 64),
        lambda g: g.update(scopes=[]),
        lambda g: g["allowed_observation_types"][0].update(observation_type="uncontracted.output"),
    ],
)
def test_revalidates_recorded_grant_payload(tmp_path, mutation):
    ledger, source = _setup(tmp_path)
    projection = ledger.projection()
    observation = next(
        o
        for o in projection.observations.values()
        if o["observation_type"] == "asset_connector.grant_declared"
    )
    mutation(observation["content"]["structured_payload"]["connector_grant"])
    with pytest.raises(LocalSourceExportError):
        build_local_source_export_events(
            source,
            source_sha256="5" * 64,
            source_size=1024,
            projection=projection,
            occurred_at="2026-09-04T12:15:00Z",
        )


def test_multi_record_partial_import_summary_and_no_network(tmp_path, monkeypatch):
    import socket

    ledger, source = _setup(tmp_path)
    second = deepcopy(source["observations"][0])
    second["record_key"] = "profile-2"
    second["observed_at"] = "2026-09-04T12:01:00Z"
    source["observations"].append(second)
    path = _write_private_manifest(tmp_path / "export.json", source)
    _, digest, size = load_local_source_export(path)
    events = build_local_source_export_events(
        source,
        source_sha256=digest,
        source_size=size,
        projection=ledger.projection(),
        occurred_at="2026-09-04T12:15:00Z",
    )
    ledger.append_batch(events[:3])
    snapshot = build_workbench_snapshot(ledger.projection(), source["asset_entity_id"])
    assert (
        snapshot["selected_asset"]["governance"]["source_exports"][0]["state"] == "PARTIAL_IMPORT"
    )

    def forbid_network(*args, **kwargs):
        raise AssertionError("local import must not create a network socket")

    monkeypatch.setattr(socket, "socket", forbid_network)
    result = _import(ledger, tmp_path, source)
    assert result["events_appended"] == 1
    assert result["observation_count"] == 2
    assert _import(ledger, tmp_path, source)["status"] == "ALREADY_IMPORTED"
    observations = [ledger.projection().observations[key] for key in result["observation_ids"]]
    assert len({o["source_artifact_id"] for o in observations}) == 1
    assert len({o["observer_frame_id"] for o in observations}) == 1
