from __future__ import annotations

import json
from pathlib import Path

from readin.cli import main
from readin.store import EventLedger
from readin.synthetic import (
    phase1_events,
    phase2_events,
    phase3_events,
    phase5_events,
    phase7_events,
    phase8_events,
    phase8d_events,
    phase8e_events,
)


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


def test_cli_exposes_belief_revision_and_non_predictive_scenario(
    tmp_path: Path, capsys: object
) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase5_events():
        ledger.append(event)

    result = main(
        [
            "show-belief-revision",
            "--ledger",
            str(ledger.path),
            "--revision",
            "84848484-8484-4484-8484-848484848481",
        ]
    )
    revision = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert revision["probability_state"] == "NOT_COMPUTED"
    assert revision["dependency_policy"] == "GROUP_BY_DECLARED_ANCESTRY"
    assert revision["authority_state"] == "NO_AUTHORITY"

    result = main(
        [
            "show-scenario-run",
            "--ledger",
            str(ledger.path),
            "--run",
            "89898989-8989-4989-8989-898989898981",
        ]
    )
    scenario = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert scenario["run"]["summary"]["unknown_branch_visible"] is True
    assert scenario["trajectory_state"] == "NOT_SIMULATED"
    assert scenario["prediction_state"] == "NOT_REQUESTED"
    assert scenario["authority_state"] == "NO_AUTHORITY"


def test_cli_exposes_discrimination_run_without_acquisition(tmp_path: Path, capsys: object) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase7_events():
        ledger.append(event)

    result = main(
        [
            "show-discrimination-run",
            "--ledger",
            str(ledger.path),
            "--run",
            "94949494-9494-4494-8494-949494949491",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert output["run"]["recommendation_state"] == "RANKED_STRUCTURAL_CANDIDATES"
    assert output["run"]["acquisition_state"] == "NOT_ATTEMPTED"
    assert output["run"]["execution_receipt"]["network_access"] is False
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_creates_and_exposes_forecast_evaluation_design_without_prediction(
    tmp_path: Path, capsys: object
) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase7_events():
        ledger.append(event)

    result = main(
        [
            "create-forecast-evaluation-design",
            "--ledger",
            str(ledger.path),
            "--scenario",
            "85858585-8585-4585-8585-858585858585",
            "--name",
            "CLI forecast evaluation design",
            "--observation-type",
            "synthetic.cli_outcome",
            "--field",
            "outcome",
            "--unit",
            "synthetic_unit",
            "--training-cutoff",
            "2026-08-21T12:00:37Z",
            "--design-id",
            "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d1",
            "--occurred-at",
            "2026-08-21T12:00:38Z",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["design"]["preregistration_state"] == ("RECORDED_BEFORE_FORECAST_ORIGIN")
    assert output["forecast_capable_fitter_state"] == "NO_ELIGIBLE_FITTER_REGISTERED"
    assert output["prediction_state"] == "NOT_PRODUCED"

    result = main(
        [
            "show-forecast-evaluation-design",
            "--ledger",
            str(ledger.path),
            "--design",
            "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d1",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["design"]["target"]["structured_field_path"] == ["outcome"]
    assert output["forecast_execution_state"] == "NOT_STARTED"
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_freezes_and_exposes_uncalibrated_forecast_baseline(
    tmp_path: Path, capsys: object
) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase8_events()[:41]:
        ledger.append(event)

    result = main(
        [
            "run-forecast-baseline",
            "--ledger",
            str(ledger.path),
            "--design",
            "a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0",
            "--value",
            "0.6",
            "--baseline-id",
            "d2d2d2d2-d2d2-42d2-82d2-d2d2d2d2d2d2",
            "--occurred-at",
            "2026-08-21T12:00:39Z",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["baseline"]["prediction"]["value"] == 0.6
    assert output["baseline"]["prediction"]["prediction_state"] == (
        "PRODUCED_UNCALIBRATED_BASELINE"
    )
    assert output["baseline"]["input_boundary"]["selected_input_observation_ids"] == []
    assert output["baseline"]["residual_scoring_state"] == "NOT_ENABLED"
    assert output["baseline"]["execution_receipt"]["network_access"] is False
    assert output["authority_state"] == "NO_AUTHORITY"

    result = main(
        [
            "show-forecast-baseline",
            "--ledger",
            str(ledger.path),
            "--baseline",
            "d2d2d2d2-d2d2-42d2-82d2-d2d2d2d2d2d2",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["baseline"]["method"]["name"] == "USER_DECLARED_CONSTANT"
    assert output["calibration_state"] == "NOT_ESTABLISHED"
    assert output["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_creates_runs_and_exposes_readback_selection(tmp_path: Path, capsys: object) -> None:
    fixture = phase8d_events()
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in fixture[:42]:
        ledger.append(event)

    result = main(
        [
            "create-readback-selection-plan",
            "--ledger",
            str(ledger.path),
            "--baseline",
            "c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0",
            "--name",
            "CLI readback aperture",
            "--frame",
            "91919191-9191-4191-8191-919191919191",
            "--observed-window-end",
            "2026-09-23T00:00:00Z",
            "--ledger-admission-cutoff",
            "2026-09-23T12:00:00Z",
            "--plan-id",
            "d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0",
            "--occurred-at",
            "2026-08-21T12:00:40Z",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["plan"]["selection_policy"]["cardinality"] == "EXACTLY_ONE"
    assert output["run"] is None

    for event in fixture[43:45]:
        ledger.append(event)
    result = main(
        [
            "run-readback-selection",
            "--ledger",
            str(ledger.path),
            "--plan",
            "d0d0d0d0-d0d0-40d0-80d0-d0d0d0d0d0d0",
            "--run-id",
            "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d0",
            "--occurred-at",
            "2026-09-23T12:00:01Z",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["run"]["selection_state"] == "UNIQUE_MATCH_SELECTED"
    assert output["run"]["residual_state"] == "NOT_COMPUTED"
    assert output["run"]["execution_receipt"]["network_access"] is False

    result = main(
        [
            "show-readback-selection-run",
            "--ledger",
            str(ledger.path),
            "--run",
            "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d0",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["selected_observation"]["id"] == ("a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2")
    assert output["residual_scoring_state"] == "NOT_ENABLED"
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_computes_and_exposes_descriptive_forecast_residual(
    tmp_path: Path, capsys: object
) -> None:
    fixture = phase8e_events()
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in fixture[:46]:
        ledger.append(event)

    result = main(
        [
            "run-forecast-residual",
            "--ledger",
            str(ledger.path),
            "--selection-run",
            "d1d1d1d1-d1d1-41d1-81d1-d1d1d1d1d1d0",
            "--residual-id",
            "e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0",
            "--occurred-at",
            "2026-09-23T12:00:02Z",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    residual = output["forecast_residual"]
    assert residual["score"]["prediction_value"] == 0.75
    assert residual["score"]["observed_value"] == 1.0
    assert residual["score"]["signed_residual"] == 0.25
    assert residual["score"]["absolute_error"] == 0.25
    assert residual["residual_state"] == "COMPUTED_DESCRIPTIVE_REFERENCE_ONLY"
    assert residual["validity_update_state"] == "NOT_APPLIED"
    assert residual["execution_receipt"]["network_access"] is False
    assert output["authority_state"] == "NO_AUTHORITY"

    result = main(
        [
            "show-forecast-residual",
            "--ledger",
            str(ledger.path),
            "--residual",
            "e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["forecast_residual"]["sample_count"] == 1
    assert output["selected_observation"]["id"] == ("a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2")
    assert output["calibration_state"] == "NOT_ESTABLISHED"
    assert output["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_records_and_exposes_residual_readback_abstention(
    tmp_path: Path, capsys: object
) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase8_events()[:43]:
        ledger.append(event)

    result = main(
        [
            "run-residual-readback",
            "--ledger",
            str(ledger.path),
            "--scenario-run",
            "89898989-8989-4989-8989-898989898981",
            "--observation",
            "a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2",
            "--readback-id",
            "c1c1c1c1-c1c1-41c1-81c1-c1c1c1c1c1c1",
            "--occurred-at",
            "2026-09-22T12:00:02Z",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["readback"]["residual_state"] == "NOT_COMPUTED"
    assert output["readback"]["validity_update_state"] == "NOT_APPLIED"
    assert output["readback"]["execution_receipt"]["network_access"] is False

    result = main(
        [
            "show-residual-readback",
            "--ledger",
            str(ledger.path),
            "--readback",
            "c1c1c1c1-c1c1-41c1-81c1-c1c1c1c1c1c1",
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert output["forecast_baseline_state"] == "NOT_AVAILABLE"
    assert output["learning_state"] == "NOT_STARTED"
    assert output["authority_state"] == "NO_AUTHORITY"


def test_cli_creates_and_runs_manual_discrimination_plan(tmp_path: Path, capsys: object) -> None:
    ledger = EventLedger(tmp_path / "events.jsonl")
    ledger.initialize()
    for event in phase7_events()[:38]:
        ledger.append(event)
    candidate = json.dumps(
        {
            "id": "99999999-9999-4999-8999-999999999991",
            "name": "CLI verification candidate",
            "observer_frame_id": "91919191-9191-4191-8191-919191919191",
            "observation_type": "manual.cli_verification",
            "question": "Would an authorized verification artifact discriminate?",
            "expected_outcomes": [
                {
                    "label": "Artifact observed",
                    "hypothesis_effects": [
                        {
                            "hypothesis_id": "81818181-8181-4181-8181-818181818181",
                            "effect": "NO_EFFECT",
                        },
                        {
                            "hypothesis_id": "82828282-8282-4282-8282-828282828282",
                            "effect": "SUPPORTS_HYPOTHESIS",
                        },
                    ],
                }
            ],
        }
    )
    result = main(
        [
            "plan-discriminating-observations",
            "--ledger",
            str(ledger.path),
            "--asset",
            "11111111-1111-4111-8111-111111111111",
            "--name",
            "CLI discrimination fixture",
            "--ambiguity",
            "Relationship evidence may not establish current activity",
            "--belief-revision",
            "84848484-8484-4484-8484-848484848481",
            "--query",
            "39393939-3939-4393-8393-393939393939",
            "--hypothesis",
            "81818181-8181-4181-8181-818181818181",
            "--hypothesis",
            "82828282-8282-4282-8282-828282828282",
            "--candidate-json",
            candidate,
            "--plan-id",
            "99999999-9999-4999-8999-999999999992",
        ]
    )
    plan_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert plan_output["collection_state"] == "NOT_STARTED"
    assert plan_output["run"] is None

    result = main(
        [
            "run-discrimination-plan",
            "--ledger",
            str(ledger.path),
            "--plan",
            "99999999-9999-4999-8999-999999999992",
            "--run-id",
            "99999999-9999-4999-8999-999999999993",
        ]
    )
    run_output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert result == 0
    assert run_output["run"]["top_candidate_ids"] == ["99999999-9999-4999-8999-999999999991"]
    assert run_output["acquisition_state"] == "NOT_ATTEMPTED"
