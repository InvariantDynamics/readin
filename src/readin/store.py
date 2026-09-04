"""Append-only local event ledger for the READIN reference runtime."""

from __future__ import annotations

import errno
import fcntl
import json
import os
import stat
from pathlib import Path
from typing import Any, TextIO

from readin.contracts import ContractViolation, validate_event
from readin.projection import ProjectionError, ReadinProjection


class LedgerError(RuntimeError):
    """Base error for local ledger operations."""


class LedgerExists(LedgerError):
    """Raised when initialization would overwrite an existing ledger."""


class LedgerMissing(LedgerError):
    """Raised when a ledger operation targets no file."""


class LedgerCorruption(LedgerError):
    """Raised when persisted ledger bytes cannot be replayed."""


class LedgerUnsafeTarget(LedgerError):
    """Raised when a ledger path could escape the expected regular-file boundary."""


class EventLedger:
    """A locked, flushed, append-only JSONL event ledger for local development."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self._ensure_private_parent_directories()
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | self._secure_open_flags()
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except FileExistsError as error:
            self._raise_existing_target(error)
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise LedgerUnsafeTarget(
                    f"ledger target must not be a symlink: {self.path}"
                ) from error
            raise

        try:
            target_stat = os.fstat(descriptor)
            if not stat.S_ISREG(target_stat.st_mode):
                raise LedgerUnsafeTarget(f"ledger target must be a regular file: {self.path}")
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                descriptor = -1
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def append(self, event: dict[str, Any]) -> None:
        validate_event(event)

        with self._open_existing(os.O_RDWR, "r+") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                events = self._read_stream(stream)
                projection = ReadinProjection.replay(events)
                projection.apply(event)
                stream.seek(0, os.SEEK_END)
                stream.write(
                    json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                )
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def read_events(self) -> list[dict[str, Any]]:
        with self._open_existing(os.O_RDONLY, "r") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
            try:
                return self._read_stream(stream)
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def projection(self) -> ReadinProjection:
        try:
            return ReadinProjection.replay(self.read_events())
        except ProjectionError as error:
            raise LedgerCorruption(f"ledger semantic replay failed: {error}") from error

    def _ensure_private_parent_directories(self) -> None:
        """Create only missing ledger ancestors and normalize those owned creations."""

        missing: list[Path] = []
        current = self.path.parent
        while True:
            try:
                current_stat = current.lstat()
            except FileNotFoundError as error:
                missing.append(current)
                parent = current.parent
                if parent == current:
                    raise LedgerUnsafeTarget(
                        f"ledger parent cannot be created safely: {self.path.parent}"
                    ) from error
                current = parent
                continue

            if stat.S_ISLNK(current_stat.st_mode):
                raise LedgerUnsafeTarget(f"ledger parent must not be a symlink: {current}")
            if not stat.S_ISDIR(current_stat.st_mode):
                raise LedgerUnsafeTarget(f"ledger parent must be a directory: {current}")
            break

        for directory in reversed(missing):
            try:
                directory.mkdir(mode=0o700)
            except FileExistsError:
                directory_stat = directory.lstat()
                if stat.S_ISLNK(directory_stat.st_mode) or not stat.S_ISDIR(directory_stat.st_mode):
                    raise LedgerUnsafeTarget(
                        f"ledger parent must be a real directory: {directory}"
                    ) from None
            else:
                os.chmod(directory, 0o700, follow_symlinks=False)

    def _open_existing(self, flags: int, mode: str) -> TextIO:
        before = self._require_regular_target()
        descriptor = -1
        try:
            descriptor = os.open(self.path, flags | self._secure_open_flags())
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                raise LedgerUnsafeTarget(f"ledger target must be a regular file: {self.path}")
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise LedgerUnsafeTarget(f"ledger target changed while opening: {self.path}")
            stream = os.fdopen(descriptor, mode, encoding="utf-8")
            descriptor = -1
            return stream
        except FileNotFoundError as error:
            raise LedgerMissing(f"ledger does not exist: {self.path}") from error
        except OSError as error:
            if error.errno == errno.ELOOP:
                raise LedgerUnsafeTarget(
                    f"ledger target must not be a symlink: {self.path}"
                ) from error
            raise
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def _require_regular_target(self) -> os.stat_result:
        try:
            target_stat = self.path.lstat()
        except FileNotFoundError as error:
            raise LedgerMissing(f"ledger does not exist: {self.path}") from error
        if stat.S_ISLNK(target_stat.st_mode):
            raise LedgerUnsafeTarget(f"ledger target must not be a symlink: {self.path}")
        if not stat.S_ISREG(target_stat.st_mode):
            raise LedgerUnsafeTarget(f"ledger target must be a regular file: {self.path}")
        return target_stat

    def _raise_existing_target(self, error: FileExistsError) -> None:
        try:
            target_stat = self.path.lstat()
        except FileNotFoundError:
            raise LedgerUnsafeTarget(
                f"ledger target changed during initialization: {self.path}"
            ) from error
        if stat.S_ISLNK(target_stat.st_mode):
            raise LedgerUnsafeTarget(f"ledger target must not be a symlink: {self.path}") from error
        if not stat.S_ISREG(target_stat.st_mode):
            raise LedgerUnsafeTarget(
                f"ledger target must be a regular file: {self.path}"
            ) from error
        raise LedgerExists(f"ledger already exists: {self.path}") from error

    @staticmethod
    def _secure_open_flags() -> int:
        return (
            getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )

    def _read_stream(self, stream: TextIO) -> list[dict[str, Any]]:
        stream.seek(0)
        events: list[dict[str, Any]] = []
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise LedgerCorruption(
                    f"ledger line {line_number} is not valid JSON: {error.msg}"
                ) from error
            if not isinstance(event, dict):
                raise LedgerCorruption(f"ledger line {line_number} is not a JSON object")
            try:
                validate_event(event)
            except ContractViolation as error:
                raise LedgerCorruption(
                    f"ledger line {line_number} violates the event contract: {error}"
                ) from error
            events.append(event)
        return events
