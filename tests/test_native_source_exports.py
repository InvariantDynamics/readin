from __future__ import annotations

import hashlib
import io
import json
import socket
import stat
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from test_connector_grants import _catalog_source, _connector_grant_source, _write_private_manifest
from test_github_public import repository_payload

from readin.asset_catalog import import_asset_catalog_source
from readin.cli import main
from readin.connector_grants import import_connector_grant_source
from readin.local_source_exports import LocalSourceExportError
from readin.native_source_exports import (
    NATIVE_SOURCE_ADAPTER,
    NativeSourceExportError,
    import_native_source_export,
    load_native_source_record_schema,
    parse_native_source,
    prepare_native_source_grant,
    validate_native_source_record,
)
from readin.source_capabilities import build_source_capabilities
from readin.store import EventLedger
from readin.workbench import build_workbench_snapshot

PROFILE = (
    b"First Name,Last Name,Address,Birth Date,Summary\r\n"
    b"Example,Operator,EXCLUDED_ADDRESS,EXCLUDED_DOB,EXCLUDED_SUMMARY\r\n"
)
TIME = "2026-09-04T13:00:00Z"


def _private(path: Path, raw: bytes) -> Path:
    path.write_bytes(raw)
    path.chmod(0o600)
    return path


def _zip(profile=PROFILE, extras=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("export/Profile.csv", profile)
        for name, content in (extras or {}).items():
            archive.writestr(name, content)
    return stream.getvalue()


def _setup(tmp_path, *, github=False, with_grant=True, grant_kind="LOCAL_EXPORT_ONLY"):
    catalog = _catalog_source()
    asset = catalog["assets"][0]
    if github:
        asset.update(
            {
                "asset_class": "SOFTWARE_REPOSITORY",
                "display_name": "Example READIN repository",
                "platform": "GitHub",
                "account_identifier": "InvariantDynamics/readin",
                "source_uri": "https://github.com/InvariantDynamics/readin",
            }
        )
    ledger = EventLedger(tmp_path / "catalog" / "events.jsonl")
    result = import_asset_catalog_source(
        ledger, _write_private_manifest(tmp_path / "catalog.json", catalog), attested=True
    )
    source = _connector_grant_source(result)
    source["asset"].update(
        {key: asset[key] for key in ("asset_class", "platform", "account_identifier")}
    )
    source["provider"].update(
        {
            "platform": asset["platform"],
            "connector_kind": "LOCAL_EXPORT",
            "connector_name": "Native export",
            "terms_review_state": "USER_ATTESTED_ALLOWED",
        }
    )
    source["grant"].update(
        {
            "grant_kind": grant_kind,
            "access_mode": "LOCAL_EXPORT_IMPORT_ONLY",
            "oauth_state": "NOT_REQUIRED",
        }
    )
    source["retention"]["raw_export_retention"] = "USER_MANAGED_NOT_RECORDED"
    if github:
        source["scopes"][0]["data_category"] = "OWNED_REPOSITORY_METADATA"
        source["allowed_observation_types"][0]["observation_type"] = (
            "github.public_repository_metadata.imported"
        )
    if grant_kind != "LOCAL_EXPORT_ONLY":
        source["provider"]["connector_kind"] = "OAUTH_API"
        source["grant"].update(
            {
                "access_mode": "API_CONNECTION_REQUIRES_SEPARATE_TOKEN_FLOW",
                "oauth_state": "NOT_REQUESTED",
            }
        )
    if with_grant:
        import_connector_grant_source(
            ledger, _write_private_manifest(tmp_path / "grant.json", source), attested=True
        )
    return ledger, source


def _run(ledger, grant, path, parser="LINKEDIN_PROFILE_CSV", **kwargs):
    return import_native_source_export(
        ledger,
        path,
        parser=parser,
        asset_id=grant["asset"]["entity_id"],
        grant_id=grant["grant_id"],
        observed_at=kwargs.pop("observed_at", TIME),
        occurred_at=kwargs.pop("occurred_at", "2026-09-04T13:05:00Z"),
        attested=kwargs.pop("attested", True),
        **kwargs,
    )


@pytest.mark.parametrize(
    "parser,raw",
    [
        ("LINKEDIN_PROFILE_CSV", PROFILE),
        (
            "LINKEDIN_PROFILE_ZIP",
            _zip(
                extras={"Messages.csv": "EXCLUDED_MESSAGE", "Connections.csv": "EXCLUDED_CONTACT"}
            ),
        ),
    ],
)
def test_linkedin_native_preview_import_and_retry(tmp_path, monkeypatch, parser, raw):
    ledger, grant = _setup(tmp_path)
    path = _private(tmp_path / "export", raw)

    def deny(*args, **kwargs):
        raise AssertionError("native import attempted network")

    monkeypatch.setattr(socket, "socket", deny)
    before = ledger.path.read_bytes()
    preview = _run(ledger, grant, path, parser, preview=True, attested=False)
    assert ledger.path.read_bytes() == before
    assert preview["events_to_append"] == 3
    assert preview["record_preview"] == {"display_name": "Example Operator"}
    assert preview["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert preview["identity_binding"] == "USER_ATTESTED_CATALOG_ASSOCIATION"
    result = _run(ledger, grant, path, parser)
    assert result["events_appended"] == 3
    if parser.endswith("ZIP"):
        assert result["archive_entries_skipped"] == 2
        assert result["selected_member_sha256"] == hashlib.sha256(PROFILE).hexdigest()
    contents = ledger.path.read_text()
    assert "EXCLUDED_" not in contents
    assert str(path) not in contents
    assert result["excluded_field_count"] == 3
    after = ledger.path.read_bytes()
    assert (
        _run(ledger, grant, path, parser, occurred_at="2026-09-05T13:05:00Z")["status"]
        == "ALREADY_IMPORTED"
    )
    assert ledger.path.read_bytes() == after
    with pytest.raises(NativeSourceExportError, match="original observed time"):
        _run(ledger, grant, path, parser, observed_at="2026-09-04T12:59:00Z")
    projection = ledger.projection()
    assert not projection.claims
    snapshot = build_workbench_snapshot(projection, grant["asset"]["entity_id"])
    batch = snapshot["selected_asset"]["governance"]["source_exports"][0]
    assert batch["parser"] == parser
    assert batch["observation_count"] == 1
    assert snapshot["source_capabilities"]["local_imported_record_count"] == 1


def test_saved_github_json_uses_local_provenance_and_excludes_owner_data(tmp_path):
    ledger, grant = _setup(tmp_path, github=True)
    raw = json.dumps(repository_payload()).encode()
    result = _run(
        ledger, grant, _private(tmp_path / "repository.json", raw), "GITHUB_REPOSITORY_JSON"
    )
    observation = ledger.projection().observations[result["observation_ids"][0]]
    assert observation["observation_type"] == "github.public_repository_metadata.imported"
    assert observation["provenance"]["adapter"] == NATIVE_SOURCE_ADAPTER
    record = observation["content"]["structured_payload"]["record"]
    assert record["full_name"] == "InvariantDynamics/readin"
    assert record["stargazers_count"] == 3
    text = ledger.path.read_text()
    assert "not-for-observation" not in text
    assert "excluded-person" not in text
    assert "GITHUB_PUBLIC_REPOSITORY_API" not in text
    assert "http_status" not in text


@pytest.mark.parametrize(
    "updates",
    [
        {"private": True},
        {"full_name": "other/repo"},
        {"html_url": "https://evil.example/repo"},
        {"stargazers_count": -1},
    ],
)
def test_github_identity_and_field_rejections_leave_ledger_unchanged(tmp_path, updates):
    ledger, grant = _setup(tmp_path, github=True)
    raw = json.dumps(repository_payload(**updates)).encode()
    before = ledger.path.read_bytes()
    with pytest.raises(NativeSourceExportError):
        _run(ledger, grant, _private(tmp_path / "repository.json", raw), "GITHUB_REPOSITORY_JSON")
    assert ledger.path.read_bytes() == before


@pytest.mark.parametrize(
    "raw",
    [
        b"First Name,First Name,Last Name\nA,B,C\n",
        b"First Name,Last Name\nA,B\nC,D\n",
        b"First Name,Last Name\nA\n",
        b"First Name,Last Name\n,\n",
        b"First Name,Last Name\nA,\xff\n",
        b"Contacts,Email\nOther,private\n",
        b'First Name,Last Name\n"unfinished',
        b"First Name,Last Name\nA,\x00\n",
    ],
)
def test_profile_layout_rejections(tmp_path, raw):
    ledger, grant = _setup(tmp_path)
    with pytest.raises(NativeSourceExportError):
        _run(ledger, grant, _private(tmp_path / "Profile.csv", raw))


@pytest.mark.parametrize(
    "extra",
    [
        {"other/Profile.csv": "First Name,Last Name\nOther,Person"},
        {"../outside.csv": "ignored"},
        {"/absolute.csv": "ignored"},
        {"folder\\escape.csv": "ignored"},
    ],
)
def test_zip_ambiguity_and_unsafe_paths(tmp_path, extra):
    ledger, grant = _setup(tmp_path)
    before = ledger.path.read_bytes()
    with pytest.raises(NativeSourceExportError):
        _run(
            ledger,
            grant,
            _private(tmp_path / "archive.zip", _zip(extras=extra)),
            "LINKEDIN_PROFILE_ZIP",
        )
    assert ledger.path.read_bytes() == before


def test_zip_symlink_and_bomb_rejected(tmp_path):
    ledger, grant = _setup(tmp_path)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        entry = zipfile.ZipInfo("Profile.csv")
        entry.create_system = 3
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, PROFILE)
    for raw in (stream.getvalue(), _zip(profile=b"a" * 1048577), b"not a zip"):
        with pytest.raises(NativeSourceExportError):
            _run(ledger, grant, _private(tmp_path / "archive.zip", raw), "LINKEDIN_PROFILE_ZIP")


def test_bom_and_quoted_names(tmp_path):
    ledger, grant = _setup(tmp_path)
    path = _private(
        tmp_path / "Profile.csv", b'\xef\xbb\xbfFirst Name,Last Name\r\n"Example, Jr.",Operator\r\n'
    )
    assert _run(ledger, grant, path)["record_preview"]["display_name"] == "Example, Jr. Operator"


def test_grant_readiness_is_separate_from_import_coverage(tmp_path):
    ledger, grant = _setup(tmp_path, with_grant=False)
    coverage = build_source_capabilities(ledger.projection())
    assert len(coverage["asset_classes"]) == 11
    assert coverage["imported_asset_count"] == 0
    assert all(p["state"] == "GRANT_REQUIRED" for p in coverage["assets"][0]["parsers"])
    assert (
        next(c for c in coverage["asset_classes"] if c["asset_class"] == "EMAIL_ACCOUNT")[
            "parser_state"
        ]
        == "PARSER_NOT_IMPLEMENTED"
    )
    import_connector_grant_source(
        ledger, _write_private_manifest(tmp_path / "grant.json", grant), attested=True
    )
    coverage = build_source_capabilities(ledger.projection())
    assert all(p["state"] == "READY_FOR_LOCAL_IMPORT" for p in coverage["assets"][0]["parsers"])
    assert coverage["imported_asset_count"] == 0
    _run(ledger, grant, _private(tmp_path / "Profile.csv", PROFILE))
    coverage = build_source_capabilities(ledger.projection())
    assert coverage["imported_asset_count"] == 1
    assert coverage["coverage_state"] == "NOT_ESTABLISHED"
    assert coverage["live_account_connections"] == "NOT_IMPLEMENTED"


def test_oauth_readiness_cannot_run_native_import(tmp_path):
    ledger, grant = _setup(tmp_path, grant_kind="OAUTH_API_REQUIRES_SEPARATE_TOKEN_FLOW")
    coverage = build_source_capabilities(ledger.projection())
    assert all(p["state"] == "INCOMPATIBLE_GRANT" for p in coverage["assets"][0]["parsers"])
    with pytest.raises(LocalSourceExportError, match="LOCAL_EXPORT_ONLY"):
        _run(ledger, grant, _private(tmp_path / "Profile.csv", PROFILE))


def test_cli_preview_import_capabilities_and_attestation(tmp_path, capsys):
    ledger, grant = _setup(tmp_path)
    path = _private(tmp_path / "Profile.csv", PROFILE)
    args = [
        "import-native-source-export",
        "--ledger",
        str(ledger.path),
        "--source",
        str(path),
        "--parser",
        "LINKEDIN_PROFILE_CSV",
        "--asset",
        grant["asset"]["entity_id"],
        "--grant",
        grant["grant_id"],
        "--observed-at",
        TIME,
    ]
    assert main(args) == 2
    assert "attestation" in capsys.readouterr().err
    assert main([*args, "--preview"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "PREVIEW"
    assert main([*args, "--attest"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "IMPORTED"
    assert main(["list-source-capabilities", "--ledger", str(ledger.path)]) == 0
    assert json.loads(capsys.readouterr().out)["imported_asset_count"] == 1


def test_normalized_contract_is_closed(tmp_path):
    ledger, grant = _setup(tmp_path)
    binding = ledger.projection().entities[grant["asset"]["entity_id"]]["attributes"][
        "asset_catalog_binding"
    ]
    schema = load_native_source_record_schema()
    Draft202012Validator.check_schema(schema)
    parsed = parse_native_source(PROFILE, "LINKEDIN_PROFILE_CSV", binding)
    validate_native_source_record(parsed)
    modified = deepcopy(parsed)
    modified["record"]["address"] = "prohibited"
    with pytest.raises(NativeSourceExportError):
        validate_native_source_record(modified)


@pytest.mark.parametrize(
    "github,parser", [(False, "LINKEDIN_PROFILE_CSV"), (True, "GITHUB_REPOSITORY_JSON")]
)
def test_generated_grant_round_trip(tmp_path, github, parser):
    ledger, original = _setup(tmp_path, github=github, with_grant=False)
    before = ledger.path.read_bytes()
    manifest = prepare_native_source_grant(
        ledger.projection(),
        original["asset"]["entity_id"],
        parser,
        declared_at="2026-09-04T12:30:00Z",
    )
    assert ledger.path.read_bytes() == before
    assert manifest["provider"]["terms_review_state"] == "REQUIRES_REVIEW"
    import_connector_grant_source(
        ledger, _write_private_manifest(tmp_path / "generated-grant.json", manifest), attested=True
    )
    raw = json.dumps(repository_payload()).encode() if github else PROFILE
    assert (
        _run(ledger, manifest, _private(tmp_path / "source", raw), parser)["status"] == "IMPORTED"
    )


@pytest.mark.parametrize("prefix", [1, 2])
def test_native_retry_after_complete_prefix_interruption(tmp_path, monkeypatch, prefix):
    ledger, grant = _setup(tmp_path)
    path = _private(tmp_path / "Profile.csv", PROFILE)
    original_append = ledger.append_batch

    def interrupted(batch):
        original_append(batch[:prefix])
        raise OSError("simulated complete-prefix interruption")

    monkeypatch.setattr(ledger, "append_batch", interrupted)
    with pytest.raises(OSError):
        _run(ledger, grant, path)
    monkeypatch.setattr(ledger, "append_batch", original_append)
    result = _run(ledger, grant, path)
    assert result["events_appended"] == 3 - prefix
    assert _run(ledger, grant, path)["status"] == "ALREADY_IMPORTED"


def test_zip_only_opens_profile_member(tmp_path, monkeypatch):
    ledger, grant = _setup(tmp_path)
    path = _private(tmp_path / "archive.zip", _zip(extras={"Messages.csv": "NEVER_OPEN"}))
    opened = []
    original = zipfile.ZipFile.open

    def checked_open(self, member, *args, **kwargs):
        opened.append(member.filename)
        assert member.filename == "export/Profile.csv"
        return original(self, member, *args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "open", checked_open)
    assert _run(ledger, grant, path, "LINKEDIN_PROFILE_ZIP")["archive_entries_skipped"] == 1
    assert opened == ["export/Profile.csv"]


def _multi_asset_fixture(tmp_path):
    catalog = _catalog_source()
    social = catalog["assets"][0]
    repository = deepcopy(social)
    repository.update(
        {
            "asset_class": "SOFTWARE_REPOSITORY",
            "display_name": "Example repository",
            "platform": "GitHub",
            "account_identifier": "InvariantDynamics/readin",
            "source_uri": "https://github.com/InvariantDynamics/readin",
        }
    )
    email = deepcopy(social)
    email.update(
        {
            "asset_class": "EMAIL_ACCOUNT",
            "display_name": "Example email account (catalog only)",
            "platform": "Gmail",
            "account_identifier": "example@example.invalid",
            "source_uri": None,
        }
    )
    catalog["assets"].extend([repository, email])
    ledger = EventLedger(tmp_path / "catalog" / "events.jsonl")
    imported = import_asset_catalog_source(
        ledger, _write_private_manifest(tmp_path / "catalog.json", catalog), attested=True
    )
    for index, parser, raw in (
        (0, "LINKEDIN_PROFILE_ZIP", _zip()),
        (1, "GITHUB_REPOSITORY_JSON", json.dumps(repository_payload()).encode()),
    ):
        asset_id = imported["assets"][index]["entity_id"]
        grant = prepare_native_source_grant(
            ledger.projection(), asset_id, parser, declared_at="2026-09-04T12:30:00Z"
        )
        import_connector_grant_source(
            ledger,
            _write_private_manifest(tmp_path / f"grant-{index}.json", grant),
            attested=True,
            occurred_at="2026-09-04T13:05:00Z",
        )
        _run(ledger, grant, _private(tmp_path / f"native-{index}.export", raw), parser)
    return ledger


def test_multi_asset_source_coverage(tmp_path):
    ledger = _multi_asset_fixture(tmp_path)
    coverage = build_source_capabilities(ledger.projection())
    assert coverage["catalog_asset_count"] == 3
    assert coverage["imported_asset_count"] == 2
    assert coverage["local_imported_record_count"] == 2
    email = next(a for a in coverage["assets"] if a["asset_class"] == "EMAIL_ACCOUNT")
    assert email["parser_state"] == "PARSER_NOT_IMPLEMENTED"
    assert email["imported_record_count"] == 0
    assert coverage["separate_public_repository_runner"]["recorded_observation_count"] == 0
