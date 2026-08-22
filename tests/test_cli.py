from __future__ import annotations

import json
from pathlib import Path

from readin.cli import main
from readin.store import EventLedger
from readin.synthetic import phase1_events, phase2_events


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


def test_cli_exposes_hindsight_labeled_timeline(tmp_path: Path, capsys: object) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    events = phase1_events()
    for event in events:
        ledger.append(event)
    entity_id = events[0]["payload"]["entity"]["id"]

    result = main(
        [
            "show-timeline",
            "--ledger",
            str(ledger.path),
            "--asset",
            entity_id,
            "--mode",
            "AS_RECONSTRUCTED_NOW",
            "--epistemic-cutoff",
            "2026-08-21T12:00:11Z",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert output["hindsight_included"] is True
    assert any(item["hindsight"] for item in output["entries"])
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_exposes_non_merging_resolution_candidate(tmp_path: Path, capsys: object) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    events = phase2_events()
    for event in events:
        ledger.append(event)

    result = main(
        [
            "show-resolution-candidate",
            "--ledger",
            str(ledger.path),
            "--candidate",
            "27272727-2727-4272-8272-272727272727",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert output["current_disposition"] == "POSSIBLE_MATCH"
    assert output["automatic_merge"] is False
    assert output["merge_state"] == "NOT_MERGED"
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_records_and_assesses_candidate_without_merge(tmp_path: Path, capsys: object) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    events = phase2_events()
    for event in events[:18]:
        ledger.append(event)

    signal = json.dumps(
        {
            "kind": "SHARED_ALIAS",
            "polarity": "SUPPORTS_CANDIDACY",
            "verification_status": "ASSERTED_NOT_VERIFIED",
            "statement": "Manual CLI signal",
            "observation_id": None,
        }
    )
    result = main(
        [
            "record-resolution-candidate",
            "--ledger",
            str(ledger.path),
            "--left",
            "11111111-1111-4111-8111-111111111111",
            "--right",
            "26262626-2626-4262-8262-262626262626",
            "--signal-json",
            signal,
            "--candidate-id",
            "43434343-4343-4434-8434-434343434343",
        ]
    )
    candidate_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert candidate_output["event_type"] == "entity.resolution_candidate_recorded"

    result = main(
        [
            "assess-resolution-candidate",
            "--ledger",
            str(ledger.path),
            "--candidate",
            "43434343-4343-4434-8434-434343434343",
            "--disposition",
            "CONFIRMED_MATCH_NOT_MERGED",
            "--rationale",
            "Manual identity assessment; merge remains outside this contract",
            "--assessment-id",
            "44444444-4444-4444-8444-444444444449",
        ]
    )
    assessment_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assessment = assessment_output["payload"]["resolution_assessment"]
    assert assessment["disposition"] == "CONFIRMED_MATCH_NOT_MERGED"
    assert assessment["automatic_merge"] is False
    assert assessment["merge_state"] == "NOT_MERGED"
