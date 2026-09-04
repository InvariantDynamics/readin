"""Owner-only, content-addressed storage for acquired evidence artifacts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_RECEIPT_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")
_COPY_CHUNK_BYTES = 64 * 1024


class VaultError(RuntimeError):
    """Raised when a vault operation cannot preserve its safety invariants."""


@dataclass(frozen=True)
class StoredArtifact:
    """An immutable reference to one verified content-addressed artifact."""

    path: Path
    sha256: str
    size: int


class EvidenceVault:
    """Store immutable evidence bytes and acquisition receipts in a private vault."""

    def __init__(
        self,
        root: str | Path,
        max_artifact_bytes: int = 1_048_576,
    ) -> None:
        if (
            isinstance(max_artifact_bytes, bool)
            or not isinstance(max_artifact_bytes, int)
            or max_artifact_bytes <= 0
        ):
            raise VaultError("max_artifact_bytes must be a positive integer")

        self.root = Path(os.path.abspath(os.fspath(root)))
        if self.root == Path(self.root.anchor):
            raise VaultError("vault root must not be a filesystem root")
        self.max_artifact_bytes = max_artifact_bytes
        self.evidence_directory = self.root / "evidence"
        self.sha256_directory = self.evidence_directory / "sha256"
        self.receipts_directory = self.root / "receipts"

    def initialize(self) -> None:
        """Create and normalize the private vault directory structure."""

        for directory in (
            self.root,
            self.evidence_directory,
            self.sha256_directory,
            self.receipts_directory,
        ):
            self._ensure_private_directory(directory)

    def store_bytes(self, data: bytes) -> StoredArtifact:
        """Persist bytes at their SHA-256 path without replacing an existing artifact."""

        if not isinstance(data, bytes):
            raise VaultError("artifact data must be bytes")
        if len(data) > self.max_artifact_bytes:
            raise VaultError(f"artifact exceeds maximum size of {self.max_artifact_bytes} bytes")

        digest = hashlib.sha256(data).hexdigest()
        self.initialize()
        directory_descriptor = self._open_directory(self.sha256_directory)
        try:
            existing = self._existing_target_stat(directory_descriptor, digest)
            if existing is not None:
                return self._verify_in_directory(directory_descriptor, digest, digest)

            temporary_name = f".artifact-{secrets.token_hex(16)}.tmp"
            temporary_created = False
            descriptor = -1
            try:
                flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | self._secure_open_flags()
                descriptor = os.open(
                    temporary_name,
                    flags,
                    0o600,
                    dir_fd=directory_descriptor,
                )
                temporary_created = True
                opened = os.fstat(descriptor)
                if not stat.S_ISREG(opened.st_mode):
                    raise VaultError("temporary artifact target must be a regular file")
                os.fchmod(descriptor, 0o600)
                self._write_all(descriptor, data)
                os.fsync(descriptor)
                os.close(descriptor)
                descriptor = -1

                try:
                    os.link(
                        temporary_name,
                        digest,
                        src_dir_fd=directory_descriptor,
                        dst_dir_fd=directory_descriptor,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    artifact = self._verify_in_directory(
                        directory_descriptor,
                        digest,
                        digest,
                    )
                else:
                    os.fsync(directory_descriptor)
                    artifact = self._verify_in_directory(
                        directory_descriptor,
                        digest,
                        digest,
                    )
                return artifact
            except VaultError:
                raise
            except OSError as error:
                raise VaultError(f"could not store artifact: {error}") from error
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
                if temporary_created:
                    try:
                        os.unlink(temporary_name, dir_fd=directory_descriptor)
                    except FileNotFoundError:
                        pass
                    else:
                        os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)

    def verify(self, sha256: str) -> StoredArtifact:
        """Re-hash one stored artifact and return it only when it matches its path."""

        if not isinstance(sha256, str) or _SHA256_PATTERN.fullmatch(sha256) is None:
            raise VaultError("sha256 must be exactly 64 lowercase hexadecimal characters")

        self.initialize()
        directory_descriptor = self._open_directory(self.sha256_directory)
        try:
            return self._verify_in_directory(directory_descriptor, sha256, sha256)
        finally:
            os.close(directory_descriptor)

    def write_receipt(self, receipt_id: str, receipt: Mapping[str, Any]) -> Path:
        """Write one canonical JSON receipt without replacing an existing receipt.

        Receipt values are persisted as supplied. Callers must exclude credentials and other
        secrets before invoking this method.
        """

        if not isinstance(receipt_id, str) or _RECEIPT_ID_PATTERN.fullmatch(receipt_id) is None:
            raise VaultError(
                "receipt_id must be 1-128 ASCII letters, digits, underscores, or hyphens "
                "and must start with a letter or digit"
            )
        if not isinstance(receipt, Mapping):
            raise VaultError("receipt must be a mapping")

        try:
            serialized = (
                json.dumps(
                    dict(receipt),
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                + b"\n"
            )
        except (TypeError, ValueError) as error:
            raise VaultError(f"receipt is not canonical-JSON serializable: {error}") from error

        self.initialize()
        filename = f"{receipt_id}.json"
        directory_descriptor = self._open_directory(self.receipts_directory)
        descriptor = -1
        created = False
        try:
            existing = self._existing_target_stat(directory_descriptor, filename)
            if existing is not None:
                self._raise_existing_receipt(filename, existing)

            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | self._secure_open_flags()
            try:
                descriptor = os.open(
                    filename,
                    flags,
                    0o600,
                    dir_fd=directory_descriptor,
                )
            except FileExistsError as error:
                existing = self._existing_target_stat(directory_descriptor, filename)
                if existing is None:
                    raise VaultError(
                        f"receipt target changed while creating: {filename}"
                    ) from error
                self._raise_existing_receipt(filename, existing, error)
            created = True

            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise VaultError(f"receipt target must be a regular file: {filename}")
            os.fchmod(descriptor, 0o600)
            self._write_all(descriptor, serialized)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = -1
            os.fsync(directory_descriptor)
            return self.receipts_directory / filename
        except VaultError:
            if created:
                self._remove_failed_receipt(directory_descriptor, filename)
            raise
        except OSError as error:
            if created:
                self._remove_failed_receipt(directory_descriptor, filename)
            raise VaultError(f"could not write receipt: {error}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(directory_descriptor)

    def _ensure_private_directory(self, directory: Path) -> None:
        missing: list[Path] = []
        current = directory
        while True:
            try:
                current_stat = current.lstat()
            except FileNotFoundError as error:
                missing.append(current)
                parent = current.parent
                if parent == current:
                    raise VaultError(
                        f"vault directory cannot be created safely: {directory}"
                    ) from error
                current = parent
                continue

            if stat.S_ISLNK(current_stat.st_mode):
                raise VaultError(f"vault directory component must not be a symlink: {current}")
            if not stat.S_ISDIR(current_stat.st_mode):
                raise VaultError(f"vault directory component must be a directory: {current}")
            break

        for missing_directory in reversed(missing):
            try:
                missing_directory.mkdir(mode=0o700)
            except FileExistsError:
                created_stat = missing_directory.lstat()
                if stat.S_ISLNK(created_stat.st_mode):
                    raise VaultError(
                        f"vault directory component must not be a symlink: {missing_directory}"
                    ) from None
                if not stat.S_ISDIR(created_stat.st_mode):
                    raise VaultError(
                        f"vault directory component must be a directory: {missing_directory}"
                    ) from None
            except OSError as error:
                raise VaultError(
                    f"could not create vault directory {missing_directory}: {error}"
                ) from error

        try:
            directory_stat = directory.lstat()
            if stat.S_ISLNK(directory_stat.st_mode):
                raise VaultError(f"vault directory must not be a symlink: {directory}")
            if not stat.S_ISDIR(directory_stat.st_mode):
                raise VaultError(f"vault directory must be a directory: {directory}")
            os.chmod(directory, 0o700, follow_symlinks=False)
        except VaultError:
            raise
        except OSError as error:
            raise VaultError(f"could not secure vault directory {directory}: {error}") from error

    def _open_directory(self, directory: Path) -> int:
        try:
            before = directory.lstat()
        except FileNotFoundError as error:
            raise VaultError(f"vault directory does not exist: {directory}") from error
        if stat.S_ISLNK(before.st_mode):
            raise VaultError(f"vault directory must not be a symlink: {directory}")
        if not stat.S_ISDIR(before.st_mode):
            raise VaultError(f"vault directory must be a directory: {directory}")

        descriptor = -1
        try:
            descriptor = os.open(
                directory,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            opened = os.fstat(descriptor)
            if not stat.S_ISDIR(opened.st_mode):
                raise VaultError(f"vault directory must be a directory: {directory}")
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise VaultError(f"vault directory changed while opening: {directory}")
            opened_descriptor = descriptor
            descriptor = -1
            return opened_descriptor
        except VaultError:
            raise
        except OSError as error:
            if error.errno == getattr(os, "ELOOP", None):
                raise VaultError(f"vault directory must not be a symlink: {directory}") from error
            raise VaultError(f"could not open vault directory {directory}: {error}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _existing_target_stat(
        self,
        directory_descriptor: int,
        filename: str,
    ) -> os.stat_result | None:
        try:
            target_stat = os.stat(
                filename,
                dir_fd=directory_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(target_stat.st_mode):
            raise VaultError(f"vault target must not be a symlink: {filename}")
        if not stat.S_ISREG(target_stat.st_mode):
            raise VaultError(f"vault target must be a regular file: {filename}")
        return target_stat

    def _verify_in_directory(
        self,
        directory_descriptor: int,
        filename: str,
        expected_sha256: str,
    ) -> StoredArtifact:
        before = self._existing_target_stat(directory_descriptor, filename)
        if before is None:
            raise VaultError(f"stored artifact does not exist: {expected_sha256}")

        descriptor = -1
        try:
            descriptor = os.open(
                filename,
                os.O_RDONLY | self._secure_open_flags(),
                dir_fd=directory_descriptor,
            )
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise VaultError(f"vault target must be a regular file: {filename}")
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise VaultError(f"vault target changed while opening: {filename}")
            os.fchmod(descriptor, 0o600)

            digest = hashlib.sha256()
            total_size = 0
            while True:
                chunk = os.read(descriptor, _COPY_CHUNK_BYTES)
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > self.max_artifact_bytes:
                    raise VaultError(
                        f"stored artifact exceeds maximum size of "
                        f"{self.max_artifact_bytes} bytes: {filename}"
                    )
                digest.update(chunk)

            actual_sha256 = digest.hexdigest()
            if actual_sha256 != expected_sha256:
                raise VaultError(
                    "stored artifact digest mismatch: "
                    f"expected {expected_sha256}, got {actual_sha256}"
                )
            return StoredArtifact(
                path=self.sha256_directory / filename,
                sha256=actual_sha256,
                size=total_size,
            )
        except VaultError:
            raise
        except OSError as error:
            if error.errno == getattr(os, "ELOOP", None):
                raise VaultError(f"vault target must not be a symlink: {filename}") from error
            raise VaultError(f"could not verify stored artifact {filename}: {error}") from error
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    @staticmethod
    def _write_all(descriptor: int, data: bytes) -> None:
        remaining = memoryview(data)
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise VaultError("filesystem write made no progress")
            remaining = remaining[written:]

    @staticmethod
    def _secure_open_flags() -> int:
        return (
            getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )

    @staticmethod
    def _raise_existing_receipt(
        filename: str,
        target_stat: os.stat_result,
        error: Exception | None = None,
    ) -> None:
        if stat.S_ISLNK(target_stat.st_mode):
            raise VaultError(f"receipt target must not be a symlink: {filename}") from error
        if not stat.S_ISREG(target_stat.st_mode):
            raise VaultError(f"receipt target must be a regular file: {filename}") from error
        raise VaultError(f"receipt already exists: {filename}") from error

    @staticmethod
    def _remove_failed_receipt(directory_descriptor: int, filename: str) -> None:
        try:
            os.unlink(filename, dir_fd=directory_descriptor)
        except OSError:
            return
        try:
            os.fsync(directory_descriptor)
        except OSError:
            return
