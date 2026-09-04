"""Read-only workbench through bounded Phase 8G fitter specification registration."""

from __future__ import annotations

import ipaddress
import json
import socket
import webbrowser
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from readin.connector_grants import CONNECTOR_GRANT_OBSERVATION_TYPE
from readin.local_source_exports import LOCAL_SOURCE_EXPORT_ADAPTER
from readin.projection import ProjectionError, ReadinProjection
from readin.store import EventLedger, LedgerError

WORKBENCH_SCHEMA_VERSION = "readin.workbench.v0.1"
LOOPBACK_BIND_HOSTS = frozenset({"127.0.0.1", "::1"})
LOOPBACK_REQUEST_HOSTS = LOOPBACK_BIND_HOSTS | {"localhost"}


class WorkbenchError(ValueError):
    """Raised when the bounded workbench contract cannot be produced or served."""


class _RequestAuthorityError(ValueError):
    """Internal fail-closed classification for an untrusted HTTP authority."""

    def __init__(self, message: str, status: HTTPStatus) -> None:
        super().__init__(message)
        self.status = status


def _parse_loopback_authority(
    value: str,
    *,
    server_port: int,
    default_port: int,
    field_name: str,
) -> None:
    """Require one syntactically complete loopback authority for this listener."""

    if not value or value != value.strip():
        raise _RequestAuthorityError(f"malformed {field_name}", HTTPStatus.BAD_REQUEST)

    try:
        parsed = urlsplit(f"//{value}")
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise _RequestAuthorityError(f"malformed {field_name}", HTTPStatus.BAD_REQUEST) from error

    if (
        not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or value.endswith(":")
    ):
        raise _RequestAuthorityError(f"malformed {field_name}", HTTPStatus.BAD_REQUEST)
    if hostname.lower() not in LOOPBACK_REQUEST_HOSTS:
        raise _RequestAuthorityError(f"untrusted {field_name}", HTTPStatus.MISDIRECTED_REQUEST)
    if (port if port is not None else default_port) != server_port:
        raise _RequestAuthorityError(
            f"{field_name} port does not match listener",
            HTTPStatus.MISDIRECTED_REQUEST,
        )


def _validate_origin(value: str, *, server_port: int) -> None:
    """Require a present Origin to identify this loopback HTTP listener."""

    if not value or value != value.strip():
        raise _RequestAuthorityError("malformed Origin", HTTPStatus.FORBIDDEN)

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise _RequestAuthorityError("malformed Origin", HTTPStatus.FORBIDDEN) from error

    if (
        parsed.scheme.lower() != "http"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.netloc.endswith(":")
        or hostname.lower() not in LOOPBACK_REQUEST_HOSTS
        or (port if port is not None else 80) != server_port
    ):
        raise _RequestAuthorityError("untrusted Origin", HTTPStatus.FORBIDDEN)


def _entity_label(projection: ReadinProjection, entity_id: str) -> str:
    entity = projection.entities.get(entity_id)
    return entity["canonical_name"] if entity is not None else entity_id


def _claim_object_label(projection: ReadinProjection, value: dict[str, Any]) -> str:
    if value["kind"] == "ENTITY":
        return _entity_label(projection, value["entity_id"])
    return json.dumps(value["value"], sort_keys=True, ensure_ascii=False)


def _asset_catalog_binding(entity: dict[str, Any]) -> dict[str, Any] | None:
    binding = entity["attributes"].get("asset_catalog_binding")
    return binding if isinstance(binding, dict) else None


def _connector_intent(binding: dict[str, Any] | None) -> dict[str, Any] | None:
    if binding is None:
        return None
    connector = binding.get("connector_intent")
    return connector if isinstance(connector, dict) else None


def _connector_grant_payload(observation: dict[str, Any]) -> dict[str, Any] | None:
    if observation["observation_type"] != CONNECTOR_GRANT_OBSERVATION_TYPE:
        return None
    payload = observation["content"]["structured_payload"]
    grant = payload.get("connector_grant") if isinstance(payload, dict) else None
    return grant if isinstance(grant, dict) else None


def _latest_connector_grant(observations: list[dict[str, Any]]) -> dict[str, Any] | None:
    grants = [
        {"observation": observation, "grant": grant}
        for observation in observations
        if (grant := _connector_grant_payload(observation)) is not None
    ]
    if not grants:
        return None
    item = grants[-1]
    grant = item["grant"]
    observation = item["observation"]
    return {
        "observation_id": observation["id"],
        "source_artifact_id": observation["source_artifact_id"],
        "observed_at": observation["observed_at"],
        "grant_id": grant["grant_id"],
        "grant_kind": grant["grant"]["grant_kind"],
        "grant_state": grant["grant"]["grant_state"],
        "access_mode": grant["grant"]["access_mode"],
        "connector_kind": grant["provider"]["connector_kind"],
        "connector_name": grant["provider"]["connector_name"],
        "connector_version": grant["provider"]["connector_version"],
        "terms_review_state": grant["provider"]["terms_review_state"],
        "scope_count": len(grant["scopes"]),
        "allowed_observation_type_count": len(grant["allowed_observation_types"]),
        "scopes": deepcopy(grant["scopes"]),
        "allowed_observation_types": deepcopy(grant["allowed_observation_types"]),
        "retention": deepcopy(grant["retention"]),
        "revocation": deepcopy(grant["revocation"]),
        "audit": deepcopy(grant["audit"]),
        "authority_state": grant["authority_state"],
        "collection_state": grant["collection_state"],
        "credential_material": grant["credential_material"],
        "credential_storage": grant["credential_storage"],
        "oauth_state": grant["oauth_state"],
        "live_collection_state": grant["live_collection_state"],
        "network_access": grant["network_access"],
        "external_action_state": grant["external_action_state"],
        "people_targeting": grant["people_targeting"],
        "activation_requirement": grant["activation_requirement"],
        "source_digest_sha256": grant["source_digest_sha256"],
    }


def _source_export_summaries(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches: dict[str, dict[str, Any]] = {}
    for observation in observations:
        if observation["provenance"]["adapter"] != LOCAL_SOURCE_EXPORT_ADAPTER:
            continue
        receipt = observation["content"]["structured_payload"].get("source_export")
        if not isinstance(receipt, dict) or not isinstance(receipt.get("export_id"), str):
            continue
        export_id = receipt["export_id"]
        if export_id not in batches:
            batches[export_id] = {
                "export_id": export_id,
                "grant_id": receipt.get("grant_id"),
                "source_sha256": receipt.get("source_sha256"),
                "source_size": receipt.get("source_size"),
                "expected_observation_count": receipt.get("observation_count"),
                "observation_count": 0,
                "observation_ids": [],
                "observation_types": [],
                "imported_at": observation["provenance"]["acquisition_time"],
                "source_artifact_id": observation["source_artifact_id"],
            }
        batch = batches[export_id]
        batch["observation_count"] += 1
        batch["observation_ids"].append(observation["id"])
        if observation["observation_type"] not in batch["observation_types"]:
            batch["observation_types"].append(observation["observation_type"])
    for batch in batches.values():
        batch["state"] = (
            "IMPORTED"
            if batch["observation_count"] == batch["expected_observation_count"]
            else "PARTIAL_IMPORT"
        )
    return list(batches.values())


def _catalog_item(item: dict[str, Any]) -> dict[str, Any]:
    entity = item["entity"]
    tracked = item["tracked_asset"]
    binding = _asset_catalog_binding(entity)
    connector = _connector_intent(binding)
    return {
        "id": entity["id"],
        "canonical_name": entity["canonical_name"],
        "entity_type": entity["type"],
        "asset_class": binding.get("asset_class") if binding else None,
        "platform": binding.get("platform") if binding else None,
        "connection_state": connector.get("connection_state") if connector else None,
        "connector_kind": connector.get("connector_kind") if connector else None,
        "live_collection_state": connector.get("live_collection_state") if connector else None,
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


def _asset_catalog_workbench_summary(catalog: list[dict[str, Any]]) -> dict[str, Any]:
    catalog_items = [item for item in catalog if item["asset_class"] is not None]
    class_counts: dict[str, int] = {}
    connection_counts: dict[str, int] = {}
    connector_counts: dict[str, int] = {}
    for item in catalog_items:
        class_counts[item["asset_class"]] = class_counts.get(item["asset_class"], 0) + 1
        connection_state = item["connection_state"] or "UNKNOWN"
        connection_counts[connection_state] = connection_counts.get(connection_state, 0) + 1
        connector_kind = item["connector_kind"] or "UNKNOWN"
        connector_counts[connector_kind] = connector_counts.get(connector_kind, 0) + 1
    return {
        "state": ("LOCAL_MANIFEST_ASSET_CATALOG_PRESENT" if catalog_items else "NOT_PRESENT"),
        "asset_count": len(catalog_items),
        "asset_class_counts": dict(sorted(class_counts.items())),
        "connection_state_counts": dict(sorted(connection_counts.items())),
        "connector_kind_counts": dict(sorted(connector_counts.items())),
        "credential_state": "NONE",
        "live_collection_state": "DISABLED",
        "network_access": False,
        "external_action_state": "PROHIBITED",
        "people_targeting": "PROHIBITED",
        "authority_state": "NO_AUTHORITY",
    }


def _observation_workbench(observation: dict[str, Any]) -> dict[str, Any]:
    """Project one immutable observation without promoting it to a claim."""

    return {
        "id": observation["id"],
        "observation_type": observation["observation_type"],
        "observed_at": observation["observed_at"],
        "observer_frame_id": observation["observer_frame_id"],
        "source_artifact_id": observation["source_artifact_id"],
        "immutable": observation["immutable"],
        "content": deepcopy(observation["content"]),
        "provenance": deepcopy(observation["provenance"]),
        "epistemic": deepcopy(observation["epistemic"]),
    }


def _event_payload_label(event: dict[str, Any]) -> str:
    payload = event["payload"]
    event_type = event["event_type"]
    if event_type == "entity.created":
        return payload["entity"]["canonical_name"]
    if event_type == "asset.tracking_started":
        return payload["tracked_asset"]["entity_id"]
    if event_type == "observer_frame.registered":
        return payload["observer_frame"]["name"]
    if event_type == "evidence.manifested":
        return payload["evidence_manifest"]["source"]["label"]
    if event_type == "observation.admitted":
        return payload["observation"]["observation_type"]
    return event_type


def _ledger_event_audit(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "event_id": event["event_id"],
            "event_type": event["event_type"],
            "occurred_at": event["occurred_at"],
            "authority_state": event["authority_state"],
            "payload_label": _event_payload_label(event),
        }
        for index, event in enumerate(events, start=1)
    ]


def _path_audit_item(
    label: str,
    path: Path,
    *,
    state: str,
    sha256: str | None = None,
    missing_state: str = "NOT_PRESENT",
) -> dict[str, Any]:
    try:
        target_stat = path.lstat()
    except FileNotFoundError:
        target_stat = None
    return {
        "label": label,
        "path": str(path),
        "state": state if target_stat is not None else missing_state,
        "sha256": sha256,
        "size": target_stat.st_size if target_stat is not None else None,
    }


def _case_audit_workbench(
    case_path: Path,
    ledger_path: Path,
    events: list[dict[str, Any]],
    policy_digest: str,
    manifest: dict[str, Any] | None,
    case_binding: dict[str, Any] | None,
    network_attempt: dict[str, Any] | None,
) -> dict[str, Any]:
    if len(events) == 5:
        sequence_state = "CLOSED_H0_SEQUENCE_VERIFIED"
    elif len(events) == 3:
        sequence_state = "INITIAL_H0_SEQUENCE_VERIFIED"
    else:
        sequence_state = "INVALID_SEQUENCE_BLOCKED"

    files_audit = [
        _path_audit_item(
            "Case policy",
            case_path / "policy.json",
            state="PRIVATE_DIGEST_VERIFIED",
            sha256=policy_digest,
        ),
        _path_audit_item("Event ledger", ledger_path, state="PRIVATE_REPLAY_VERIFIED"),
        _path_audit_item(
            "Network-attempt marker",
            case_path / "network-attempt.json",
            state=("PRIVATE_MARKER_VERIFIED" if network_attempt is not None else "NOT_ATTEMPTED"),
            missing_state="NOT_ATTEMPTED",
        ),
    ]
    if case_binding is not None:
        files_audit.append(
            _path_audit_item(
                "Acquisition receipt",
                case_path / "receipts" / f"{case_binding['acquisition_receipt_id']}.json",
                state="PRIVATE_DIGEST_VERIFIED",
                sha256=case_binding["acquisition_receipt_sha256"],
            )
        )
    else:
        files_audit.append(
            {
                "label": "Acquisition receipt",
                "path": str(case_path / "receipts"),
                "state": "NOT_PRESENT",
                "sha256": None,
                "size": None,
            }
        )
    if manifest is not None:
        files_audit.append(
            _path_audit_item(
                "Raw source artifact",
                case_path / "evidence" / "sha256" / manifest["sha256"],
                state="PRIVATE_SHA256_VERIFIED",
                sha256=manifest["sha256"],
            )
        )
    else:
        files_audit.append(
            {
                "label": "Raw source artifact",
                "path": str(case_path / "evidence" / "sha256"),
                "state": "NOT_PRESENT",
                "sha256": None,
                "size": None,
            }
        )

    return {
        "case_dir": str(case_path),
        "ledger_path": str(ledger_path),
        "sequence_state": sequence_state,
        "event_count": len(events),
        "ledger_events": _ledger_event_audit(events),
        "files": files_audit,
        "read_gate": "PASSED",
        "raw_artifact_preview": "NOT_EXPOSED",
        "authority_state": "NO_AUTHORITY",
    }


def _real_asset_case_workbench(
    policy: dict[str, Any],
    policy_digest: str,
    projection: ReadinProjection,
    network_attempt: dict[str, Any] | None,
    *,
    case_path: Path,
    ledger_path: Path,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a read-only summary after the complete H0 case read gate succeeds."""

    target = policy["target"]
    observations = [
        observation
        for observation in projection.observations.values()
        if target["entity_id"] in observation["subject_entities"]
        and observation["provenance"]["adapter"] == "github-public-rest"
    ]
    observation = observations[0] if observations else None
    manifest = (
        projection.evidence.get(observation["source_artifact_id"])
        if observation is not None
        else None
    )
    case_binding = (
        observation["content"]["structured_payload"]["case_binding"]
        if observation is not None
        else None
    )

    if observation is not None:
        case_state = "VALIDATED_ARTIFACT_ADMITTED"
        collection_result = "ARTIFACT_ADMITTED"
    elif network_attempt is not None:
        case_state = "VALIDATED_ATTEMPT_NO_ADMISSION"
        collection_result = "NO_ARTIFACT_ADMITTED"
    else:
        case_state = "VALIDATED_NOT_ATTEMPTED"
        collection_result = "NOT_ATTEMPTED"

    custody_checks = [
        {
            "component": "Case policy",
            "state": "DIGEST_VERIFIED",
            "detail": f"sha256:{policy_digest}",
        },
        {
            "component": "Ledger binding",
            "state": "REPLAY_VERIFIED",
            "detail": "Policy target and the closed H0 event sequence agree",
        },
        {
            "component": "Network attempt",
            "state": "MARKER_VERIFIED" if network_attempt is not None else "NOT_ATTEMPTED",
            "detail": (
                "One request budget reserved before transport"
                if network_attempt is not None
                else "No request marker exists"
            ),
        },
        {
            "component": "Acquisition receipt",
            "state": "DIGEST_AND_BINDING_VERIFIED" if case_binding else "NOT_PRESENT",
            "detail": (
                f"Receipt {case_binding['acquisition_receipt_id']}"
                if case_binding
                else "No artifact was admitted"
            ),
        },
        {
            "component": "Raw source artifact",
            "state": "SHA256_VERIFIED" if manifest else "NOT_PRESENT",
            "detail": (
                f"sha256:{manifest['sha256']}" if manifest else "No retained source artifact"
            ),
        },
        {
            "component": "Manifest and observation",
            "state": "SOURCE_REDERIVED_AND_MATCHED" if observation else "NOT_PRESENT",
            "detail": (
                "Stored bytes re-parse to the admitted immutable observation"
                if observation
                else "No observation was admitted"
            ),
        },
    ]

    return {
        "state": case_state,
        "case_id": policy["case_id"],
        "policy_id": policy["policy_id"],
        "policy_sha256": policy_digest,
        "declared_at": policy["declared_at"],
        "purpose": deepcopy(policy["purpose"]),
        "target": deepcopy(target),
        "source": deepcopy(policy["source"]),
        "budgets": {
            **deepcopy(policy["budgets"]),
            "network_requests_used": 1 if network_attempt is not None else 0,
            "artifacts_admitted": len(observations),
        },
        "retention": deepcopy(policy["retention"]),
        "minimization": deepcopy(policy["minimization"]),
        "authority": deepcopy(policy["authority"]),
        "collection": {
            "result": collection_result,
            "attempt_state": (
                network_attempt["state"] if network_attempt is not None else "NOT_ATTEMPTED"
            ),
            "authorized_at": (
                network_attempt["authorized_at"] if network_attempt is not None else None
            ),
        },
        "evidence": (
            {
                "manifest_id": manifest["id"],
                "receipt_id": case_binding["acquisition_receipt_id"],
                "receipt_sha256": case_binding["acquisition_receipt_sha256"],
                "artifact_sha256": manifest["sha256"],
                "media_type": manifest["media_type"],
                "size": manifest["size"],
                "acquired_at": manifest["acquired_at"],
                "http_status": 200,
            }
            if manifest is not None and case_binding is not None
            else None
        ),
        "custody": {
            "state": "FULL_CHAIN_VERIFIED",
            "checks": custody_checks,
        },
        "audit": _case_audit_workbench(
            case_path,
            ledger_path,
            events,
            policy_digest,
            manifest,
            case_binding,
            network_attempt,
        ),
        "authority_state": "NO_AUTHORITY",
    }


def _asset_workbench(projection: ReadinProjection, entity_id: str) -> dict[str, Any]:
    view = projection.asset_view(entity_id)
    entity = view["entity"]
    real_asset_case_binding = entity["attributes"].get("real_asset_case_binding")
    asset_catalog_binding = _asset_catalog_binding(entity)
    connector_intent = _connector_intent(asset_catalog_binding)
    latest_connector_grant = _latest_connector_grant(view["observations"])
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

    discrimination = None
    if view["discrimination_plans"]:
        item = view["discrimination_plans"][-1]
        plan = item["plan"]
        run = item["run"]
        candidate_by_id = {candidate["id"]: candidate for candidate in plan["candidates"]}
        scores = run["candidate_scores"] if run is not None else []
        discrimination = {
            "id": plan["id"],
            "name": plan["name"],
            "ambiguity_statement": plan["ambiguity_statement"],
            "recommendation_state": (
                run["recommendation_state"] if run is not None else "NOT_EVALUATED"
            ),
            "top_candidate_ids": deepcopy(run["top_candidate_ids"] if run else []),
            "collection_state": item["collection_state"],
            "acquisition_state": item["acquisition_state"],
            "source_independence_state": item["source_independence_state"],
            "expected_information_gain_state": item["expected_information_gain_state"],
            "probability_state": item["probability_state"],
            "ranking_interpretation": (
                "STRUCTURAL_ORDINAL_HEURISTIC_NOT_EXPECTED_INFORMATION_GAIN"
            ),
            "candidates": [
                {
                    **deepcopy(score),
                    "name": candidate_by_id[score["candidate_id"]]["name"],
                    "question": candidate_by_id[score["candidate_id"]]["question"],
                    "observation_type": candidate_by_id[score["candidate_id"]]["observation_type"],
                    "effort": candidate_by_id[score["candidate_id"]]["effort"],
                    "observer_frame_name": projection.frames[
                        candidate_by_id[score["candidate_id"]]["observer_frame_id"]
                    ]["name"],
                    "blind_region_targets": deepcopy(
                        candidate_by_id[score["candidate_id"]]["declared_blind_region_targets"]
                    ),
                }
                for score in scores
            ],
        }

    forecast_design = None
    forecast_baseline = None
    if view["forecast_evaluation_designs"]:
        item = view["forecast_evaluation_designs"][-1]
        design = item["design"]
        baseline = item["forecast_baseline"]
        forecast_design = {
            "id": design["id"],
            "name": design["name"],
            "scenario_name": item["scenario"]["name"],
            "observation_type": design["target"]["observation_type"],
            "structured_field_path": deepcopy(design["target"]["structured_field_path"]),
            "unit": design["target"]["unit"],
            "target_semantics": design["target"]["target_semantics"],
            "metric_name": design["metric"]["name"],
            "metric_state": design["metric"]["metric_state"],
            "residual_definition": design["metric"]["residual_definition"],
            "training_cutoff": design["timing"]["training_cutoff"],
            "forecast_origin": design["timing"]["forecast_origin"],
            "horizon_end": design["timing"]["horizon_end"],
            "leakage_basis": design["timing"]["leakage_basis"],
            "post_cutoff_input_policy": design["timing"]["post_cutoff_input_policy"],
            "preregistration_state": design["preregistration_state"],
            "fitter_selection_state": design["fitter_selection_state"],
            "forecast_capable_fitter_state": item["forecast_capable_fitter_state"],
            "forecast_baseline_state": item["forecast_baseline_state"],
            "forecast_execution_state": item["forecast_execution_state"],
            "prediction_state": item["prediction_state"],
            "calibration_state": item["calibration_state"],
        }
    if view["forecast_baselines"]:
        item = view["forecast_baselines"][-1]
        baseline = item["baseline"]
        forecast_baseline = {
            "id": baseline["id"],
            "method_name": baseline["method"]["name"],
            "method_state": baseline["method"]["method_state"],
            "forecast_method_selection_state": baseline["forecast_method_selection_state"],
            "prediction_value": baseline["prediction"]["value"],
            "unit": baseline["prediction"]["unit"],
            "target_observation_type": baseline["prediction"]["target_observation_type"],
            "structured_field_path": deepcopy(baseline["prediction"]["structured_field_path"]),
            "forecast_origin": baseline["prediction"]["forecast_origin"],
            "horizon_end": baseline["prediction"]["horizon_end"],
            "prediction_state": baseline["prediction"]["prediction_state"],
            "input_state": baseline["input_boundary"]["input_state"],
            "selected_input_observation_ids": deepcopy(
                baseline["input_boundary"]["selected_input_observation_ids"]
            ),
            "calibration_state": baseline["calibration_state"],
            "empirical_validity_state": baseline["empirical_validity_state"],
            "residual_scoring_state": baseline["residual_scoring_state"],
            "validity_update_state": baseline["validity_update_state"],
            "weighting_update_state": baseline["weighting_update_state"],
            "learning_state": baseline["learning_state"],
            "network_access": baseline["execution_receipt"]["network_access"],
            "recorded_at": baseline["recorded_at"],
        }

    readback_selection = None
    if view["readback_selection_plans"]:
        item = view["readback_selection_plans"][-1]
        plan = item["plan"]
        run = item["run"]
        readback_selection = {
            "plan_id": plan["id"],
            "name": plan["name"],
            "target_observation_type": plan["target"]["observation_type"],
            "structured_field_path": deepcopy(plan["target"]["structured_field_path"]),
            "unit": plan["target"]["unit"],
            "unit_match_state": plan["target"]["unit_match_state"],
            "horizon_end": plan["timing"]["horizon_end"],
            "observed_window_end": plan["timing"]["observed_window_end"],
            "ledger_admission_cutoff": plan["timing"]["ledger_admission_cutoff"],
            "eligible_observer_frames": [
                {"id": frame["id"], "name": frame["name"]}
                for frame in item["eligible_observer_frames"]
            ],
            "cardinality": plan["selection_policy"]["cardinality"],
            "zero_candidate_policy": plan["selection_policy"]["zero_candidate_policy"],
            "multiple_candidate_policy": plan["selection_policy"]["multiple_candidate_policy"],
            "aggregation_policy": plan["selection_policy"]["aggregation_policy"],
            "ranking_policy": plan["selection_policy"]["ranking_policy"],
            "preregistration_state": plan["preregistration_state"],
            "execution_state": "COMPLETED" if run is not None else "NOT_STARTED",
            "selection_state": run["selection_state"] if run is not None else "NOT_EXECUTED",
            "candidate_count": run["candidate_count"] if run is not None else None,
            "candidate_observation_ids": (
                deepcopy(run["candidate_observation_ids"]) if run is not None else []
            ),
            "selected_observation_id": (
                run["selected_observation_id"] if run is not None else None
            ),
            "selected_target_value": run["selected_target_value"] if run is not None else None,
            "excluded_counts": (
                {
                    "after_admission_cutoff": len(
                        run["excluded_after_admission_cutoff_observation_ids"]
                    ),
                    "outside_observed_window": len(
                        run["excluded_outside_observed_window_observation_ids"]
                    ),
                    "observation_type_mismatch": len(
                        run["excluded_observation_type_mismatch_observation_ids"]
                    ),
                    "frame_mismatch": len(run["excluded_frame_mismatch_observation_ids"]),
                    "invalid_target": len(run["excluded_invalid_target_observation_ids"]),
                }
                if run is not None
                else None
            ),
            "aggregation_state": run["aggregation_state"] if run is not None else "NOT_PERFORMED",
            "ranking_state": run["ranking_state"] if run is not None else "NOT_PERFORMED",
            "residual_state": run["residual_state"] if run is not None else "NOT_COMPUTED",
            "residual_scoring_state": (
                run["residual_scoring_state"] if run is not None else "NOT_ENABLED"
            ),
            "calibration_state": (
                run["calibration_state"] if run is not None else "NOT_ESTABLISHED"
            ),
            "empirical_validity_state": (
                run["empirical_validity_state"] if run is not None else "NOT_ESTABLISHED"
            ),
            "validity_update_state": (
                run["validity_update_state"] if run is not None else "NOT_APPLIED"
            ),
            "weighting_update_state": (
                run["weighting_update_state"] if run is not None else "NOT_APPLIED"
            ),
            "future_admissibility_update_state": (
                run["future_admissibility_update_state"] if run is not None else "NOT_APPLIED"
            ),
            "learning_state": run["learning_state"] if run is not None else "NOT_STARTED",
            "network_access": (
                run["execution_receipt"]["network_access"] if run is not None else False
            ),
        }

    forecast_residual = None
    if view["forecast_residuals"]:
        item = view["forecast_residuals"][-1]
        result = item["forecast_residual"]
        forecast_residual = {
            "id": result["id"],
            "readback_selection_run_id": result["readback_selection_run_id"],
            "selected_observation_id": result["selected_observation_id"],
            "selected_observer_frame_name": item["selected_observer_frame"]["name"],
            "prediction_value": result["score"]["prediction_value"],
            "observed_value": result["score"]["observed_value"],
            "signed_residual": result["score"]["signed_residual"],
            "absolute_error": result["score"]["absolute_error"],
            "unit": result["score"]["unit"],
            "unit_match_state": result["score"]["unit_match_state"],
            "metric_name": result["metric"]["name"],
            "metric_state": result["metric"]["metric_state"],
            "residual_definition": result["metric"]["residual_definition"],
            "residual_state": result["residual_state"],
            "residual_scoring_state": result["residual_scoring_state"],
            "baseline_state": result["baseline_state"],
            "sample_count": result["sample_count"],
            "uncertainty_state": result["uncertainty_state"],
            "calibration_state": result["calibration_state"],
            "empirical_validity_state": result["empirical_validity_state"],
            "validity_update_state": result["validity_update_state"],
            "weighting_update_state": result["weighting_update_state"],
            "future_admissibility_update_state": result["future_admissibility_update_state"],
            "learning_state": result["learning_state"],
            "interpretation": result["interpretation"],
            "network_access": result["execution_receipt"]["network_access"],
            "recorded_at": result["recorded_at"],
        }

    forecast_validity_assessment = None
    if view["forecast_validity_assessments"]:
        item = view["forecast_validity_assessments"][-1]
        assessment = item["forecast_validity_assessment"]
        basis = assessment["assessment_basis"]
        forecast_validity_assessment = {
            "id": assessment["id"],
            "forecast_residual_id": assessment["forecast_residual_id"],
            "eligibility_state": assessment["eligibility_state"],
            "decision_state": assessment["decision_state"],
            "blockers": deepcopy(assessment["blockers"]),
            "target_fitter_id": assessment["target_fitter_id"],
            "target_fitter_state": assessment["target_fitter_state"],
            "residual_use_state": assessment["residual_use_state"],
            "forecast_method": basis["forecast_method"],
            "sample_count": basis["sample_count"],
            "unit_match_state": basis["unit_match_state"],
            "uncertainty_state": basis["uncertainty_state"],
            "validation_corpus_state": basis["validation_corpus_state"],
            "calibration_state": assessment["calibration_state"],
            "empirical_validity_state": assessment["empirical_validity_state"],
            "validity_update_state": assessment["validity_update_state"],
            "weighting_update_state": assessment["weighting_update_state"],
            "future_admissibility_update_state": assessment["future_admissibility_update_state"],
            "learning_state": assessment["learning_state"],
            "interpretation": assessment["interpretation"],
            "network_access": assessment["execution_receipt"]["network_access"],
            "recorded_at": assessment["recorded_at"],
        }

    forecast_fitter_specification = None
    if view["forecast_fitter_specifications"]:
        item = view["forecast_fitter_specifications"][-1]
        specification = item["specification"]
        training = specification["training_contract"]
        output = specification["output_contract"]
        applicability = specification["applicability"]
        forecast_fitter_specification = {
            "id": specification["id"],
            "name": specification["name"],
            "model_family": specification["model_family"],
            "registration_state": specification["registration_state"],
            "capability_state": specification["capability_state"],
            "target_observation_type": specification["target_contract"]["observation_type"],
            "target_structured_field_path": deepcopy(
                specification["target_contract"]["structured_field_path"]
            ),
            "target_unit": specification["target_contract"]["unit"],
            "feature_contracts": deepcopy(specification["feature_contracts"]),
            "objective": training["objective"],
            "training_data_state": training["training_data_state"],
            "training_state": training["training_state"],
            "temporal_split_state": training["temporal_split_state"],
            "negative_controls_state": training["negative_controls_state"],
            "implementation_state": specification["implementation_state"],
            "selection_state": specification["selection_state"],
            "execution_state": specification["execution_state"],
            "prediction_state": specification["prediction_state"],
            "uncertainty_state": output["uncertainty_state"],
            "validation_corpus_state": specification["validation_corpus_state"],
            "calibration_state": specification["calibration_state"],
            "empirical_validity_state": specification["empirical_validity_state"],
            "temporal_scope": applicability["temporal_scope"],
            "retroactive_application_state": applicability["retroactive_application_state"],
            "prior_assessment_effect": applicability["prior_assessment_effect"],
            "earlier_validity_assessment_ids": deepcopy(item["earlier_validity_assessment_ids"]),
            "network_access": specification["network_access"],
            "registered_at": specification["registered_at"],
        }

    residual_readback = None
    if view["residual_readbacks"]:
        item = view["residual_readbacks"][-1]
        readback = item["readback"]
        residual_readback = {
            "id": readback["id"],
            "scenario_run_id": readback["scenario_run_id"],
            "scenario_name": item["scenario"]["name"],
            "scenario_start_time": item["scenario"]["start_time"],
            "scenario_horizon_days": item["scenario"]["horizon_days"],
            "observation_count": len(item["observations"]),
            "latest_observed_at": max(
                observation["observed_at"] for observation in item["observations"]
            ),
            "observation_types": sorted(
                {observation["observation_type"] for observation in item["observations"]}
            ),
            "temporal_order_state": readback["temporal_order_state"],
            "baseline_eligibility_state": readback["baseline_eligibility_state"],
            "reference_prediction_state": readback["reference_prediction_state"],
            "forecast_baseline_state": item["forecast_baseline_state"],
            "residual_state": item["residual_state"],
            "validity_update_state": item["validity_update_state"],
            "weighting_update_state": item["weighting_update_state"],
            "future_admissibility_update_state": item["future_admissibility_update_state"],
            "learning_state": item["learning_state"],
            "interpretation": readback["interpretation"],
            "network_access": readback["execution_receipt"]["network_access"],
        }

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
        "governance": {
            "state": (
                "REAL_ASSET_CASE_BINDING_DECLARED"
                if real_asset_case_binding is not None
                else (
                    "ASSET_CATALOG_BINDING_DECLARED"
                    if asset_catalog_binding is not None
                    else "LEGACY_UNGOVERNED"
                )
            ),
            "asset_catalog_binding": deepcopy(asset_catalog_binding),
            "connector_intent": deepcopy(connector_intent),
            "connector_grant": deepcopy(latest_connector_grant),
            "source_exports": _source_export_summaries(view["observations"]),
            "source_setup": (
                {
                    "asset_class": asset_catalog_binding["asset_class"],
                    "platform": asset_catalog_binding["platform"],
                    "account_identifier": asset_catalog_binding["account_identifier"],
                    "source_uri": asset_catalog_binding["source_uri"],
                    "authorization_basis": asset_catalog_binding["authorization_basis"],
                    "collection_mode": asset_catalog_binding["collection_mode"],
                    "connector_kind": connector_intent["connector_kind"],
                    "connection_state": connector_intent["connection_state"],
                    "credential_state": connector_intent["credential_state"],
                    "oauth_state": connector_intent["oauth_state"],
                    "terms_review_state": connector_intent["terms_review_state"],
                    "live_collection_state": connector_intent["live_collection_state"],
                    "network_access": asset_catalog_binding["authority"]["network_access"],
                    "external_action_state": connector_intent["external_action_state"],
                    "source_digest_sha256": asset_catalog_binding["source_digest_sha256"],
                    "owner_attestation": asset_catalog_binding["ownership_attestation"],
                    "people_targeting": asset_catalog_binding["authority"]["people_targeting"],
                    "connector_grant_state": (
                        latest_connector_grant["grant_state"]
                        if latest_connector_grant is not None
                        else "NOT_RECORDED"
                    ),
                    "connector_grant_id": (
                        latest_connector_grant["grant_id"]
                        if latest_connector_grant is not None
                        else None
                    ),
                    "connector_grant_access_mode": (
                        latest_connector_grant["access_mode"]
                        if latest_connector_grant is not None
                        else None
                    ),
                }
                if asset_catalog_binding is not None and connector_intent is not None
                else None
            ),
            "real_asset_case_binding": deepcopy(real_asset_case_binding),
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
            "discrimination_plans": len(view["discrimination_plans"]),
            "forecast_evaluation_designs": len(view["forecast_evaluation_designs"]),
            "forecast_baselines": len(view["forecast_baselines"]),
            "readback_selection_plans": len(view["readback_selection_plans"]),
            "readback_selection_runs": sum(
                item["run"] is not None for item in view["readback_selection_plans"]
            ),
            "forecast_residuals": len(view["forecast_residuals"]),
            "forecast_validity_assessments": len(view["forecast_validity_assessments"]),
            "forecast_fitter_specifications": len(view["forecast_fitter_specifications"]),
            "residual_readbacks": len(view["residual_readbacks"]),
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
            "observations": [
                _observation_workbench(observation) for observation in view["observations"]
            ],
            "manifests": [
                {
                    "id": item["id"],
                    "source_label": item["source"]["label"],
                    "source_uri": item["source"]["uri"],
                    "access_policy": item["access_policy"],
                    "sha256": item["sha256"],
                    "media_type": item["media_type"],
                    "size": item["size"],
                    "acquired_at": item["acquired_at"],
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
        "collection": {"latest_discrimination": discrimination},
        "forecasting": {
            "latest_evaluation_design": forecast_design,
            "latest_baseline": forecast_baseline,
            "latest_fitter_specification": forecast_fitter_specification,
        },
        "readback": {
            "latest": residual_readback,
            "latest_selection": readback_selection,
            "latest_forecast_residual": forecast_residual,
            "latest_validity_assessment": forecast_validity_assessment,
        },
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
    recorded_source_observations = [
        observation
        for observation in projection.observations.values()
        if observation["provenance"]["adapter"] == "github-public-rest"
    ]
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
        "asset_catalog": _asset_catalog_workbench_summary(catalog),
        "case": None,
        "epistemic_limits": {
            "coverage_state": "NOT_ESTABLISHED",
            "completeness_claim": "NOT_MADE",
            "probability_state": "NOT_COMPUTED",
            "prediction_state": (
                "PRODUCED_UNCALIBRATED_BASELINE"
                if projection.forecast_baselines
                else "NOT_REQUESTED"
            ),
            "trajectory_state": "NOT_SIMULATED",
            "empirical_validity_state": "NOT_ESTABLISHED",
            "consensus_state": "NOT_COMPUTED",
            "collection_state": (
                "RECORDED_USER_INVOKED_ONE_SHOT" if recorded_source_observations else "NOT_STARTED"
            ),
            "acquisition_state": (
                "PUBLIC_SOURCE_ARTIFACT_ADMISSION_RECORDED"
                if recorded_source_observations
                else "NOT_ATTEMPTED"
            ),
            "source_independence_state": "NOT_ESTABLISHED",
            "residual_state": (
                "COMPUTED_DESCRIPTIVE_REFERENCE_ONLY"
                if projection.forecast_residuals
                else "NOT_COMPUTED"
            ),
            "validity_update_state": "NOT_APPLIED",
            "learning_state": "NOT_STARTED",
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

    path = Path(ledger_path)
    events = EventLedger(path).read_events()
    policy_path = path.parent / "policy.json"
    policy_present = policy_path.exists() or policy_path.is_symlink()
    if policy_present and path.name != "events.jsonl":
        raise WorkbenchError("policy-bound case must use its canonical events.jsonl ledger")
    projection = EventLedger(path).projection()
    has_case_binding = any(
        "real_asset_case_binding" in entity.get("attributes", {})
        for entity in projection.entities.values()
    )
    if has_case_binding and not policy_present:
        raise WorkbenchError("policy-bound case ledger is missing its required policy.json")
    network_attempt = None
    case_policy = None
    case_policy_digest = None
    if policy_present or has_case_binding:
        from readin.real_asset_cases import (  # Local import avoids a module cycle.
            RealAssetCaseError,
            load_real_asset_case_policy,
            validate_real_asset_case_read_access,
        )

        try:
            _, case_policy, case_policy_digest = load_real_asset_case_policy(path.parent)
            network_attempt = validate_real_asset_case_read_access(path.parent)
        except RealAssetCaseError as error:
            raise WorkbenchError(str(error)) from error
    snapshot = build_workbench_snapshot(projection, asset_id)
    if case_policy is not None and case_policy_digest is not None:
        snapshot["case"] = _real_asset_case_workbench(
            case_policy,
            case_policy_digest,
            projection,
            network_attempt,
            case_path=path.parent,
            ledger_path=path,
            events=events,
        )
    limits = snapshot["epistemic_limits"]
    if network_attempt is not None and limits["acquisition_state"] == "NOT_ATTEMPTED":
        limits["collection_state"] = "NETWORK_ATTEMPT_RESERVED_NO_ADMISSION"
        limits["acquisition_state"] = "NO_ARTIFACT_ADMITTED"
    return snapshot


def validate_loopback_host(host: str) -> None:
    """Require a numeric loopback bind address without resolver dependence."""

    if host not in LOOPBACK_BIND_HOSTS:
        raise WorkbenchError(
            "workbench bind host must be a numeric loopback address "
            f"({', '.join(sorted(LOOPBACK_BIND_HOSTS))}): {host}"
        )


class WorkbenchHTTPServer(ThreadingHTTPServer):
    """HTTP server carrying only an immutable local-ledger path."""

    def __init__(self, address: tuple[str, int], ledger_path: Path) -> None:
        self.ledger_path = ledger_path
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, WorkbenchRequestHandler)
        try:
            bound_address = ipaddress.ip_address(self.server_address[0])
        except ValueError as error:
            self.server_close()
            raise WorkbenchError("workbench listener did not bind a numeric IP address") from error
        if not bound_address.is_loopback:
            self.server_close()
            raise WorkbenchError("workbench listener did not bind a loopback address")


class WorkbenchRequestHandler(BaseHTTPRequestHandler):
    """Serve the static interface and a single read-only JSON endpoint."""

    server: WorkbenchHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        if not self._request_authority_is_trusted():
            return
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
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/launch-guard.js": ("launch-guard.js", "text/javascript; charset=utf-8"),
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
        if not self._request_authority_is_trusted():
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._security_headers()
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if not self._request_authority_is_trusted():
            return
        self._method_not_allowed()

    def do_PUT(self) -> None:  # noqa: N802
        if not self._request_authority_is_trusted():
            return
        self._method_not_allowed()

    def do_PATCH(self) -> None:  # noqa: N802
        if not self._request_authority_is_trusted():
            return
        self._method_not_allowed()

    def do_DELETE(self) -> None:  # noqa: N802
        if not self._request_authority_is_trusted():
            return
        self._method_not_allowed()

    def _request_authority_is_trusted(self) -> bool:
        host_values = self.headers.get_all("Host", [])
        origin_values = self.headers.get_all("Origin", [])
        try:
            if len(host_values) != 1:
                raise _RequestAuthorityError(
                    "exactly one Host header is required", HTTPStatus.BAD_REQUEST
                )
            _parse_loopback_authority(
                host_values[0],
                server_port=self.server.server_port,
                default_port=80,
                field_name="Host",
            )
            if len(origin_values) > 1:
                raise _RequestAuthorityError(
                    "at most one Origin header is permitted", HTTPStatus.FORBIDDEN
                )
            if origin_values:
                _validate_origin(origin_values[0], server_port=self.server.server_port)
        except _RequestAuthorityError as error:
            self._send_json(
                {
                    "error": str(error),
                    "authority_state": "NO_AUTHORITY",
                },
                error.status,
                include_body=self.command != "HEAD",
            )
            return False
        return True

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
        include_body: bool = True,
    ) -> None:
        body = json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
        self._send_bytes(
            body,
            "application/json; charset=utf-8",
            status,
            extra_headers,
            include_body=include_body,
        )

    def _send_bytes(
        self,
        body: bytes,
        media_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        extra_headers: dict[str, str] | None = None,
        *,
        include_body: bool = True,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if include_body:
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
    build_ledger_workbench_snapshot(path)
    return WorkbenchHTTPServer((host, port), path)


def serve_workbench(
    ledger_path: str | Path,
    *,
    host: str = "127.0.0.1",
    port: int = 4173,
    open_browser: bool = False,
) -> None:
    """Serve the workbench until interrupted."""

    server = create_workbench_server(ledger_path, host=host, port=port)
    display_host = f"[{host}]" if ":" in host else host
    url = f"http://{display_host}:{server.server_port}"
    try:
        print(f"READIN workbench · NO_AUTHORITY · {url}", flush=True)
        if open_browser:
            try:
                opened = webbrowser.open(url, new=2)
            except webbrowser.Error as error:
                print(f"Browser launch failed ({error}). Open {url} manually.", flush=True)
            else:
                if not opened:
                    print(f"Browser did not open automatically. Open {url} manually.", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
