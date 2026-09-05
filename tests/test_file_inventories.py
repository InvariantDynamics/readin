from __future__ import annotations

import hashlib
import io
import json
import socket
import stat
import zipfile

import pytest
from test_connector_grants import _catalog_source, _write_private_manifest
from test_native_source_exports import _private, _run

from readin.asset_catalog import import_asset_catalog_source
from readin.cli import main
from readin.connector_grants import ConnectorGrantError, import_connector_grant_source
from readin.local_source_exports import LocalSourceExportError
from readin.native_source_exports import (
    NativeSourceExportError,
    parse_native_source,
    prepare_native_source_grant,
    validate_native_source_record,
)
from readin.source_capabilities import build_source_capabilities
from readin.store import EventLedger
from readin.workbench import build_workbench_snapshot

PARSER = "DOCUMENT_COLLECTION_ZIP"
BINDING = {"asset_class": "DOCUMENT_COLLECTION", "platform": "Local"}


def _archive(entries=None):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in entries or [
            ("Project/", b""),
            ("Project/notes.txt", b"EXCLUDED_PRIVATE_CONTENT"),
            ("Project/budget.csv", b"EXCLUDED_FINANCIAL_CONTENT"),
        ]:
            archive.writestr(name, raw)
    return buffer.getvalue()


def _inventory_setup(tmp_path, *, local_files=False, platform="Local", with_grant=True):
    catalog = _catalog_source()
    asset = catalog["assets"][0]
    asset.update(
        asset_class="LOCAL_FILE_COLLECTION" if local_files else "DOCUMENT_COLLECTION",
        display_name="Example selected files" if local_files else "Example owned documents",
        platform=platform,
        account_identifier="example-owned-inventory",
        source_uri=None,
        collection_mode="LOCAL_EXPORT_IMPORT_ONLY",
    )
    asset["connector_intent"].update(
        connector_kind="LOCAL_EXPORT",
        connection_state="EXPORT_IMPORT_READY",
        oauth_state="NOT_REQUIRED",
    )
    ledger = EventLedger(tmp_path / "catalog" / "events.jsonl")
    result = import_asset_catalog_source(
        ledger, _write_private_manifest(tmp_path / "catalog.json", catalog), attested=True
    )
    parser = "LOCAL_FILE_COLLECTION_ZIP" if local_files else PARSER
    grant = prepare_native_source_grant(
        ledger.projection(),
        result["assets"][0]["entity_id"],
        parser,
        declared_at="2026-09-04T12:30:00Z",
    )
    if with_grant:
        import_connector_grant_source(
            ledger, _write_private_manifest(tmp_path / "grant.json", grant), attested=True
        )
    return ledger, grant, parser


@pytest.mark.parametrize(
    "local_files,platform", [(False, "Local"), (True, "My files"), (False, "Drive")]
)
def test_inventory_preview_import_retry_and_coverage(tmp_path, monkeypatch, local_files, platform):
    ledger, grant, parser = _inventory_setup(tmp_path, local_files=local_files, platform=platform)
    raw = _archive()
    path = _private(tmp_path / "selected.zip", raw)

    def deny(*args, **kwargs):
        raise AssertionError("inventory attempted member content or network access")

    monkeypatch.setattr(zipfile.ZipFile, "open", deny)
    monkeypatch.setattr(socket, "socket", deny)
    before = ledger.path.read_bytes()
    result = _run(ledger, grant, path, parser, preview=True, attested=False)
    assert ledger.path.read_bytes() == before
    assert result["file_entry_count"] == 2
    assert result["observation_count"] == 1
    assert result["member_content_read"] is False
    assert result["archive_entry_names_recorded"] is True
    assert result["source_path_recorded_in_ledger"] is False
    assert result["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert result["archive_entries_skipped"] == 1
    assert result["excluded_field_count"] == 14
    assert result["content_verification"] == "NOT_PERFORMED"
    record = result["record_preview"]
    assert record["file_count"] == 2
    assert record["total_declared_bytes"] == 50
    assert [row["entry_name"] for row in record["entries"]] == [
        "Project/budget.csv",
        "Project/notes.txt",
    ]
    assert _run(ledger, grant, path, parser)["status"] == "IMPORTED"
    after = ledger.path.read_bytes()
    assert b"EXCLUDED_" not in after
    assert str(path).encode() not in after
    assert _run(ledger, grant, path, parser)["status"] == "ALREADY_IMPORTED"
    assert ledger.path.read_bytes() == after
    with pytest.raises(NativeSourceExportError, match="original observed time"):
        _run(ledger, grant, path, parser, observed_at="2026-09-04T12:59:00Z")
    projection = ledger.projection()
    assert len(projection.assets) == 1
    assert not projection.claims
    coverage = build_source_capabilities(projection)
    assert coverage["local_imported_record_count"] == 1
    assert coverage["assets"][0]["parsers"][0]["state"] == "READY_FOR_LOCAL_IMPORT"
    snapshot = build_workbench_snapshot(projection, grant["asset"]["entity_id"])
    assert snapshot["selected_asset"]["governance"]["source_exports"][0]["parser"] == parser


@pytest.mark.parametrize(
    "name",
    [
        "../secret",
        "/absolute",
        "a/../b",
        "a//b",
        "./b",
        "C:secret",
        "a\\b",
        "a\nb",
        "a\u202eb",
        "x" * 513,
    ],
)
def test_inventory_rejects_unsafe_names(name):
    with pytest.raises(NativeSourceExportError, match="unsafe"):
        parse_native_source(_archive([(name, b"x")]), PARSER, BINDING)


@pytest.mark.parametrize(
    "names", [("A.txt", "a.txt"), ("é.txt", "e\u0301.txt"), ("dir", "dir/"), ("dir", "dir/file")]
)
def test_inventory_rejects_ambiguous_paths(names):
    with pytest.raises(NativeSourceExportError, match="ambiguous|conflicts"):
        parse_native_source(_archive([(name, b"") for name in names]), PARSER, BINDING)


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFSOCK, stat.S_IFCHR])
def test_inventory_rejects_non_regular_entries(mode):
    info = zipfile.ZipInfo("entry")
    info.create_system = 3
    info.external_attr = (mode | 0o600) << 16
    with pytest.raises(NativeSourceExportError, match="type"):
        parse_native_source(_archive([(info, b"target")]), PARSER, BINDING)


def test_inventory_does_not_verify_crc_or_decompress_content(monkeypatch):
    raw = _archive([("notes.txt", b"x" * 100000)])

    def deny(*args, **kwargs):
        raise AssertionError("member decompression forbidden")

    monkeypatch.setattr(zipfile.ZipFile, "open", deny)
    parsed = parse_native_source(raw, PARSER, BINDING)
    assert parsed["record"]["entries"][0]["size_bytes"] == 100000
    assert parsed["record"]["content_verification"] == "NOT_PERFORMED"


@pytest.mark.parametrize("kind", ["encrypted", "nul", "oversize", "entries"])
def test_inventory_rejects_invalid_directory_metadata(monkeypatch, kind):
    raw = _archive()
    original = zipfile.ZipFile.infolist

    def changed(self):
        rows = original(self)
        if kind == "encrypted":
            rows[-1].flag_bits |= 1
        elif kind == "nul":
            rows[-1].orig_filename += "\x00hidden"
        elif kind == "oversize":
            rows[-1].file_size = 1099511627777
        else:
            rows = rows * 700
        return rows

    monkeypatch.setattr(zipfile.ZipFile, "infolist", changed)
    with pytest.raises(NativeSourceExportError):
        parse_native_source(raw, PARSER, BINDING)


@pytest.mark.parametrize("raw", [b"not zip", _archive([("empty/", b"")]), _archive()[:-30]])
def test_inventory_rejects_malformed_or_empty_archives(raw):
    with pytest.raises(NativeSourceExportError):
        parse_native_source(raw, PARSER, BINDING)


@pytest.mark.parametrize(
    "mutation",
    [
        "content",
        "path",
        "count",
        "size",
        "crc",
        "duplicate",
        "unsafe",
        "verification",
        "exclusions",
    ],
)
def test_inventory_closed_output_contract(mutation):
    parsed = parse_native_source(_archive(), PARSER, BINDING)
    record = parsed["record"]
    if mutation == "content":
        record["entries"][0]["content"] = "not allowed"
    elif mutation == "path":
        record["source_path"] = "/private/example"
    elif mutation == "count":
        record["file_count"] += 1
    elif mutation == "size":
        record["total_declared_bytes"] += 1
    elif mutation == "crc":
        record["entries"][0]["crc32"] = "not crc"
    elif mutation == "duplicate":
        record["entries"][1]["entry_name"] = record["entries"][0]["entry_name"]
    elif mutation == "unsafe":
        record["entries"][0]["entry_name"] = "../secret"
    elif mutation == "verification":
        record["content_verification"] = "VERIFIED"
    else:
        parsed["excluded_field_count"] = 0
    with pytest.raises(NativeSourceExportError):
        validate_native_source_record(parsed)


def test_inventory_wrong_grant_rejected_before_file_read(tmp_path, monkeypatch):
    ledger, grant, parser = _inventory_setup(tmp_path, with_grant=False)
    before = ledger.path.read_bytes()
    assert (
        build_source_capabilities(ledger.projection())["assets"][0]["parsers"][0]["state"]
        == "GRANT_REQUIRED"
    )

    def deny(*args, **kwargs):
        raise AssertionError("source read before grant validation")

    monkeypatch.setattr("readin.native_source_exports.read_private_source_bytes", deny)
    with pytest.raises(LocalSourceExportError, match="matching recorded connector grant"):
        _run(ledger, grant, tmp_path / "missing.zip", parser)
    assert ledger.path.read_bytes() == before


def test_inventory_cli_and_class_matching(tmp_path, capsys):
    ledger, grant, parser = _inventory_setup(tmp_path)
    path = _private(tmp_path / "selected.zip", _archive())
    args = [
        "import-native-source-export",
        "--ledger",
        str(ledger.path),
        "--asset",
        grant["asset"]["entity_id"],
        "--grant",
        grant["grant_id"],
        "--parser",
        parser,
        "--source",
        str(path),
        "--observed-at",
        "2026-09-04T13:00:00Z",
    ]
    assert main([*args, "--preview"]) == 0
    assert json.loads(capsys.readouterr().out)["file_entry_count"] == 2
    assert main([*args, "--attest"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "IMPORTED"
    assert main([*args, "--attest"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ALREADY_IMPORTED"
    with pytest.raises(NativeSourceExportError, match="class"):
        parse_native_source(_archive(), "LOCAL_FILE_COLLECTION_ZIP", BINDING)
    with pytest.raises(NativeSourceExportError, match="support"):
        prepare_native_source_grant(
            ledger.projection(), grant["asset"]["entity_id"], "LINKEDIN_PROFILE_ZIP"
        )


def test_multiple_snapshots_are_not_independent_file_assets(tmp_path):
    ledger, grant, parser = _inventory_setup(tmp_path)
    first = _run(ledger, grant, _private(tmp_path / "one.zip", _archive()), parser)
    second = _run(
        ledger,
        grant,
        _private(tmp_path / "two.zip", _archive([("Project/notes.txt", b"changed")])),
        parser,
    )
    assert first["source_sha256"] != second["source_sha256"]
    assert build_source_capabilities(ledger.projection())["local_imported_record_count"] == 2
    assert len(ledger.projection().assets) == 1


@pytest.mark.parametrize("prefix", [1, 2])
def test_inventory_complete_prefix_retry(tmp_path, monkeypatch, prefix):
    ledger, grant, parser = _inventory_setup(tmp_path)
    path = _private(tmp_path / "selected.zip", _archive())
    append = ledger.append_batch

    def interrupted(events):
        append(events[:prefix])
        raise OSError("complete prefix interrupted")

    monkeypatch.setattr(ledger, "append_batch", interrupted)
    with pytest.raises(OSError):
        _run(ledger, grant, path, parser)
    monkeypatch.setattr(ledger, "append_batch", append)
    assert _run(ledger, grant, path, parser)["events_appended"] == 3 - prefix


@pytest.mark.parametrize(
    "control", ["scope", "output", "private", "symlink", "attestation", "malformed"]
)
def test_inventory_failures_leave_ledger_unchanged(tmp_path, control):
    ledger, grant, parser = _inventory_setup(tmp_path, with_grant=False)
    if control == "scope":
        grant["scopes"][0]["data_category"] = "ACCOUNT_PROFILE_METADATA"
    if control == "output":
        grant["allowed_observation_types"][0]["observation_type"] = "social.profile_metadata"
    import_connector_grant_source(
        ledger, _write_private_manifest(tmp_path / "grant.json", grant), attested=True
    )
    path = _private(tmp_path / "source.zip", b"invalid" if control == "malformed" else _archive())
    if control == "private":
        path.chmod(0o644)
    if control == "symlink":
        link = tmp_path / "link.zip"
        link.symlink_to(path)
        path = link
    before = ledger.path.read_bytes()
    with pytest.raises(ConnectorGrantError):
        _run(ledger, grant, path, parser, attested=control != "attestation")
    assert ledger.path.read_bytes() == before


def _inventory_demo_fixture(tmp_path):
    ledger, grant, parser = _inventory_setup(tmp_path)
    raw = _archive(
        [
            ("Project/", b""),
            ("Project/notes.txt", b"Synthetic fixture only"),
            ("Project/budget.csv", b"category,amount\nexample,0\n"),
            ("Research/" + "long-document-name-" * 12 + ".md", b"Synthetic long-name fixture"),
            ("Literal <img src=x onerror=alert(1)>.txt", b"Synthetic escaping fixture"),
        ]
    )
    _run(ledger, grant, _private(tmp_path / "selected.zip", raw), parser)
    return ledger


def test_inventory_demo_fixture(tmp_path):
    ledger = _inventory_demo_fixture(tmp_path)
    snapshot = build_workbench_snapshot(ledger.projection())
    batches = snapshot["selected_asset"]["governance"]["source_exports"]
    assert batches[0]["file_entry_count"] == 4
    assert batches[0]["archive_entry_names_recorded"] is True
    assert snapshot["source_capabilities"]["local_imported_record_count"] == 1
