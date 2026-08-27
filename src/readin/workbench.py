"""Read-only workbench through bounded Phase 8G fitter specification registration."""

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
            "prediction_state": (
                "PRODUCED_UNCALIBRATED_BASELINE"
                if projection.forecast_baselines
                else "NOT_REQUESTED"
            ),
            "trajectory_state": "NOT_SIMULATED",
            "empirical_validity_state": "NOT_ESTABLISHED",
            "consensus_state": "NOT_COMPUTED",
            "collection_state": "NOT_STARTED",
            "acquisition_state": "NOT_ATTEMPTED",
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
