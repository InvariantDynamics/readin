from __future__ import annotations

import json
from pathlib import Path

from readin.cli import main


def test_cli_initializes_and_tracks_entity(tmp_path: Path, capsys: object) -> None:
    ledger = tmp_path / "events.jsonl"
    assert main(["init", "--ledger", str(ledger)]) == 0
    capsys.readouterr()  # type: ignore[attr-defined]

    result = main(
        [
            "create-entity",
            "--ledger",
            str(ledger),
            "--name",
            "CLI Example",
            "--type",
            "Organization",
            "--entity-id",
            "55555555-5555-4555-8555-555555555555",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert output["entity_id"] == "55555555-5555-4555-8555-555555555555"
    assert len(output["events"]) == 2
    assert output["authority_state"] == "NO_AUTHORITY"
