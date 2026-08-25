"""Serve the bounded workbench with a synthetic Phase 8D readback fixture."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from readin.store import EventLedger
from readin.synthetic import phase8d_events
from readin.workbench import serve_workbench


def main() -> None:
    with TemporaryDirectory(prefix="readin-workbench-") as directory:
        ledger = EventLedger(f"{directory}/events.jsonl")
        ledger.initialize()
        for event in phase8d_events():
            ledger.append(event)
        serve_workbench(ledger.path)


if __name__ == "__main__":
    main()
