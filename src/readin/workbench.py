"""Read-only Phase 6 workbench projection and loopback HTTP server."""

from __future__ import annotations

import json
import socket
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from readin.projection import ProjectionError, ReadinProjection
from readin.store import EventLedger, LedgerError

WORKBENCH_SCHEMA_VERSION = "readin.workbench.v0.1"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class WorkbenchError(ValueError):
    """Raised when the bounded workbench contract cannot be produced or served."""


def _entity_label(projection: ReadinProjection, entity_id: str) -> str:
    entity = projection.entities.get(entity_id)
    return entity["canonical_name"] if entity is not None else entity_id


def _claim_object_label(projection: ReadinProjection, value: dict[str, Any]) -> str:
    if value["kind"] == "ENTITY":
        return _entity_label(projection, value["entity_id"])
    return json.dumps(value["value"], sort_keys=True, ensure_ascii=False)


def _catalog_item(item: dict[str, Any]) -> dict[str, Any]:
    entity = item["entity"]
    tracked = item["tracked_asset"]
    return {
        "id": entity["id"],
        "canonical_name": entity["canonical_name"],
        "entity_type": entity["type"],
        "priority": tracked["tracking"]["priority"],
        "state_version": tracked["epistemic_state_version"],
        "counts": {
            "observations": item["observation_count"],
            "claims": item["claim_count"],
            "relations": item["relation_count"],
            "hypotheses": item["hypothesis_count"],
            "scenarios": item["scenario_count"],
        },
        "authority_state": "NO_AUTHORITY",
    }


def _asset_workbench(projection: ReadinProjection, entity_id: str) -> dict[str, Any]:
    view = projection.asset_view(entity_id)
    entity = view["entity"]
    tracked = view["tracked_asset"]
    observation_count_by_frame: dict[str, int] = {}
    for observation in view["observations"]:
        frame_id = observation["observer_frame_id"]
        observation_count_by_frame[frame_id] = observation_count_by_frame.get(frame_id, 0) + 1

    frames = [
        {
            "id": frame["id"],
            "name": frame["name"],
            "frame_class": frame["class"],
            "access_scope": frame["access_projection"]["scope"],
            "observation_count": observation_count_by_frame.get(frame["id"], 0),
            "blind_regions": deepcopy(frame["known_blind_regions"]),
            "validity_conditions": deepcopy(frame["validity_conditions"]),
        }
        for frame in view["observer_frames"]
    ]

    claims = []
    for claim_view in view["claims"]:
        claim = claim_view["claim"]
        claims.append(
            {
                "id": claim["id"],
                "predicate": claim["predicate"],
                "object_label": _claim_object_label(projection, claim["object"]),
                "modality": claim["modality"],
                "epistemic_status": claim["epistemic_status"],
                "evidence_role_counts": deepcopy(claim_view["evidence_role_counts"]),
                "dependency_groups": deepcopy(claim_view["dependency_groups"]),
                "independence_status": claim_view["independence_status"],
                "invalidation_conditions": deepcopy(claim["invalidation_conditions"]),
            }
        )

    relations = [
        {
            "id": relation["id"],
            "relation_type": relation["relation_type"],
            "relation_semantics": relation["relation_semantics"],
            "source_label": _entity_label(projection, relation["source_entity"]),
            "target_label": _entity_label(projection, relation["target_entity"]),
            "claim_ids": deepcopy(relation["claims"]),
        }
        for relation in view["relations"]
    ]

    latest_query = None
    if view["cartographic_query_plans"]:
        plan_view = view["cartographic_query_plans"][-1]
        result = projection.execute_cartographic_query(plan_view["plan"]["id"])
        latest_query = {
            "id": plan_view["plan"]["id"],
            "direction": plan_view["plan"]["direction"],
            "reconstruction_mode": plan_view["plan"]["reconstruction"]["mode"],
            "epistemic_cutoff": plan_view["plan"]["reconstruction"]["epistemic_cutoff"],
            "hindsight_in_query_lens": plan_view["query_lens"]["hindsight_in_query_lens"],
            "surfaces": [
                {
                    "id": surface["surface"]["id"],
                    "name": surface["surface"]["name"],
                    "coverage_state": surface["coverage_state"],
                    "completeness_claim": surface["completeness_claim"],
                    "blind_region_state": surface["surface"]["blind_region_state"],
                }
                for surface in plan_view["surfaces"]
            ],
            "aperture": deepcopy(result["aperture"]),
            "blind_regions": deepcopy(result["blind_regions"]),
            "execution": deepcopy(result["execution"]),
        }

    latest_fitter = None
    if view["multi_fitter_runs"]:
        run = view["multi_fitter_runs"][-1]
        latest_fitter = {
            "run_group_id": run["run_group_id"],
            "completion_state": run["completion_state"],
            "outcome_counts": deepcopy(run["outcome_counts"]),
            "disagreement": deepcopy(run["disagreement"]),
            "consensus": deepcopy(run["consensus"]),
            "empirical_validity_state": run["empirical_validity_state"],
            "prediction_state": run["prediction_state"],
            "runs": [
                {
                    "fitter_id": item["run"]["fitter_id"],
                    "fitter_class": item["descriptor"]["fitter_class"],
                    "name": item["descriptor"]["name"],
                    "outcome": item["run"]["outcome"],
                    "admissibility": item["run"]["admissibility"]["status"],
                    "target_metric": item["descriptor"]["target_metric"],
                }
                for item in run["runs"]
            ],
        }

    hypothesis_state: dict[str, str] = {}
    latest_revision = None
    if view["belief_revisions"]:
        revision = view["belief_revisions"][-1]
        hypothesis_state = {
            item["hypothesis_id"]: item["state"] for item in revision["revision"]["node_results"]
        }
        latest_revision = {
            "id": revision["revision"]["id"],
            "recorded_at": revision["revision"]["recorded_at"],
            "probability_state": revision["probability_state"],
            "prediction_state": revision["prediction_state"],
            "interpretation": revision["interpretation"],
        }
    hypotheses = [
        {
            "id": item["hypothesis"]["id"],
            "name": item["hypothesis"]["name"],
            "statement": item["hypothesis"]["proposition"]["statement"],
            "state": hypothesis_state.get(item["hypothesis"]["id"], "UNRESOLVED"),
            "probability_state": item["probability_state"],
        }
        for item in view["hypotheses"]
    ]

    scenarios = []
    for item in view["scenarios"]:
        scenario = item["scenario"]
        run_by_branch = {
            result["branch_id"]: result for result in (item["run"] or {}).get("branch_results", [])
        }
        scenarios.append(
            {
                "id": scenario["id"],
                "name": scenario["name"],
                "horizon_days": scenario["horizon_days"],
                "unknown_branch_visible": item["unknown_branch_visible"],
                "likelihood_state": item["likelihood_state"],
                "trajectory_state": item["trajectory_state"],
                "prediction_state": item["prediction_state"],
                "branches": [
                    {
                        "id": branch["id"],
                        "name": branch["name"],
                        "kind": branch["kind"],
                        "outcome_statement": branch["outcome_statement"],
                        "antecedent_state": run_by_branch.get(branch["id"], {}).get(
                            "antecedent_state", "NOT_EVALUATED"
                        ),
                        "outcome_state": run_by_branch.get(branch["id"], {}).get(
                            "outcome_state", "NOT_EVALUATED"
                        ),
                    }
                    for branch in scenario["branches"]
                ],
            }
        )

    timeline = projection.timeline_view(entity_id)["entries"]
    return {
        "identity": {
            "id": entity["id"],
            "canonical_name": entity["canonical_name"],
            "entity_type": entity["type"],
            "aliases": deepcopy(entity["aliases"]),
            "status": entity["status"],
        },
        "tracking": {
            "priority": tracked["tracking"]["priority"],
            "scopes": deepcopy(tracked["scopes"]),
            "state_version": tracked["epistemic_state_version"],
            "collection_profile": tracked["tracking"]["collection_profile"],
        },
        "counts": {
            "observations": len(view["observations"]),
            "claims": len(claims),
            "relations": len(relations),
            "observer_frames": len(frames),
            "evidence_manifests": len(view["evidence_manifests"]),
            "dependency_edges": len(view["evidence_dependencies"]),
            "resolution_candidates": len(view["resolution_candidates"]),
            "hypotheses": len(hypotheses),
            "scenarios": len(scenarios),
            "timeline_events": len(timeline),
        },
        "observer_frames": frames,
        "cartography": {
            "surface_count": len(
                {
                    surface["surface"]["id"]
                    for plan_view in view["cartographic_query_plans"]
                    for surface in plan_view["surfaces"]
                }
            ),
            "latest_query": latest_query,
        },
        "claims": claims,
        "relations": relations,
        "evidence": {
            "manifests": [
                {
                    "id": item["id"],
                    "source_label": item["source"]["label"],
                    "source_uri": item["source"]["uri"],
                    "access_policy": item["access_policy"],
                    "sha256": item["sha256"],
                    "transformation_count": len(item["transformations"]),
                }
                for item in view["evidence_manifests"]
            ],
            "dependencies": [
                {
                    "id": item["id"],
                    "group_id": item["dependency_group_id"],
                    "relationship": item["relationship"],
                    "verification_status": item["verification_status"],
                }
                for item in view["evidence_dependencies"]
            ],
        },
        "resolution_candidates": [
            {
                "id": item["candidate"]["id"],
                "candidate_label": _entity_label(
                    projection,
                    item["candidate"]["right_entity_id"]
                    if item["candidate"]["left_entity_id"] == entity_id
                    else item["candidate"]["left_entity_id"],
                ),
                "disposition": item["current_disposition"],
                "merge_state": item["merge_state"],
                "reversible": item["reversible"],
            }
            for item in view["resolution_candidates"]
        ],
        "fitters": {"latest_run": latest_fitter},
        "belief": {"latest_revision": latest_revision, "hypotheses": hypotheses},
        "scenarios": scenarios,
        "timeline": [
            {
                "event_id": item["event_id"],
                "event_type": item["event_type"],
                "recorded_at": item["recorded_at"],
                "effective_at": item["effective_at"],
                "hindsight": item["hindsight"],
            }
            for item in reversed(timeline)
        ],
        "authority_state": "NO_AUTHORITY",
    }


def build_workbench_snapshot(
    projection: ReadinProjection, asset_id: str | None = None
) -> dict[str, Any]:
    """Build the closed, presentation-only workbench read model."""

    catalog = [_catalog_item(item) for item in projection.catalog_view()]
    selected_id = asset_id or (catalog[0]["id"] if catalog else None)
    if selected_id is not None and selected_id not in projection.assets:
        raise WorkbenchError(f"unknown tracked asset: {selected_id}")
    return {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "generated_from": {
            "source": "LOCAL_LEDGER_REPLAY",
            "read_only": True,
            "network_access": False,
            "event_count": len(projection.event_ids),
        },
        "authority": {
            "state": "NO_AUTHORITY",
            "operational_use": "PROHIBITED",
            "writes": "DISABLED",
        },
        "epistemic_limits": {
            "coverage_state": "NOT_ESTABLISHED",
            "completeness_claim": "NOT_MADE",
            "probability_state": "NOT_COMPUTED",
            "prediction_state": "NOT_REQUESTED",
            "trajectory_state": "NOT_SIMULATED",
            "empirical_validity_state": "NOT_ESTABLISHED",
            "consensus_state": "NOT_COMPUTED",
        },
        "catalog": catalog,
        "selected_asset": (
            _asset_workbench(projection, selected_id) if selected_id is not None else None
        ),
    }


def build_ledger_workbench_snapshot(
    ledger_path: str | Path, asset_id: str | None = None
) -> dict[str, Any]:
    """Replay one local ledger and build its read-only workbench view."""

    return build_workbench_snapshot(EventLedger(ledger_path).projection(), asset_id)


def validate_loopback_host(host: str) -> None:
    """Reject non-loopback bindings for the bounded local workbench."""

    if host.lower() not in LOOPBACK_HOSTS:
        raise WorkbenchError(
            f"workbench host must be loopback-only ({', '.join(sorted(LOOPBACK_HOSTS))}): {host}"
        )


class WorkbenchHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying only an immutable local-ledger path."""

    def __init__(self, address: tuple[str, int], ledger_path: Path) -> None:
        self.ledger_path = ledger_path
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, WorkbenchRequestHandler)


class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    """Serve the static interface and a single read-only JSON endpoint."""

    server: WorkbenchHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        target = urlsplit(self.path)
        if target.path == "/api/workbench":
            asset_values = parse_qs(target.query).get("asset", [])
            asset_id = asset_values[0] if asset_values else None
            try:
                payload = build_ledger_workbench_snapshot(self.server.ledger_path, asset_id)
            except (LedgerError, ProjectionError, WorkbenchError) as error:
                self._send_json(
                    {"error": str(error), "authority_state": "NO_AUTHORITY"},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            self._send_json(payload)
            return

        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/index.html": ("index.html", "text/html; charset=utf-8"),
            "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
        }
        if target.path not in assets:
            self._send_json(
                {"error": "not found", "authority_state": "NO_AUTHORITY"},
                HTTPStatus.NOT_FOUND,
            )
            return
        asset_name, media_type = assets[target.path]
        resource = files("readin").joinpath(f"workbench_assets/{asset_name}")
        if not resource.is_file():
            self._send_json(
                {"error": "workbench asset unavailable", "authority_state": "NO_AUTHORITY"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self._send_bytes(resource.read_bytes(), media_type)

    def do_HEAD(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._security_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PUT(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802
        self._method_not_allowed()

    def _method_not_allowed(self) -> None:
        self._send_json(
            {
                "error": "workbench is read-only",
                "authority_state": "NO_AUTHORITY",
            },
            HTTPStatus.METHOD_NOT_ALLOWED,
            extra_headers={"Allow": "GET, HEAD"},
        )

    def _security_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")

    def _send_json(
        self,
        value: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
        *,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
        self._send_bytes(body, "application/json; charset=utf-8", status, extra_headers)

    def _send_bytes(
        self,
        body: bytes,
        media_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Keep normal local requests quiet; callers control operational logging."""


def create_workbench_server(
    ledger_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 4173,
) -> WorkbenchHTTPServer:
    """Create a loopback-only workbench server without starting its event loop."""

    validate_loopback_host(host)
    path = Path(ledger_path)
    EventLedger(path).projection()
    return WorkbenchHTTPServer((host, port), path)


def serve_workbench(
    ledger_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 4173,
) -> None:
    """Serve the workbench until interrupted."""

    server = create_workbench_server(ledger_path, host=host, port=port)
    try:
        print(f"READIN workbench · NO_AUTHORITY · http://{host}:{server.server_port}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
