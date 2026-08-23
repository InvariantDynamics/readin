from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from readin.cli import main
from readin.projection import ReadinProjection
from readin.store import EventLedger
from readin.synthetic import phase5_events
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
