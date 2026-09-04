from __future__ import annotations

import stat
from pathlib import Path

import pytest

from readin.projection import ProjectionError
from readin.store import (
    EventLedger,
    LedgerCorruption,
    LedgerExists,
    LedgerMissing,
    LedgerUnsafeTarget,
)
from readin.synthetic import phase0_events, phase1_events


def test_ledger_round_trip(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase0_events():
        ledger.append(event)

    events = ledger.read_events()
    entity_id = events[0]["payload"]["entity"]["id"]
    view = ledger.projection().asset_view(entity_id)

    assert len(events) == 5
    assert len(view["observations"]) == 1


def test_ledger_initialization_never_overwrites(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    with pytest.raises(LedgerExists):
        ledger.initialize()


def test_ledger_initialization_uses_owner_only_permissions(tmp_path: Path) -> None:
    ledger_path = tmp_path / "case" / "ledger" / "events.jsonl"
    ledger = EventLedger(ledger_path)

    ledger.initialize()

    assert stat.S_IMODE(ledger_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(ledger_path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(ledger_path.parent.parent.stat().st_mode) == 0o700


@pytest.mark.parametrize("operation", ["initialize", "append", "read"])
def test_ledger_rejects_symlink_target(tmp_path: Path, operation: str) -> None:
    victim = tmp_path / "victim.jsonl"
    victim.write_text("", encoding="utf-8")
    ledger_path = tmp_path / "events.jsonl"
    ledger_path.symlink_to(victim)
    ledger = EventLedger(ledger_path)

    with pytest.raises(LedgerUnsafeTarget, match="must not be a symlink"):
        if operation == "initialize":
            ledger.initialize()
        elif operation == "append":
            ledger.append(phase0_events()[0])
        else:
            ledger.read_events()

    assert victim.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("operation", ["initialize", "append", "read"])
def test_ledger_rejects_non_regular_target(tmp_path: Path, operation: str) -> None:
    ledger_path = tmp_path / "events.jsonl"
    ledger_path.mkdir()
    ledger = EventLedger(ledger_path)

    with pytest.raises(LedgerUnsafeTarget, match="must be a regular file"):
        if operation == "initialize":
            ledger.initialize()
        elif operation == "append":
            ledger.append(phase0_events()[0])
        else:
            ledger.read_events()


def test_rejected_backdated_append_does_not_mutate_ledger(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    events = phase1_events()
    for event in events[:5]:
        ledger.append(event)
    changed = events[5]
    changed["occurred_at"] = "2026-08-21T12:00:03Z"

    with pytest.raises(ProjectionError, match="precedes the prior ledger event"):
        ledger.append(changed)

    assert ledger.read_events() == events[:5]


def test_missing_ledger_fails_closed(tmp_path: Path) -> None:
    ledger = EventLedger(tmp_path / "missing.jsonl")
    with pytest.raises(LedgerMissing):
        ledger.read_events()


def test_corrupt_ledger_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    ledger = EventLedger(path)
    with pytest.raises(LedgerCorruption, match="not valid JSON"):
        ledger.read_events()
