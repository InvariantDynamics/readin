"""Run the closed synthetic Phase 0 loop in a temporary local ledger."""

from __future__ import annotations

import json
from tempfile import TemporaryDirectory

from readin.store import EventLedger
from readin.synthetic import phase0_events


def main() -> None:
    with TemporaryDirectory(prefix="readin-demo-") as directory:
        ledger = EventLedger(f"{directory}/events.jsonl")
        ledger.initialize()
        for event in phase0_events():
            ledger.append(event)
        entity_id = phase0_events()[0]["payload"]["entity"]["id"]
        print(
            json.dumps(
                ledger.projection().asset_view(entity_id),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
