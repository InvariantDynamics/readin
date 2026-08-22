"""Run the closed synthetic Phase 2 Array loop in a temporary local ledger."""

from __future__ import annotations

import json
from tempfile import TemporaryDirectory

from readin.store import EventLedger
from readin.synthetic import phase2_events


def main() -> None:
    with TemporaryDirectory(prefix="readin-demo-") as directory:
        ledger = EventLedger(f"{directory}/events.jsonl")
        ledger.initialize()
        events = phase2_events()
        for event in events:
            ledger.append(event)
        entity_id = events[0]["payload"]["entity"]["id"]
        print(
            json.dumps(
                ledger.projection().asset_view_at(
                    entity_id,
                    mode="AS_RECONSTRUCTED_NOW",
                    epistemic_cutoff="2026-08-21T12:00:18Z",
                ),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
