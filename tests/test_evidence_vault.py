from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from readin.evidence_vault import EvidenceVault, StoredArtifact, VaultError


def test_initialize_creates_owner_only_directory_tree(tmp_path: Path) -> None:
    root = tmp_path / "case" / "vault"
    vault = EvidenceVault(root)

    vault.initialize()
    vault.initialize()

    for directory in (
        root,
        root / "evidence",
        root / "evidence" / "sha256",
        root / "receipts",
    ):
        assert directory.is_dir()
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_initialize_normalizes_existing_vault_directory_modes(tmp_path: Path) -> None:
    root = tmp_path / "vault"
    digest_directory = root / "evidence" / "sha256"
    digest_directory.mkdir(parents=True)
    receipts_directory = root / "receipts"
    receipts_directory.mkdir()
    for directory in (root, root / "evidence", digest_directory, receipts_directory):
        directory.chmod(0o755)

    EvidenceVault(root).initialize()

    for directory in (root, root / "evidence", digest_directory, receipts_directory):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700


def test_store_bytes_round_trips_with_content_address_and_owner_mode(tmp_path: Path) -> None:
    data = b'{"source":"public"}\n'
    expected_digest = hashlib.sha256(data).hexdigest()
    vault = EvidenceVault(tmp_path / "vault")

    stored = vault.store_bytes(data)

    assert stored == StoredArtifact(
        path=tmp_path / "vault" / "evidence" / "sha256" / expected_digest,
        sha256=expected_digest,
        size=len(data),
    )
    assert stored.path.read_bytes() == data
    assert stat.S_IMODE(stored.path.stat().st_mode) == 0o600
    assert vault.verify(expected_digest) == stored


def test_store_bytes_reuses_verified_artifact_without_replacing_it(tmp_path: Path) -> None:
    data = b"immutable evidence"
    vault = EvidenceVault(tmp_path / "vault")
    first = vault.store_bytes(data)
    original_inode = first.path.stat().st_ino

    second = vault.store_bytes(data)

    assert second == first
    assert second.path.stat().st_ino == original_inode
    assert list(vault.sha256_directory.iterdir()) == [first.path]


def test_store_bytes_rejects_oversize_and_non_bytes_input(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault", max_artifact_bytes=4)

    with pytest.raises(VaultError, match="exceeds maximum size"):
        vault.store_bytes(b"12345")
    with pytest.raises(VaultError, match="must be bytes"):
        vault.store_bytes(bytearray(b"1234"))  # type: ignore[arg-type]


@pytest.mark.parametrize("limit", [0, -1, 1.5, True, "1024", None])
def test_vault_rejects_invalid_size_limit(tmp_path: Path, limit: object) -> None:
    with pytest.raises(VaultError, match="positive integer"):
        EvidenceVault(tmp_path / "vault", max_artifact_bytes=limit)  # type: ignore[arg-type]


def test_verify_rejects_missing_invalid_and_corrupt_artifacts(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault")
    vault.initialize()
    expected = hashlib.sha256(b"expected").hexdigest()
    (vault.sha256_directory / expected).write_bytes(b"tampered")

    with pytest.raises(VaultError, match="digest mismatch"):
        vault.verify(expected)
    with pytest.raises(VaultError, match="does not exist"):
        vault.verify("0" * 64)
    with pytest.raises(VaultError, match="64 lowercase"):
        vault.verify("../escape")
    with pytest.raises(VaultError, match="64 lowercase"):
        vault.verify("A" * 64)


def test_verify_rejects_artifact_over_configured_cap(tmp_path: Path) -> None:
    data = b"five!"
    digest = hashlib.sha256(data).hexdigest()
    vault = EvidenceVault(tmp_path / "vault", max_artifact_bytes=4)
    vault.initialize()
    (vault.sha256_directory / digest).write_bytes(data)

    with pytest.raises(VaultError, match="stored artifact exceeds maximum size"):
        vault.verify(digest)


def test_store_rejects_corruption_at_existing_digest_path(tmp_path: Path) -> None:
    data = b"original content"
    digest = hashlib.sha256(data).hexdigest()
    vault = EvidenceVault(tmp_path / "vault")
    vault.initialize()
    target = vault.sha256_directory / digest
    target.write_bytes(b"different content")
    original_inode = target.stat().st_ino

    with pytest.raises(VaultError, match="digest mismatch"):
        vault.store_bytes(data)

    assert target.read_bytes() == b"different content"
    assert target.stat().st_ino == original_inode


@pytest.mark.parametrize("component", ["root", "evidence", "sha256", "receipts"])
def test_initialize_rejects_symlink_directory_components(
    tmp_path: Path,
    component: str,
) -> None:
    real_directory = tmp_path / "real"
    real_directory.mkdir()
    root = tmp_path / "vault"
    if component == "root":
        root.symlink_to(real_directory, target_is_directory=True)
    else:
        root.mkdir()
        if component == "evidence":
            (root / "evidence").symlink_to(real_directory, target_is_directory=True)
        elif component == "sha256":
            (root / "evidence").mkdir()
            (root / "evidence" / "sha256").symlink_to(
                real_directory,
                target_is_directory=True,
            )
        else:
            (root / "receipts").symlink_to(real_directory, target_is_directory=True)

    with pytest.raises(VaultError, match="must not be a symlink"):
        EvidenceVault(root).initialize()


@pytest.mark.parametrize("component", ["root", "evidence", "sha256", "receipts"])
def test_initialize_rejects_non_directory_components(tmp_path: Path, component: str) -> None:
    root = tmp_path / "vault"
    if component == "root":
        root.write_text("not a directory", encoding="utf-8")
    else:
        root.mkdir()
        if component == "evidence":
            (root / "evidence").write_text("not a directory", encoding="utf-8")
        elif component == "sha256":
            (root / "evidence").mkdir()
            (root / "evidence" / "sha256").write_text(
                "not a directory",
                encoding="utf-8",
            )
        else:
            (root / "receipts").write_text("not a directory", encoding="utf-8")

    with pytest.raises(VaultError, match="must be a directory"):
        EvidenceVault(root).initialize()


@pytest.mark.parametrize("target_kind", ["symlink", "directory"])
def test_verify_rejects_nonregular_artifact_target(
    tmp_path: Path,
    target_kind: str,
) -> None:
    vault = EvidenceVault(tmp_path / "vault")
    vault.initialize()
    digest = "0" * 64
    target = vault.sha256_directory / digest
    if target_kind == "symlink":
        victim = tmp_path / "victim"
        victim.write_bytes(b"untouched")
        target.symlink_to(victim)
    else:
        target.mkdir()

    with pytest.raises(VaultError, match="regular file|symlink"):
        vault.verify(digest)


def test_write_receipt_is_canonical_exclusive_and_owner_only(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault")
    receipt = {"z": 1, "nested": {"beta": False, "alpha": "value"}, "a": 2}

    path = vault.write_receipt("fetch_123-abc", receipt)

    assert path.read_bytes() == (b'{"a":2,"nested":{"alpha":"value","beta":false},"z":1}\n')
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    with pytest.raises(VaultError, match="already exists"):
        vault.write_receipt("fetch_123-abc", {"replacement": True})
    assert json.loads(path.read_text(encoding="utf-8")) == receipt


@pytest.mark.parametrize(
    "receipt_id",
    ["", ".", "..", "../escape", "nested/name", " leading", "x" * 129],
)
def test_write_receipt_rejects_unsafe_identifier(
    tmp_path: Path,
    receipt_id: str,
) -> None:
    vault = EvidenceVault(tmp_path / "vault")

    with pytest.raises(VaultError, match="receipt_id"):
        vault.write_receipt(receipt_id, {})


def test_write_receipt_rejects_symlink_without_touching_victim(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault")
    vault.initialize()
    victim = tmp_path / "victim.json"
    victim.write_text("unchanged", encoding="utf-8")
    (vault.receipts_directory / "receipt.json").symlink_to(victim)

    with pytest.raises(VaultError, match="must not be a symlink"):
        vault.write_receipt("receipt", {"new": "content"})

    assert victim.read_text(encoding="utf-8") == "unchanged"


def test_write_receipt_rejects_nonregular_and_unserializable_values(tmp_path: Path) -> None:
    vault = EvidenceVault(tmp_path / "vault")
    vault.initialize()
    (vault.receipts_directory / "directory.json").mkdir()

    with pytest.raises(VaultError, match="regular file"):
        vault.write_receipt("directory", {})
    with pytest.raises(VaultError, match="serializable"):
        vault.write_receipt("invalid", {"value": object()})

    assert not (vault.receipts_directory / "invalid.json").exists()


def test_verify_normalizes_existing_artifact_mode(tmp_path: Path) -> None:
    data = b"public artifact"
    digest = hashlib.sha256(data).hexdigest()
    vault = EvidenceVault(tmp_path / "vault")
    vault.initialize()
    target = vault.sha256_directory / digest
    target.write_bytes(data)
    target.chmod(0o644)

    stored = vault.verify(digest)

    assert stored.size == len(data)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_rejects_filesystem_root_as_vault_root() -> None:
    with pytest.raises(VaultError, match="filesystem root"):
        EvidenceVault(Path(os.sep))
