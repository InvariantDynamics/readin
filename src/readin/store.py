"""Append-only local event ledger for the READIN reference runtime."""

from __future__ import annotations

import fcntl
import json
import os
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


class EventLedger:
    """A locked, flushed, append-only JSONL event ledger for local development."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("x", encoding="utf-8") as stream:
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise LedgerExists(f"ledger already exists: {self.path}") from error

    def append(self, event: dict[str, Any]) -> None:
        validate_event(event)
        if not self.path.is_file():
            raise LedgerMissing(f"ledger does not exist: {self.path}")

        with self.path.open("r+", encoding="utf-8") as stream:
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
        if not self.path.is_file():
            raise LedgerMissing(f"ledger does not exist: {self.path}")
        with self.path.open(encoding="utf-8") as stream:
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
