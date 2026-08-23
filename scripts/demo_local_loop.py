"""Run the closed synthetic Phase 4 multi-fitter loop in a temporary local ledger."""

from __future__ import annotations

import json
from tempfile import TemporaryDirectory

from readin.store import EventLedger
from readin.synthetic import phase4_events


def main() -> None:
    with TemporaryDirectory(prefix="readin-demo-") as directory:
        ledger = EventLedger(f"{directory}/events.jsonl")
        ledger.initialize()
        events = phase4_events()
        for event in events:
            ledger.append(event)
        print(
            json.dumps(
                ledger.projection().multi_fitter_run_view("65656565-6565-4656-8565-656565656565"),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
