"""Run the closed synthetic Phase 8D readback-selection prerequisite loop."""

from __future__ import annotations

import json
from tempfile import TemporaryDirectory

from readin.store import EventLedger
from readin.synthetic import phase8d_events


def main() -> None:
    with TemporaryDirectory(prefix="readin-demo-") as directory:
        ledger = EventLedger(f"{directory}/events.jsonl")
        ledger.initialize()
        events = phase8d_events()
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
                    "discrimination_run": ledger.projection().discrimination_run_view(
                        "94949494-9494-4494-8494-949494949491"
                    ),
                    "forecast_evaluation_design": (
                        ledger.projection().forecast_evaluation_design_view(
                            "a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0"
                        )
                    ),
                    "forecast_baseline": ledger.projection().forecast_baseline_view(
                        "c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0"
                    ),
                    "readback_selection": ledger.projection().readback_selection_plan_view(
                        "d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0"
                    ),
                },
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
