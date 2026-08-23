"""Run the closed synthetic Phase 5 belief and scenario loop in a temporary ledger."""

from __future__ import annotations

import json
from tempfile import TemporaryDirectory

from readin.store import EventLedger
from readin.synthetic import phase5_events


def main() -> None:
    with TemporaryDirectory(prefix="readin-demo-") as directory:
        ledger = EventLedger(f"{directory}/events.jsonl")
        ledger.initialize()
        events = phase5_events()
        for event in events:
            ledger.append(event)
        print(
            json.dumps(
                {
                    "belief_revision": ledger.projection().belief_revision_view(
                        "84848484-8484-4484-8484-848484848481"
                    ),
                    "scenario_run": ledger.projection().scenario_run_view(
                        "89898989-8989-4989-8989-898989898981"
                    ),
                },
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
