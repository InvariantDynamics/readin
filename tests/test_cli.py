from __future__ import annotations

import json
from pathlib import Path

from readin.cli import main
from readin.store import EventLedger
from readin.synthetic import phase1_events, phase2_events, phase3_events


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


def test_cli_executes_persisted_cartographic_query_locally(tmp_path: Path, capsys: object) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase3_events():
        ledger.append(event)

    result = main(
        [
            "run-cartographic-query",
            "--ledger",
            str(ledger.path),
            "--query",
            "39393939-3939-4393-8393-393939393939",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert output["execution"]["state"] == "LOCAL_LEDGER_REPLAY"
    assert output["execution"]["network_access"] is False
    assert output["aperture"]["excluded_asset_observation_count"] == 1
    assert output["query_lens"]["hindsight_in_query_lens"] is True
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_registers_surface_and_persists_backward_plan(tmp_path: Path, capsys: object) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase2_events():
        ledger.append(event)

    result = main(
        [
            "register-cartographic-surface",
            "--ledger",
            str(ledger.path),
            "--name",
            "CLI public-record surface",
            "--description",
            "One fixture observer frame",
            "--frame",
            "22222222-2222-4222-8222-222222222222",
            "--blind-region-state",
            "DECLARED",
            "--blind-region",
            "No independent operational verification",
            "--surface-id",
            "51515151-5151-4515-8515-515151515151",
        ]
    )
    surface_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert surface_output["event_type"] == "cartography.surface_registered"

    result = main(
        [
            "plan-cartographic-query",
            "--ledger",
            str(ledger.path),
            "--asset",
            "11111111-1111-4111-8111-111111111111",
            "--surface",
            "51515151-5151-4515-8515-515151515151",
            "--mode",
            "AS_KNOWN_THEN",
            "--epistemic-cutoff",
            "2026-08-21T12:00:16Z",
            "--query-id",
            "52525252-5252-4525-8525-525252525252",
        ]
    )
    query_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    plan = query_output["payload"]["cartographic_query_plan"]
    assert plan["direction"] == "BACKWARD"
    assert plan["traversal"]["max_relation_hops"] == 1
    assert plan["execution_state"] == "PLANNED_READ_ONLY"


def test_cli_registers_and_runs_reference_fitters_without_consensus(
    tmp_path: Path, capsys: object
) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase3_events():
        ledger.append(event)

    registrations = (
        ("BAYESIAN", "74747474-7474-4747-8474-747474747474"),
        ("GRAPH", "75757575-7575-4757-8575-757575757575"),
        ("TEMPORAL", "76767676-7676-4767-8676-767676767676"),
    )
    for fitter_class, fitter_id in registrations:
        result = main(
            [
                "register-reference-fitter",
                "--ledger",
                str(ledger.path),
                "--class",
                fitter_class,
                "--fitter-id",
                fitter_id,
            ]
        )
        output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
        assert result == 0
        assert output["event_type"] == "fitter.registered"

    result = main(
        [
            "run-fitters",
            "--ledger",
            str(ledger.path),
            "--query",
            "39393939-3939-4393-8393-393939393939",
            "--fitter",
            registrations[0][1],
            "--fitter",
            registrations[1][1],
            "--fitter",
            registrations[2][1],
            "--run-group-id",
            "77777777-7777-4777-8777-777777777771",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert output["outcome_counts"] == {"ABSTAINED": 0, "FIT": 2, "INVALID": 1}
    assert output["disagreement"]["signals"] == [
        "MODEL_INVALIDITY_PRESENT",
        "OUTPUTS_INCOMMENSURATE",
    ]
    assert output["consensus"]["state"] == "NOT_COMPUTED"
    assert output["authority_state"] == "NO_AUTHORITY"
