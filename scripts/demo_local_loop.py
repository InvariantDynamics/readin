"""Run the closed synthetic Phase 3 cartographic loop in a temporary local ledger."""

from __future__ import annotations

import json
from tempfile import TemporaryDirectory

from readin.store import EventLedger
from readin.synthetic import phase3_events


def main() -> None:
    with TemporaryDirectory(prefix="readin-demo-") as directory:
        ledger = EventLedger(f"{directory}/events.jsonl")
        ledger.initialize()
        events = phase3_events()
        for event in events:
            ledger.append(event)
        print(
            json.dumps(
                ledger.projection().execute_cartographic_query(
                    "39393939-3939-4393-8393-393939393939"
                ),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
