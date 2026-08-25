from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from readin.cli import main
from readin.projection import ReadinProjection
from readin.store import EventLedger
from readin.synthetic import (
    phase5_events,
    phase7_events,
    phase8_events,
    phase8c_events,
    phase8d_events,
)
from readin.workbench import (
    WorkbenchError,
    build_workbench_snapshot,
    create_workbench_server,
    validate_loopback_host,
)

ASSET_ID = "11111111-1111-4111-8111-111111111111"


def _phase5_ledger(path: Path) -> EventLedger:
    ledger = EventLedger(path)
    ledger.initialize()
    for event in phase5_events():
        ledger.append(event)
    return ledger


def test_workbench_projection_preserves_phase5_boundaries() -> None:
    projection = ReadinProjection.replay(phase5_events())

    snapshot = build_workbench_snapshot(projection, ASSET_ID)

    assert snapshot["schema_version"] == "readin.workbench.v0.1"
    assert snapshot["generated_from"] == {
        "source": "LOCAL_LEDGER_REPLAY",
        "read_only": True,
        "network_access": False,
        "event_count": 37,
    }
    assert snapshot["authority"] == {
        "state": "NO_AUTHORITY",
        "operational_use": "PROHIBITED",
        "writes": "DISABLED",
    }
    assert snapshot["epistemic_limits"] == {
        "coverage_state": "NOT_ESTABLISHED",
        "completeness_claim": "NOT_MADE",
        "probability_state": "NOT_COMPUTED",
        "prediction_state": "NOT_REQUESTED",
        "trajectory_state": "NOT_SIMULATED",
        "empirical_validity_state": "NOT_ESTABLISHED",
        "consensus_state": "NOT_COMPUTED",
        "collection_state": "NOT_STARTED",
        "acquisition_state": "NOT_ATTEMPTED",
        "source_independence_state": "NOT_ESTABLISHED",
        "residual_state": "NOT_COMPUTED",
        "validity_update_state": "NOT_APPLIED",
        "learning_state": "NOT_STARTED",
    }

    asset = snapshot["selected_asset"]
    assert asset["identity"]["canonical_name"] == "Example Research Cooperative"
    assert asset["counts"]["observer_frames"] == 2
    assert asset["cartography"]["latest_query"]["aperture"]["excluded_asset_observation_count"] == 1
    assert asset["cartography"]["latest_query"]["aperture"]["coverage_state"] == ("NOT_ESTABLISHED")
    assert asset["claims"][0]["independence_status"] == "DEPENDENT_EVIDENCE_PRESENT"
    assert asset["fitters"]["latest_run"]["outcome_counts"]["INVALID"] == 1
    assert asset["fitters"]["latest_run"]["consensus"]["state"] == "NOT_COMPUTED"
    assert asset["belief"]["latest_revision"]["probability_state"] == "NOT_COMPUTED"
    assert any(
        branch["kind"] == "UNKNOWN_UNMODELED" for branch in asset["scenarios"][0]["branches"]
    )
    assert asset["scenarios"][0]["prediction_state"] == "NOT_REQUESTED"
    assert asset["authority_state"] == "NO_AUTHORITY"


def test_workbench_exposes_phase7_next_observation_without_collection() -> None:
    snapshot = build_workbench_snapshot(ReadinProjection.replay(phase7_events()), ASSET_ID)
    collection = snapshot["selected_asset"]["collection"]["latest_discrimination"]

    assert snapshot["generated_from"]["event_count"] == 40
    assert collection["recommendation_state"] == "RANKED_STRUCTURAL_CANDIDATES"
    assert collection["candidates"][0]["rank"] == 1
    assert collection["candidates"][0]["name"] == "Independent activity verification"
    assert collection["candidates"][1]["rank"] is None
    assert collection["collection_state"] == "NOT_STARTED"
    assert collection["acquisition_state"] == "NOT_ATTEMPTED"
    assert collection["source_independence_state"] == "NOT_ESTABLISHED"
    assert collection["expected_information_gain_state"] == "NOT_COMPUTED"
    assert snapshot["selected_asset"]["readback"]["latest"] is None


def test_workbench_exposes_phase8_readback_without_residual_or_validity_update() -> None:
    snapshot = build_workbench_snapshot(ReadinProjection.replay(phase8_events()), ASSET_ID)
    readback = snapshot["selected_asset"]["readback"]["latest"]

    assert snapshot["generated_from"]["event_count"] == 44
    assert snapshot["selected_asset"]["counts"]["residual_readbacks"] == 1
    assert snapshot["selected_asset"]["counts"]["forecast_evaluation_designs"] == 1
    design = snapshot["selected_asset"]["forecasting"]["latest_evaluation_design"]
    assert design["preregistration_state"] == "RECORDED_BEFORE_FORECAST_ORIGIN"
    assert design["fitter_selection_state"] == "NOT_SELECTED"
    assert design["prediction_state"] == "NOT_PRODUCED"
    assert readback["scenario_name"] == "Synthetic conditional program horizon"
    assert readback["observation_count"] == 1
    assert readback["forecast_baseline_state"] == "NOT_AVAILABLE"
    assert readback["baseline_eligibility_state"] == "INELIGIBLE_NO_FORECAST_BASELINE"
    assert readback["residual_state"] == "NOT_COMPUTED"
    assert readback["validity_update_state"] == "NOT_APPLIED"
    assert readback["weighting_update_state"] == "NOT_APPLIED"
    assert readback["future_admissibility_update_state"] == "NOT_APPLIED"
    assert readback["learning_state"] == "NOT_STARTED"
    assert readback["network_access"] is False


def test_workbench_exposes_phase8c_baseline_without_scoring_or_learning() -> None:
    snapshot = build_workbench_snapshot(ReadinProjection.replay(phase8c_events()), ASSET_ID)
    asset = snapshot["selected_asset"]
    baseline = asset["forecasting"]["latest_baseline"]
    design = asset["forecasting"]["latest_evaluation_design"]

    assert snapshot["generated_from"]["event_count"] == 44
    assert snapshot["epistemic_limits"]["prediction_state"] == ("PRODUCED_UNCALIBRATED_BASELINE")
    assert asset["counts"]["forecast_baselines"] == 1
    assert asset["counts"]["residual_readbacks"] == 0
    assert design["fitter_selection_state"] == "NOT_SELECTED"
    assert design["forecast_baseline_state"] == "COMPLETED"
    assert design["forecast_execution_state"] == "COMPLETED"
    assert design["prediction_state"] == "PRODUCED_UNCALIBRATED_BASELINE"
    assert baseline["method_name"] == "USER_DECLARED_CONSTANT"
    assert baseline["forecast_method_selection_state"] == ("SELECTED_REFERENCE_CONSTANT_BASELINE")
    assert baseline["prediction_value"] == 0.75
    assert baseline["input_state"] == "NO_TRAINING_INPUTS_USED"
    assert baseline["selected_input_observation_ids"] == []
    assert baseline["calibration_state"] == "NOT_ESTABLISHED"
    assert baseline["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert baseline["residual_scoring_state"] == "NOT_ENABLED"
    assert baseline["learning_state"] == "NOT_STARTED"
    assert baseline["network_access"] is False
    assert asset["readback"]["latest"] is None


def test_workbench_exposes_phase8d_selection_without_residual_or_learning() -> None:
    snapshot = build_workbench_snapshot(ReadinProjection.replay(phase8d_events()), ASSET_ID)
    asset = snapshot["selected_asset"]
    selection = asset["readback"]["latest_selection"]

    assert snapshot["generated_from"]["event_count"] == 46
    assert asset["counts"]["readback_selection_plans"] == 1
    assert asset["counts"]["readback_selection_runs"] == 1
    assert selection["cardinality"] == "EXACTLY_ONE"
    assert selection["selection_state"] == "UNIQUE_MATCH_SELECTED"
    assert selection["candidate_count"] == 1
    assert selection["selected_target_value"] == 1.0
    assert selection["eligible_observer_frames"][0]["name"] == (
        "Synthetic independent technical verification"
    )
    assert selection["aggregation_policy"] == "PROHIBITED"
    assert selection["ranking_policy"] == "NONE"
    assert selection["residual_state"] == "NOT_COMPUTED"
    assert selection["residual_scoring_state"] == "NOT_ENABLED"
    assert selection["calibration_state"] == "NOT_ESTABLISHED"
    assert selection["empirical_validity_state"] == "NOT_ESTABLISHED"
    assert selection["validity_update_state"] == "NOT_APPLIED"
    assert selection["learning_state"] == "NOT_STARTED"
    assert selection["network_access"] is False
    assert asset["readback"]["latest"] is None


def test_workbench_projection_supports_empty_catalog_and_rejects_unknown_asset() -> None:
    empty = build_workbench_snapshot(ReadinProjection())
    assert empty["catalog"] == []
    assert empty["selected_asset"] is None

    with pytest.raises(WorkbenchError, match="unknown tracked asset"):
        build_workbench_snapshot(ReadinProjection.replay(phase5_events()), "missing")


def test_workbench_refuses_non_loopback_binding() -> None:
    validate_loopback_host("localhost")
    validate_loopback_host("127.0.0.1")

    with pytest.raises(WorkbenchError, match="loopback-only"):
        validate_loopback_host("0.0.0.0")


def test_workbench_server_is_static_and_read_only(tmp_path: Path) -> None:
    ledger = _phase5_ledger(tmp_path / "events.jsonl")
    server = create_workbench_server(ledger.path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    try:
        connection.request("GET", "/")
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        assert response.status == 200
        assert "READIN Asset Workbench" in body
        assert "Next observation" in body
        assert "Readback" in body
        assert response.getheader("Content-Security-Policy") == (
            "default-src 'self'; script-src 'self'"
        )

        connection.request("HEAD", "/")
        response = connection.getresponse()
        response.read()
        assert response.status == 204
        assert response.getheader("Cache-Control") == "no-store"

        connection.request("GET", f"/api/workbench?asset={ASSET_ID}")
        response = connection.getresponse()
        payload = json.loads(response.read())
        assert response.status == 200
        assert payload["selected_asset"]["identity"]["id"] == ASSET_ID
        assert payload["authority"]["state"] == "NO_AUTHORITY"

        connection.request("POST", "/api/workbench", body=b"{}")
        response = connection.getresponse()
        payload = json.loads(response.read())
        assert response.status == 405
        assert response.getheader("Allow") == "GET, HEAD"
        assert payload == {
            "error": "workbench is read-only",
            "authority_state": "NO_AUTHORITY",
        }

        connection.request("GET", "/../pyproject.toml")
        response = connection.getresponse()
        payload = json.loads(response.read())
        assert response.status == 404
        assert payload["authority_state"] == "NO_AUTHORITY"
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_cli_emits_workbench_projection(tmp_path: Path, capsys: object) -> None:
    ledger = _phase5_ledger(tmp_path / "events.jsonl")

    result = main(
        [
            "show-workbench",
            "--ledger",
            str(ledger.path),
            "--asset",
            ASSET_ID,
        ]
    )
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]

    assert result == 0
    assert output["schema_version"] == "readin.workbench.v0.1"
    assert output["authority"]["writes"] == "DISABLED"
    assert output["selected_asset"]["identity"]["id"] == ASSET_ID
