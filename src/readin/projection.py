"""Fail-closed deterministic replay for the READIN Phase 0 through Phase 8G ledger."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any

from readin.belief import (
    BELIEF_ALGORITHM_ID,
    BeliefRuntimeError,
    belief_implementation_sha256,
    build_belief_snapshot,
    compute_belief_components,
)
from readin.contracts import validate_event
from readin.discrimination import (
    DISCRIMINATION_ALGORITHM_ID,
    DiscriminationRuntimeError,
    build_discrimination_snapshot,
    compute_discrimination_components,
    discrimination_implementation_sha256,
)
from readin.fitters import (
    FitterRuntimeError,
    canonical_sha256,
    evaluate_reference_admissibility,
    reference_fit_components,
    reference_fitter_spec,
    validate_reference_descriptor,
)
from readin.forecast_residuals import (
    FORECAST_RESIDUAL_ALGORITHM_ID,
    ForecastResidualError,
    build_forecast_residual_snapshot,
    compute_forecast_residual_components,
    forecast_residual_implementation_sha256,
)
from readin.forecast_validity import (
    FORECAST_VALIDITY_ALGORITHM_ID,
    ForecastValidityError,
    build_forecast_validity_snapshot,
    compute_forecast_validity_components,
    forecast_validity_implementation_sha256,
)
from readin.forecasting import (
    FORECAST_BASELINE_ALGORITHM_ID,
    ForecastBaselineError,
    build_forecast_baseline_snapshot,
    compute_forecast_baseline_components,
    forecast_baseline_implementation_sha256,
)
from readin.readback_selection import (
    READBACK_SELECTION_ALGORITHM_ID,
    ReadbackSelectionError,
    build_readback_selection_snapshot,
    compute_readback_selection_components,
    readback_selection_implementation_sha256,
)
from readin.residuals import (
    RESIDUAL_ALGORITHM_ID,
    ResidualRuntimeError,
    build_residual_snapshot,
    compute_residual_components,
    residual_implementation_sha256,
)
from readin.scenarios import (
    SCENARIO_ALGORITHM_ID,
    ScenarioRuntimeError,
    build_scenario_snapshot,
    compute_scenario_components,
    scenario_implementation_sha256,
)


class ProjectionError(ValueError):
    """Raised when a valid event violates ledger semantics."""


class ReadinProjection:
    """In-memory projection of the READIN ledger and its inspectable state history."""

    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}
        self.assets: dict[str, dict[str, Any]] = {}
        self.frames: dict[str, dict[str, Any]] = {}
        self.evidence: dict[str, dict[str, Any]] = {}
        self.observations: dict[str, dict[str, Any]] = {}
        self.dependencies: dict[str, dict[str, Any]] = {}
        self.claims: dict[str, dict[str, Any]] = {}
        self.evidence_links: dict[str, dict[str, Any]] = {}
        self.relations: dict[str, dict[str, Any]] = {}
        self.resolution_candidates: dict[str, dict[str, Any]] = {}
        self.resolution_assessments: dict[str, dict[str, Any]] = {}
        self.cartographic_surfaces: dict[str, dict[str, Any]] = {}
        self.cartographic_query_plans: dict[str, dict[str, Any]] = {}
        self.fitters: dict[str, dict[str, Any]] = {}
        self.fitter_runs: dict[str, dict[str, Any]] = {}
        self.fit_results: dict[str, dict[str, Any]] = {}
        self.fitter_receipts: dict[str, dict[str, Any]] = {}
        self.hypotheses: dict[str, dict[str, Any]] = {}
        self.belief_edges: dict[str, dict[str, Any]] = {}
        self.belief_revisions: dict[str, dict[str, Any]] = {}
        self.belief_receipts: dict[str, dict[str, Any]] = {}
        self.scenarios: dict[str, dict[str, Any]] = {}
        self.scenario_runs: dict[str, dict[str, Any]] = {}
        self.scenario_receipts: dict[str, dict[str, Any]] = {}
        self.discrimination_plans: dict[str, dict[str, Any]] = {}
        self.discrimination_runs: dict[str, dict[str, Any]] = {}
        self.discrimination_receipts: dict[str, dict[str, Any]] = {}
        self.forecast_evaluation_designs: dict[str, dict[str, Any]] = {}
        self.forecast_baselines: dict[str, dict[str, Any]] = {}
        self.forecast_baseline_receipts: dict[str, dict[str, Any]] = {}
        self.readback_selection_plans: dict[str, dict[str, Any]] = {}
        self.readback_selection_runs: dict[str, dict[str, Any]] = {}
        self.readback_selection_receipts: dict[str, dict[str, Any]] = {}
        self.forecast_residuals: dict[str, dict[str, Any]] = {}
        self.forecast_residual_receipts: dict[str, dict[str, Any]] = {}
        self.forecast_validity_assessments: dict[str, dict[str, Any]] = {}
        self.forecast_validity_receipts: dict[str, dict[str, Any]] = {}
        self.forecast_fitter_specifications: dict[str, dict[str, Any]] = {}
        self.residual_readbacks: dict[str, dict[str, Any]] = {}
        self.residual_receipts: dict[str, dict[str, Any]] = {}
        self.asset_versions: dict[str, list[dict[str, Any]]] = {}
        self.event_ids: set[str] = set()
        self._evidence_digests: dict[str, str] = {}
        self._observation_recorded_at: dict[str, str] = {}
        self._dependency_groups: dict[str, set[str]] = {}
        self._dependency_graph: dict[str, set[str]] = {}
        self._candidate_pairs: dict[tuple[str, str], str] = {}
        self._latest_resolution_assessment: dict[str, str] = {}
        self._cartographic_surface_recorded_at: dict[str, str] = {}
        self._cartographic_query_recorded_at: dict[str, str] = {}
        self._fitter_recorded_at: dict[str, str] = {}
        self._fitter_run_groups: dict[str, dict[str, Any]] = {}
        self._fitter_run_pairs: set[tuple[str, str]] = set()
        self._belief_graph: dict[str, set[str]] = {}
        self._belief_edge_pairs: set[tuple[str, str]] = set()
        self._latest_belief_revision: dict[str, str] = {}
        self._latest_scenario_run: dict[str, str] = {}
        self._latest_discrimination_run: dict[str, str] = {}
        self._scenario_forecast_evaluation_design: dict[str, str] = {}
        self._design_forecast_baseline: dict[str, str] = {}
        self._baseline_readback_selection_plan: dict[str, str] = {}
        self._plan_readback_selection_run: dict[str, str] = {}
        self._selection_run_forecast_residual: dict[str, str] = {}
        self._residual_forecast_validity_assessment: dict[str, str] = {}
        self._scenario_readback: dict[str, str] = {}
        self._events: list[dict[str, Any]] = []

    @classmethod
    def replay(cls, events: list[dict[str, Any]]) -> ReadinProjection:
        projection = cls()
        for event in events:
            projection.apply(event)
        return projection

    def apply(self, event: dict[str, Any]) -> None:
        validate_event(event)
        event_id = event["event_id"]
        if event_id in self.event_ids:
            raise ProjectionError(f"duplicate event id: {event_id}")
        if self._events and self._parse_timestamp(event["occurred_at"]) < self._parse_timestamp(
            self._events[-1]["occurred_at"]
        ):
            raise ProjectionError("event occurred_at precedes the prior ledger event")

        handler_name = event["event_type"].replace(".", "_")
        handler = getattr(self, f"_apply_{handler_name}", None)
        if handler is None:
            raise ProjectionError(f"unsupported event type: {event['event_type']}")
        handler(event)
        self.event_ids.add(event_id)
        self._events.append(deepcopy(event))

    def _apply_entity_created(self, event: dict[str, Any]) -> None:
        entity = deepcopy(event["payload"]["entity"])
        entity_id = entity["id"]
        if entity_id in self.entities:
            raise ProjectionError(f"duplicate entity id: {entity_id}")
        self.entities[entity_id] = entity

    def _apply_asset_tracking_started(self, event: dict[str, Any]) -> None:
        asset = deepcopy(event["payload"]["tracked_asset"])
        entity_id = asset["entity_id"]
        if entity_id not in self.entities:
            raise ProjectionError(f"tracking references unknown entity: {entity_id}")
        if entity_id in self.assets:
            raise ProjectionError(f"entity is already tracked: {entity_id}")
        self.assets[entity_id] = asset
        self.asset_versions[entity_id] = []
        self._advance_asset(entity_id, event)

    def _apply_observer_frame_registered(self, event: dict[str, Any]) -> None:
        frame = deepcopy(event["payload"]["observer_frame"])
        frame_id = frame["id"]
        if frame_id in self.frames:
            raise ProjectionError(f"duplicate observer frame id: {frame_id}")
        self.frames[frame_id] = frame

    def _apply_evidence_manifested(self, event: dict[str, Any]) -> None:
        manifest = deepcopy(event["payload"]["evidence_manifest"])
        artifact_id = manifest["id"]
        digest = manifest["sha256"]
        if artifact_id in self.evidence:
            raise ProjectionError(f"duplicate evidence artifact id: {artifact_id}")
        if digest in self._evidence_digests:
            existing = self._evidence_digests[digest]
            raise ProjectionError(f"evidence digest already manifested as {existing}: {digest}")

        referenced = set(manifest["derivative_refs"])
        for transformation in manifest["transformations"]:
            referenced.update(transformation["input_artifact_ids"])
        missing = sorted(referenced - self.evidence.keys())
        if missing:
            raise ProjectionError(f"evidence manifest references unknown artifacts: {missing}")

        self.evidence[artifact_id] = manifest
        self._evidence_digests[digest] = artifact_id

    def _apply_observation_admitted(self, event: dict[str, Any]) -> None:
        observation = deepcopy(event["payload"]["observation"])
        observation_id = observation["id"]
        if observation_id in self.observations:
            raise ProjectionError(f"duplicate observation id: {observation_id}")

        unknown_subjects = sorted(set(observation["subject_entities"]) - self.assets.keys())
        if unknown_subjects:
            raise ProjectionError(f"observation references untracked entities: {unknown_subjects}")

        frame_id = observation["observer_frame_id"]
        if frame_id not in self.frames:
            raise ProjectionError(f"observation references unknown frame: {frame_id}")

        artifact_id = observation["source_artifact_id"]
        if artifact_id not in self.evidence:
            raise ProjectionError(f"observation references unknown evidence: {artifact_id}")
        self._validate_observation_dependency_groups(observation)

        superseded_id = observation["supersedes_observation_id"]
        if superseded_id is not None:
            if superseded_id not in self.observations:
                raise ProjectionError(
                    f"observation supersedes unknown observation: {superseded_id}"
                )
            prior_subjects = set(self.observations[superseded_id]["subject_entities"])
            if not prior_subjects.intersection(observation["subject_entities"]):
                raise ProjectionError("superseding observation does not share a subject")

        self._validate_temporal_scope(observation)
        self._validate_source_alignment(observation)

        self.observations[observation_id] = observation
        self._observation_recorded_at[observation_id] = event["occurred_at"]
        for entity_id in observation["subject_entities"]:
            self._advance_asset(entity_id, event)

    def _apply_evidence_dependency_declared(self, event: dict[str, Any]) -> None:
        dependency = deepcopy(event["payload"]["dependency"])
        dependency_id = dependency["id"]
        if dependency_id in self.dependencies:
            raise ProjectionError(f"duplicate evidence dependency id: {dependency_id}")

        ancestor_id = dependency["ancestor_evidence_id"]
        descendant_id = dependency["descendant_evidence_id"]
        missing = sorted({ancestor_id, descendant_id} - self.evidence.keys())
        if missing:
            raise ProjectionError(f"dependency references unknown evidence: {missing}")
        if ancestor_id == descendant_id:
            raise ProjectionError("evidence dependency cannot be self-referential")
        if descendant_id in self._dependency_graph.get(ancestor_id, set()):
            raise ProjectionError("duplicate evidence dependency edge")
        if self._dependency_path_exists(descendant_id, ancestor_id):
            raise ProjectionError("evidence dependency would create a cycle")

        if dependency["verification_status"] == "VERIFIED_FROM_MANIFEST":
            if dependency["relationship"] not in {
                "DERIVED_FROM",
                "SUMMARIZES",
                "REPRODUCES",
                "TRANSFORMS",
            }:
                raise ProjectionError(
                    "manifest verification is incompatible with the dependency relationship"
                )
            inputs = {
                input_id
                for transformation in self.evidence[descendant_id]["transformations"]
                for input_id in transformation["input_artifact_ids"]
            }
            if ancestor_id not in inputs:
                raise ProjectionError("verified dependency is not bound by the descendant manifest")
            if dependency["basis"]["method"] != "MANIFEST_TRANSFORMATION":
                raise ProjectionError("verified dependency requires MANIFEST_TRANSFORMATION basis")
        elif dependency["basis"]["method"] == "MANIFEST_TRANSFORMATION":
            raise ProjectionError(
                "MANIFEST_TRANSFORMATION basis requires VERIFIED_FROM_MANIFEST status"
            )

        self.dependencies[dependency_id] = dependency
        self._dependency_graph.setdefault(ancestor_id, set()).add(descendant_id)
        group_id = dependency["dependency_group_id"]
        self._dependency_groups.setdefault(group_id, set()).update({ancestor_id, descendant_id})
        for entity_id in self._assets_for_evidence({ancestor_id, descendant_id}):
            self._advance_asset(entity_id, event)

    def _apply_claim_created(self, event: dict[str, Any]) -> None:
        claim = deepcopy(event["payload"]["claim"])
        claim_id = claim["id"]
        if claim_id in self.claims:
            raise ProjectionError(f"duplicate claim id: {claim_id}")

        subject = claim["subject"]
        if subject not in self.assets:
            raise ProjectionError(f"claim references untracked subject: {subject}")
        if claim["object"]["kind"] == "ENTITY":
            object_entity = claim["object"]["entity_id"]
            if object_entity not in self.entities:
                raise ProjectionError(f"claim references unknown object entity: {object_entity}")

        missing_observations = sorted(set(claim["derived_from"]) - self.observations.keys())
        if missing_observations:
            raise ProjectionError(f"claim references unknown observations: {missing_observations}")
        if not any(
            subject in self.observations[observation_id]["subject_entities"]
            for observation_id in claim["derived_from"]
        ):
            raise ProjectionError("claim derivation has no observation of its subject")
        self._validate_interval(claim["temporal_scope"], "claim temporal_scope")

        self.claims[claim_id] = claim
        self._advance_asset(subject, event)

    def _apply_evidence_linked(self, event: dict[str, Any]) -> None:
        link = deepcopy(event["payload"]["evidence_link"])
        link_id = link["id"]
        if link_id in self.evidence_links:
            raise ProjectionError(f"duplicate evidence link id: {link_id}")
        if link["evidence_id"] not in self.evidence:
            raise ProjectionError(
                f"evidence link references unknown evidence: {link['evidence_id']}"
            )
        if link["claim_id"] not in self.claims:
            raise ProjectionError(f"evidence link references unknown claim: {link['claim_id']}")
        if any(
            existing["evidence_id"] == link["evidence_id"]
            and existing["claim_id"] == link["claim_id"]
            and existing["role"] == link["role"]
            for existing in self.evidence_links.values()
        ):
            raise ProjectionError("duplicate evidence/claim/role link")

        group_id = link["dependency_group"]
        if group_id is not None:
            if group_id not in self._dependency_groups:
                raise ProjectionError(
                    f"evidence link references unknown dependency group: {group_id}"
                )
            if link["evidence_id"] not in self._dependency_groups[group_id]:
                raise ProjectionError("linked evidence is not a member of its dependency group")

        if link["role"] == "derives":
            claim = self.claims[link["claim_id"]]
            derived_artifacts = {
                self.observations[observation_id]["source_artifact_id"]
                for observation_id in claim["derived_from"]
            }
            if link["evidence_id"] not in derived_artifacts:
                raise ProjectionError(
                    "derives link evidence is not an artifact of a claim derivation observation"
                )

        self._validate_evidence_link_axes(link)
        self.evidence_links[link_id] = link
        self._advance_asset(self.claims[link["claim_id"]]["subject"], event)

    def _apply_relation_created(self, event: dict[str, Any]) -> None:
        relation = deepcopy(event["payload"]["relation"])
        relation_id = relation["id"]
        if relation_id in self.relations:
            raise ProjectionError(f"duplicate relation id: {relation_id}")
        source = relation["source_entity"]
        target = relation["target_entity"]
        missing_entities = sorted({source, target} - self.entities.keys())
        if missing_entities:
            raise ProjectionError(f"relation references unknown entities: {missing_entities}")
        if source == target:
            raise ProjectionError("relation source and target must differ")

        missing_claims = sorted(set(relation["claims"]) - self.claims.keys())
        if missing_claims:
            raise ProjectionError(f"relation references unknown claims: {missing_claims}")
        unconnected_claims = sorted(
            item
            for item in relation["claims"]
            if not self._claim_connects_entities(self.claims[item], source, target)
        )
        if unconnected_claims:
            raise ProjectionError(
                f"relation cites claims that do not connect its source and target: "
                f"{unconnected_claims}"
            )
        self._validate_interval(relation, "relation validity")

        relation_type = relation["relation_type"]
        semantics = relation["relation_semantics"]
        if relation_type == "CAUSES":
            raise ProjectionError("causal relations must remain explicitly provisional as CAUSES?")
        if (relation_type == "CAUSES?") != (semantics == "CAUSAL_HYPOTHESIS"):
            raise ProjectionError("CAUSES? and CAUSAL_HYPOTHESIS must be declared together")

        self.relations[relation_id] = relation
        for entity_id in {source, target}.intersection(self.assets):
            self._advance_asset(entity_id, event)

    def _apply_entity_resolution_candidate_recorded(self, event: dict[str, Any]) -> None:
        candidate = deepcopy(event["payload"]["resolution_candidate"])
        candidate_id = candidate["id"]
        if candidate_id in self.resolution_candidates:
            raise ProjectionError(f"duplicate resolution candidate id: {candidate_id}")

        left_entity_id = candidate["left_entity_id"]
        right_entity_id = candidate["right_entity_id"]
        missing_entities = sorted({left_entity_id, right_entity_id} - self.entities.keys())
        if missing_entities:
            raise ProjectionError(
                f"resolution candidate references unknown entities: {missing_entities}"
            )
        if left_entity_id == right_entity_id:
            raise ProjectionError("resolution candidate entities must differ")
        if not {left_entity_id, right_entity_id}.intersection(self.assets):
            raise ProjectionError("resolution candidate must involve at least one tracked entity")

        pair = tuple(sorted((left_entity_id, right_entity_id)))
        if pair in self._candidate_pairs:
            raise ProjectionError(
                f"resolution candidate already exists for entity pair: "
                f"{self._candidate_pairs[pair]}"
            )

        for signal in candidate["signals"]:
            self._validate_resolution_signal(signal, {left_entity_id, right_entity_id})

        self.resolution_candidates[candidate_id] = candidate
        self._candidate_pairs[pair] = candidate_id
        for entity_id in {left_entity_id, right_entity_id}.intersection(self.assets):
            self._advance_asset(entity_id, event)

    def _apply_entity_resolution_candidate_assessed(self, event: dict[str, Any]) -> None:
        assessment = deepcopy(event["payload"]["resolution_assessment"])
        assessment_id = assessment["id"]
        if assessment_id in self.resolution_assessments:
            raise ProjectionError(f"duplicate resolution assessment id: {assessment_id}")

        candidate_id = assessment["candidate_id"]
        if candidate_id not in self.resolution_candidates:
            raise ProjectionError(
                f"resolution assessment references unknown candidate: {candidate_id}"
            )

        current_assessment_id = self._latest_resolution_assessment.get(candidate_id)
        supersedes_id = assessment["supersedes_assessment_id"]
        if current_assessment_id is None and supersedes_id is not None:
            raise ProjectionError("first resolution assessment cannot supersede another assessment")
        if current_assessment_id is not None and supersedes_id != current_assessment_id:
            raise ProjectionError(
                "resolution reassessment must supersede the candidate's latest assessment"
            )
        if current_assessment_id is not None:
            current_assessed_at = self.resolution_assessments[current_assessment_id]["assessed_at"]
            if self._parse_timestamp(assessment["assessed_at"]) < self._parse_timestamp(
                current_assessed_at
            ):
                raise ProjectionError(
                    "resolution reassessment assessed_at precedes the latest assessment"
                )

        self.resolution_assessments[assessment_id] = assessment
        self._latest_resolution_assessment[candidate_id] = assessment_id
        candidate = self.resolution_candidates[candidate_id]
        for entity_id in {
            candidate["left_entity_id"],
            candidate["right_entity_id"],
        }.intersection(self.assets):
            self._advance_asset(entity_id, event)

    def _apply_cartography_surface_registered(self, event: dict[str, Any]) -> None:
        surface = deepcopy(event["payload"]["cartographic_surface"])
        surface_id = surface["id"]
        if surface_id in self.cartographic_surfaces:
            raise ProjectionError(f"duplicate cartographic surface id: {surface_id}")

        unknown_frames = sorted(set(surface["observer_frame_ids"]) - self.frames.keys())
        if unknown_frames:
            raise ProjectionError(
                f"cartographic surface references unknown observer frames: {unknown_frames}"
            )
        if surface["blind_region_state"] == "DECLARED" and not surface["blind_regions"]:
            raise ProjectionError("DECLARED surface requires at least one blind region")
        if surface["blind_region_state"] == "NOT_CHARACTERIZED" and surface["blind_regions"]:
            raise ProjectionError("NOT_CHARACTERIZED surface cannot declare blind regions")

        self.cartographic_surfaces[surface_id] = surface
        self._cartographic_surface_recorded_at[surface_id] = event["occurred_at"]

    def _apply_cartography_query_planned(self, event: dict[str, Any]) -> None:
        plan = deepcopy(event["payload"]["cartographic_query_plan"])
        query_id = plan["id"]
        if query_id in self.cartographic_query_plans:
            raise ProjectionError(f"duplicate cartographic query plan id: {query_id}")

        asset_id = plan["asset_entity_id"]
        if asset_id not in self.assets:
            raise ProjectionError(
                f"cartographic query references unknown tracked asset: {asset_id}"
            )
        unknown_surfaces = sorted(set(plan["surface_ids"]) - self.cartographic_surfaces.keys())
        if unknown_surfaces:
            raise ProjectionError(
                f"cartographic query references unknown surfaces: {unknown_surfaces}"
            )

        traversal = plan["traversal"]
        if traversal["include_relations"] and traversal["max_relation_hops"] == 0:
            raise ProjectionError("relation traversal requires at least one relation hop")
        if not traversal["include_relations"] and traversal["max_relation_hops"] != 0:
            raise ProjectionError("disabled relation traversal requires zero relation hops")

        reconstruction = plan["reconstruction"]
        cutoff = reconstruction["epistemic_cutoff"]
        if reconstruction["mode"] == "AS_KNOWN_THEN" and cutoff is not None:
            tracked_at = self.asset_versions[asset_id][0]["recorded_at"]
            if self._parse_timestamp(cutoff) < self._parse_timestamp(tracked_at):
                raise ProjectionError("cartographic cutoff precedes asset tracking")

        self.cartographic_query_plans[query_id] = plan
        self._cartographic_query_recorded_at[query_id] = event["occurred_at"]
        self._advance_asset(asset_id, event)

    def _apply_fitter_registered(self, event: dict[str, Any]) -> None:
        descriptor = deepcopy(event["payload"]["fitter_descriptor"])
        fitter_id = descriptor["id"]
        if fitter_id in self.fitters:
            raise ProjectionError(f"duplicate fitter id: {fitter_id}")
        try:
            validate_reference_descriptor(descriptor)
        except FitterRuntimeError as error:
            raise ProjectionError(str(error)) from error

        self.fitters[fitter_id] = descriptor
        self._fitter_recorded_at[fitter_id] = event["occurred_at"]

    def _apply_fitter_run_completed(self, event: dict[str, Any]) -> None:
        run = deepcopy(event["payload"]["fitter_run"])
        run_id = run["id"]
        receipt = run["execution_receipt"]
        receipt_id = receipt["id"]
        if run_id in self.fitter_runs:
            raise ProjectionError(f"duplicate fitter run id: {run_id}")
        if receipt_id in self.fitter_receipts:
            raise ProjectionError(f"duplicate fitter receipt id: {receipt_id}")

        fitter_id = run["fitter_id"]
        if fitter_id not in self.fitters:
            raise ProjectionError(f"fitter run references unknown fitter: {fitter_id}")
        query_id = run["query_plan_id"]
        if query_id not in self.cartographic_query_plans:
            raise ProjectionError(f"fitter run references unknown query plan: {query_id}")
        if (run["run_group_id"], fitter_id) in self._fitter_run_pairs:
            raise ProjectionError("fitter already completed within this run group")

        descriptor = self.fitters[fitter_id]
        query_result = self.execute_cartographic_query(query_id)
        asset_id = query_result["query_plan"]["asset_entity_id"]
        expected_input_ids = self._fitter_input_ids(query_result)
        expected_excluded_ids = sorted(query_result["aperture"]["excluded_asset_observation_ids"])
        expected_input_sha256 = canonical_sha256(query_result)

        self._validate_fitter_receipt_identity(
            run,
            receipt,
            descriptor,
            event,
        )
        for key, expected in expected_input_ids.items():
            if receipt[key] != expected:
                raise ProjectionError(f"fitter receipt {key} does not match query input")
        if receipt["excluded_observation_ids"] != expected_excluded_ids:
            raise ProjectionError("fitter receipt exclusions do not match query aperture")
        if receipt["input_snapshot_sha256"] != expected_input_sha256:
            raise ProjectionError("fitter receipt input snapshot digest mismatch")
        requested_fitter_ids = receipt["requested_fitter_ids"]
        if requested_fitter_ids != sorted(requested_fitter_ids):
            raise ProjectionError("requested fitter ids must use deterministic sorted order")
        unknown_requested_fitters = sorted(set(requested_fitter_ids) - self.fitters.keys())
        if unknown_requested_fitters:
            raise ProjectionError(
                f"fitter receipt requests unknown fitters: {unknown_requested_fitters}"
            )
        if fitter_id not in requested_fitter_ids:
            raise ProjectionError("completed fitter is absent from the requested fitter set")

        group_id = run["run_group_id"]
        group = self._fitter_run_groups.get(group_id)
        new_group: dict[str, Any] | None = None
        if group is None:
            expected_state_version = self.assets[asset_id]["epistemic_state_version"]
            if receipt["asset_state_version"] != expected_state_version:
                raise ProjectionError("fitter receipt asset state version mismatch")
            new_group = {
                "query_plan_id": query_id,
                "asset_entity_id": asset_id,
                "asset_state_version": expected_state_version,
                "input_snapshot_sha256": expected_input_sha256,
                "requested_fitter_ids": requested_fitter_ids,
            }
        elif group != {
            "query_plan_id": query_id,
            "asset_entity_id": asset_id,
            "asset_state_version": receipt["asset_state_version"],
            "input_snapshot_sha256": expected_input_sha256,
            "requested_fitter_ids": requested_fitter_ids,
        }:
            raise ProjectionError("fitter run group input binding mismatch")

        expected_admissibility = evaluate_reference_admissibility(descriptor, query_result)
        if run["admissibility"] != expected_admissibility:
            raise ProjectionError("fitter admissibility result does not match reference evaluation")
        expected_outcome = {
            "ADMISSIBLE": "FIT",
            "INADMISSIBLE": "ABSTAINED",
            "INVALID": "INVALID",
        }[expected_admissibility["status"]]
        if run["outcome"] != expected_outcome:
            raise ProjectionError("fitter outcome is inconsistent with admissibility")

        fit_result = run["fit_result"]
        spec = reference_fitter_spec(descriptor["fitter_class"])
        if expected_outcome == "FIT":
            if fit_result is None:
                raise ProjectionError("admissible fitter run requires a fit result")
            result_id = fit_result["id"]
            if result_id in self.fit_results:
                raise ProjectionError(f"duplicate fit result id: {result_id}")
            components = reference_fit_components(descriptor, query_result)
            self._validate_fit_result(
                fit_result,
                receipt,
                descriptor,
                query_id,
                asset_id,
                expected_input_ids,
                components,
            )
        elif fit_result is not None:
            raise ProjectionError("abstained or invalid fitter run cannot contain a fit result")

        if receipt["assumptions"] != spec["assumptions"]:
            raise ProjectionError("fitter receipt assumptions do not match reference fitter")
        expected_outcome_sha256 = canonical_sha256(
            {
                "outcome": run["outcome"],
                "admissibility": run["admissibility"],
                "fit_result": fit_result,
            }
        )
        if receipt["outcome_sha256"] != expected_outcome_sha256:
            raise ProjectionError("fitter receipt outcome digest mismatch")

        if new_group is not None:
            self._fitter_run_groups[group_id] = new_group
        self.fitter_runs[run_id] = run
        self.fitter_receipts[receipt_id] = receipt
        if fit_result is not None:
            self.fit_results[fit_result["id"]] = fit_result
        self._fitter_run_pairs.add((group_id, fitter_id))
        self._advance_asset(asset_id, event)

    def _apply_hypothesis_created(self, event: dict[str, Any]) -> None:
        hypothesis = deepcopy(event["payload"]["hypothesis"])
        hypothesis_id = hypothesis["id"]
        if hypothesis_id in self.hypotheses:
            raise ProjectionError(f"duplicate hypothesis id: {hypothesis_id}")
        asset_id = hypothesis["asset_entity_id"]
        if asset_id not in self.assets:
            raise ProjectionError(f"hypothesis references unknown tracked asset: {asset_id}")
        unknown_targets = sorted(set(hypothesis["target_entity_ids"]) - self.entities.keys())
        if unknown_targets:
            raise ProjectionError(f"hypothesis references unknown targets: {unknown_targets}")
        claim_ids = [item["claim_id"] for item in hypothesis["claim_bindings"]]
        if len(claim_ids) != len(set(claim_ids)):
            raise ProjectionError("hypothesis binds the same claim more than once")
        unknown_claims = sorted(set(claim_ids) - self.claims.keys())
        if unknown_claims:
            raise ProjectionError(f"hypothesis references unknown claims: {unknown_claims}")
        wrong_asset_claims = sorted(
            claim_id for claim_id in claim_ids if self.claims[claim_id]["subject"] != asset_id
        )
        if wrong_asset_claims:
            raise ProjectionError(
                f"hypothesis claims belong to another asset: {wrong_asset_claims}"
            )

        self.hypotheses[hypothesis_id] = hypothesis
        self.assets[asset_id]["active_hypotheses"].append(hypothesis_id)
        self.assets[asset_id]["active_hypotheses"].sort()
        self._advance_asset(asset_id, event)

    def _apply_belief_edge_created(self, event: dict[str, Any]) -> None:
        edge = deepcopy(event["payload"]["belief_edge"])
        edge_id = edge["id"]
        if edge_id in self.belief_edges:
            raise ProjectionError(f"duplicate belief edge id: {edge_id}")
        source = edge["source_hypothesis_id"]
        target = edge["target_hypothesis_id"]
        missing = sorted({source, target} - self.hypotheses.keys())
        if missing:
            raise ProjectionError(f"belief edge references unknown hypotheses: {missing}")
        if source == target:
            raise ProjectionError("belief edge cannot be self-referential")
        source_asset = self.hypotheses[source]["asset_entity_id"]
        target_asset = self.hypotheses[target]["asset_entity_id"]
        if source_asset != target_asset:
            raise ProjectionError("belief edge cannot cross tracked assets")
        pair = (source, target)
        if pair in self._belief_edge_pairs:
            raise ProjectionError("belief edge already exists for this directed hypothesis pair")
        if self._belief_path_exists(target, source):
            raise ProjectionError("belief edge would create a cycle")

        self.belief_edges[edge_id] = edge
        self._belief_edge_pairs.add(pair)
        self._belief_graph.setdefault(source, set()).add(target)
        self._advance_asset(source_asset, event)

    def _apply_belief_revision_completed(self, event: dict[str, Any]) -> None:
        revision = deepcopy(event["payload"]["belief_revision"])
        revision_id = revision["id"]
        receipt = revision["execution_receipt"]
        receipt_id = receipt["id"]
        if revision_id in self.belief_revisions:
            raise ProjectionError(f"duplicate belief revision id: {revision_id}")
        if receipt_id in self.belief_receipts:
            raise ProjectionError(f"duplicate belief receipt id: {receipt_id}")
        asset_id = revision["asset_entity_id"]
        if asset_id not in self.assets:
            raise ProjectionError(f"belief revision references unknown asset: {asset_id}")
        if receipt["asset_entity_id"] != asset_id:
            raise ProjectionError("belief receipt asset binding mismatch")
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("belief receipt asset state version mismatch")
        if not (revision["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("belief execution times must match ledger-recorded time")
        if receipt["hypothesis_ids"] != sorted(receipt["hypothesis_ids"]):
            raise ProjectionError("belief receipt hypothesis ids must use sorted order")

        try:
            snapshot = build_belief_snapshot(self, asset_id, receipt["hypothesis_ids"])
            components = compute_belief_components(snapshot)
        except BeliefRuntimeError as error:
            raise ProjectionError(str(error)) from error
        if receipt["input_snapshot_sha256"] != canonical_sha256(snapshot):
            raise ProjectionError("belief receipt input snapshot digest mismatch")
        for key, expected in snapshot["input_ids"].items():
            if receipt[key] != expected:
                raise ProjectionError(f"belief receipt {key} does not match graph input")
        if receipt["algorithm_id"] != BELIEF_ALGORITHM_ID:
            raise ProjectionError("belief receipt algorithm mismatch")
        if receipt["implementation_sha256"] != belief_implementation_sha256():
            raise ProjectionError("belief receipt implementation digest mismatch")
        for key, expected in components.items():
            if revision[key] != expected:
                raise ProjectionError(f"belief revision {key} does not match reference propagation")
        if receipt["outcome_sha256"] != canonical_sha256(components):
            raise ProjectionError("belief receipt outcome digest mismatch")

        self.belief_revisions[revision_id] = revision
        self.belief_receipts[receipt_id] = receipt
        self._latest_belief_revision[asset_id] = revision_id
        self._advance_asset(asset_id, event)

    def _apply_scenario_created(self, event: dict[str, Any]) -> None:
        scenario = deepcopy(event["payload"]["scenario"])
        scenario_id = scenario["id"]
        if scenario_id in self.scenarios:
            raise ProjectionError(f"duplicate scenario id: {scenario_id}")
        asset_id = scenario["asset_entity_id"]
        if asset_id not in self.assets:
            raise ProjectionError(f"scenario references unknown tracked asset: {asset_id}")
        if scenario["initial_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("scenario initial state version mismatch")
        revision_id = scenario["belief_revision_id"]
        if revision_id not in self.belief_revisions:
            raise ProjectionError(f"scenario references unknown belief revision: {revision_id}")
        if self.belief_revisions[revision_id]["asset_entity_id"] != asset_id:
            raise ProjectionError("scenario belief revision belongs to another asset")
        unknown_targets = sorted(set(scenario["target_entity_ids"]) - self.entities.keys())
        if unknown_targets:
            raise ProjectionError(f"scenario references unknown target entities: {unknown_targets}")
        self._validate_scenario_plan(scenario)

        self.scenarios[scenario_id] = scenario
        self.assets[asset_id]["active_scenarios"].append(scenario_id)
        self.assets[asset_id]["active_scenarios"].sort()
        self._advance_asset(asset_id, event)

    def _apply_scenario_run_completed(self, event: dict[str, Any]) -> None:
        run = deepcopy(event["payload"]["scenario_run"])
        run_id = run["id"]
        receipt = run["execution_receipt"]
        receipt_id = receipt["id"]
        if run_id in self.scenario_runs:
            raise ProjectionError(f"duplicate scenario run id: {run_id}")
        if receipt_id in self.scenario_receipts:
            raise ProjectionError(f"duplicate scenario receipt id: {receipt_id}")
        scenario_id = run["scenario_id"]
        if scenario_id not in self.scenarios:
            raise ProjectionError(f"scenario run references unknown scenario: {scenario_id}")
        if scenario_id in self._latest_scenario_run:
            raise ProjectionError("bounded scenario already has a completed run")
        scenario = self.scenarios[scenario_id]
        asset_id = scenario["asset_entity_id"]
        if run["asset_entity_id"] != asset_id or receipt["asset_entity_id"] != asset_id:
            raise ProjectionError("scenario run asset binding mismatch")
        if receipt["scenario_id"] != scenario_id:
            raise ProjectionError("scenario receipt plan binding mismatch")
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("scenario receipt asset state version mismatch")
        if not (run["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("scenario execution times must match ledger-recorded time")

        try:
            snapshot = build_scenario_snapshot(self, scenario_id)
            components = compute_scenario_components(snapshot)
        except ScenarioRuntimeError as error:
            raise ProjectionError(str(error)) from error
        expected_receipt_fields = {
            "scenario_snapshot_sha256": canonical_sha256(scenario),
            "belief_revision_id": scenario["belief_revision_id"],
            "belief_revision_sha256": canonical_sha256(snapshot["belief_revision"]),
            "branch_ids": sorted(item["id"] for item in scenario["branches"]),
            "assumption_ids": sorted(item["id"] for item in scenario["assumptions"]),
            "intervention_ids": sorted(item["id"] for item in scenario["interventions"]),
            "algorithm_id": SCENARIO_ALGORITHM_ID,
            "implementation_sha256": scenario_implementation_sha256(),
            "outcome_sha256": canonical_sha256(components),
        }
        mismatched = [
            key for key, expected in expected_receipt_fields.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"scenario receipt binding mismatch: {mismatched}")
        for key, expected in components.items():
            if run[key] != expected:
                raise ProjectionError(f"scenario run {key} does not match reference evaluation")

        self.scenario_runs[run_id] = run
        self.scenario_receipts[receipt_id] = receipt
        self._latest_scenario_run[scenario_id] = run_id
        self._advance_asset(asset_id, event)

    def _apply_collection_discrimination_plan_created(self, event: dict[str, Any]) -> None:
        plan = deepcopy(event["payload"]["discrimination_plan"])
        plan_id = plan["id"]
        if plan_id in self.discrimination_plans:
            raise ProjectionError(f"duplicate discrimination plan id: {plan_id}")
        asset_id = plan["asset_entity_id"]
        if asset_id not in self.assets:
            raise ProjectionError(f"discrimination plan references unknown asset: {asset_id}")
        if plan["initial_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("discrimination plan initial state version mismatch")

        revision_id = plan["belief_revision_id"]
        if revision_id not in self.belief_revisions:
            raise ProjectionError(
                f"discrimination plan references unknown belief revision: {revision_id}"
            )
        revision = self.belief_revisions[revision_id]
        if revision["asset_entity_id"] != asset_id:
            raise ProjectionError("discrimination belief revision belongs to another asset")
        query_id = plan["query_plan_id"]
        if query_id not in self.cartographic_query_plans:
            raise ProjectionError(
                f"discrimination plan references unknown cartographic query: {query_id}"
            )
        if self.cartographic_query_plans[query_id]["asset_entity_id"] != asset_id:
            raise ProjectionError("discrimination query belongs to another asset")

        target_ids = plan["target_hypothesis_ids"]
        if target_ids != sorted(target_ids) or len(target_ids) != len(set(target_ids)):
            raise ProjectionError("discrimination target hypothesis ids must be unique and sorted")
        unknown_hypotheses = sorted(set(target_ids) - self.hypotheses.keys())
        if unknown_hypotheses:
            raise ProjectionError(
                f"discrimination plan references unknown hypotheses: {unknown_hypotheses}"
            )
        if any(self.hypotheses[item]["asset_entity_id"] != asset_id for item in target_ids):
            raise ProjectionError("discrimination hypotheses belong to another asset")
        revision_hypothesis_ids = {item["hypothesis_id"] for item in revision["node_results"]}
        if not set(target_ids).issubset(revision_hypothesis_ids):
            raise ProjectionError("discrimination hypotheses are absent from the bound revision")

        known_blind_regions = set(
            self.execute_cartographic_query(query_id)["blind_regions"]["known"]
        )
        candidate_ids: set[str] = set()
        candidate_keys: set[tuple[str, str, str]] = set()
        for candidate in plan["candidates"]:
            candidate_id = candidate["id"]
            if candidate_id in candidate_ids:
                raise ProjectionError(f"duplicate discrimination candidate id: {candidate_id}")
            candidate_ids.add(candidate_id)
            if candidate["target_hypothesis_ids"] != target_ids:
                raise ProjectionError("candidate target hypotheses do not match plan")
            frame_id = candidate["observer_frame_id"]
            if frame_id not in self.frames:
                raise ProjectionError(f"candidate references unknown observer frame: {frame_id}")
            if (
                candidate["access_scope_snapshot"]
                != self.frames[frame_id]["access_projection"]["scope"]
            ):
                raise ProjectionError("candidate observer-frame access snapshot mismatch")
            candidate_key = (
                frame_id,
                candidate["observation_type"],
                candidate["question"],
            )
            if candidate_key in candidate_keys:
                raise ProjectionError("duplicate discrimination candidate semantic key")
            candidate_keys.add(candidate_key)
            invalid_blind_targets = sorted(
                set(candidate["declared_blind_region_targets"]) - known_blind_regions
            )
            if invalid_blind_targets:
                raise ProjectionError(
                    f"candidate targets unknown query blind regions: {invalid_blind_targets}"
                )
            outcome_labels: set[str] = set()
            for outcome in candidate["expected_outcomes"]:
                if outcome["label"] in outcome_labels:
                    raise ProjectionError("candidate expected-outcome labels must be unique")
                outcome_labels.add(outcome["label"])
                effect_ids = [item["hypothesis_id"] for item in outcome["hypothesis_effects"]]
                if effect_ids != target_ids:
                    raise ProjectionError(
                        "candidate outcome effects must cover every target hypothesis "
                        "in sorted order"
                    )

        self.discrimination_plans[plan_id] = plan
        self._advance_asset(asset_id, event)

    def _apply_collection_discrimination_run_completed(self, event: dict[str, Any]) -> None:
        run = deepcopy(event["payload"]["discrimination_run"])
        run_id = run["id"]
        receipt = run["execution_receipt"]
        receipt_id = receipt["id"]
        if run_id in self.discrimination_runs:
            raise ProjectionError(f"duplicate discrimination run id: {run_id}")
        if receipt_id in self.discrimination_receipts:
            raise ProjectionError(f"duplicate discrimination receipt id: {receipt_id}")
        plan_id = run["plan_id"]
        if plan_id not in self.discrimination_plans:
            raise ProjectionError(f"discrimination run references unknown plan: {plan_id}")
        if plan_id in self._latest_discrimination_run:
            raise ProjectionError("bounded discrimination plan already has a completed run")
        plan = self.discrimination_plans[plan_id]
        asset_id = plan["asset_entity_id"]
        if run["asset_entity_id"] != asset_id or receipt["asset_entity_id"] != asset_id:
            raise ProjectionError("discrimination run asset binding mismatch")
        if receipt["plan_id"] != plan_id:
            raise ProjectionError("discrimination receipt plan binding mismatch")
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("discrimination receipt asset state version mismatch")
        if not (run["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("discrimination execution times must match ledger-recorded time")

        try:
            snapshot = build_discrimination_snapshot(self, plan_id)
            components = compute_discrimination_components(snapshot)
        except DiscriminationRuntimeError as error:
            raise ProjectionError(str(error)) from error
        expected_receipt_fields = {
            "plan_sha256": canonical_sha256(plan),
            "belief_revision_id": plan["belief_revision_id"],
            "belief_revision_sha256": canonical_sha256(snapshot["belief_revision"]),
            "query_plan_id": plan["query_plan_id"],
            "query_result_sha256": snapshot["query_context"]["query_result_sha256"],
            "candidate_ids": sorted(item["id"] for item in plan["candidates"]),
            "target_hypothesis_ids": plan["target_hypothesis_ids"],
            "algorithm_id": DISCRIMINATION_ALGORITHM_ID,
            "implementation_sha256": discrimination_implementation_sha256(),
            "outcome_sha256": canonical_sha256(components),
        }
        mismatched = [
            key for key, expected in expected_receipt_fields.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"discrimination receipt binding mismatch: {mismatched}")
        for key, expected in components.items():
            if run[key] != expected:
                raise ProjectionError(f"discrimination run {key} does not match reference ranking")

        self.discrimination_runs[run_id] = run
        self.discrimination_receipts[receipt_id] = receipt
        self._latest_discrimination_run[plan_id] = run_id
        self._advance_asset(asset_id, event)

    def _apply_residual_readback_completed(self, event: dict[str, Any]) -> None:
        readback = deepcopy(event["payload"]["residual_readback"])
        readback_id = readback["id"]
        receipt = readback["execution_receipt"]
        receipt_id = receipt["id"]
        if readback_id in self.residual_readbacks:
            raise ProjectionError(f"duplicate residual readback id: {readback_id}")
        if receipt_id in self.residual_receipts:
            raise ProjectionError(f"duplicate residual receipt id: {receipt_id}")
        scenario_run_id = readback["scenario_run_id"]
        if scenario_run_id not in self.scenario_runs:
            raise ProjectionError(
                f"residual readback references unknown scenario run: {scenario_run_id}"
            )
        if scenario_run_id in self._scenario_readback:
            raise ProjectionError("bounded scenario run already has a residual readback")
        asset_id = self.scenario_runs[scenario_run_id]["asset_entity_id"]
        if readback["asset_entity_id"] != asset_id or receipt["asset_entity_id"] != asset_id:
            raise ProjectionError("residual readback asset binding mismatch")
        if receipt["readback_id"] != readback_id:
            raise ProjectionError("residual receipt readback binding mismatch")
        if receipt["scenario_run_id"] != scenario_run_id:
            raise ProjectionError("residual receipt scenario-run binding mismatch")
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("residual receipt asset state version mismatch")
        if not (readback["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("residual readback times must match ledger-recorded time")
        if readback["observation_ids"] != sorted(readback["observation_ids"]):
            raise ProjectionError("residual readback observation ids must use sorted order")

        try:
            snapshot = build_residual_snapshot(
                self,
                scenario_run_id,
                readback["observation_ids"],
            )
            components = compute_residual_components(snapshot)
        except ResidualRuntimeError as error:
            raise ProjectionError(str(error)) from error
        expected_receipt_fields = {
            "forecast_evaluation_design_id": snapshot["forecast_evaluation_design"]["id"],
            "forecast_evaluation_design_sha256": canonical_sha256(
                snapshot["forecast_evaluation_design"]
            ),
            "scenario_run_sha256": canonical_sha256(snapshot["scenario_run"]),
            "scenario_sha256": canonical_sha256(snapshot["scenario"]),
            "observation_ids": snapshot["observation_ids"],
            "source_artifact_ids": snapshot["source_artifact_ids"],
            "observer_frame_ids": snapshot["observer_frame_ids"],
            "observation_snapshot_sha256": canonical_sha256(snapshot["observation_snapshot"]),
            "algorithm_id": RESIDUAL_ALGORITHM_ID,
            "implementation_sha256": residual_implementation_sha256(),
            "outcome_sha256": canonical_sha256(components),
        }
        mismatched = [
            key for key, expected in expected_receipt_fields.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"residual receipt binding mismatch: {mismatched}")
        for key, expected in components.items():
            if readback[key] != expected:
                raise ProjectionError(
                    f"residual readback {key} does not match reference eligibility gate"
                )

        self.residual_readbacks[readback_id] = readback
        self.residual_receipts[receipt_id] = receipt
        self._scenario_readback[scenario_run_id] = readback_id
        self._advance_asset(asset_id, event)

    def _apply_forecast_baseline_completed(self, event: dict[str, Any]) -> None:
        baseline = deepcopy(event["payload"]["forecast_baseline"])
        baseline_id = baseline["id"]
        receipt = baseline["execution_receipt"]
        receipt_id = receipt["id"]
        if baseline_id in self.forecast_baselines:
            raise ProjectionError(f"duplicate forecast baseline id: {baseline_id}")
        if receipt_id in self.forecast_baseline_receipts:
            raise ProjectionError(f"duplicate forecast baseline receipt id: {receipt_id}")
        design_id = baseline["forecast_evaluation_design_id"]
        if design_id not in self.forecast_evaluation_designs:
            raise ProjectionError(
                f"forecast baseline references unknown evaluation design: {design_id}"
            )
        if design_id in self._design_forecast_baseline:
            raise ProjectionError("forecast evaluation design already has a frozen baseline")
        design = self.forecast_evaluation_designs[design_id]
        asset_id = design["asset_entity_id"]
        scenario_id = design["scenario_id"]
        if baseline["asset_entity_id"] != asset_id or receipt["asset_entity_id"] != asset_id:
            raise ProjectionError("forecast baseline asset binding mismatch")
        if baseline["scenario_id"] != scenario_id or receipt["scenario_id"] != scenario_id:
            raise ProjectionError("forecast baseline scenario binding mismatch")
        if receipt["forecast_baseline_id"] != baseline_id:
            raise ProjectionError("forecast baseline receipt identity mismatch")
        if receipt["forecast_evaluation_design_id"] != design_id:
            raise ProjectionError("forecast baseline receipt design binding mismatch")
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("forecast baseline asset state version mismatch")
        if not (baseline["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("forecast baseline times must match ledger-recorded time")

        recorded_at = self._parse_timestamp(baseline["recorded_at"])
        if recorded_at < self._parse_timestamp(design["created_at"]):
            raise ProjectionError("forecast baseline precedes its evaluation design")
        if recorded_at >= self._parse_timestamp(design["timing"]["forecast_origin"]):
            raise ProjectionError("forecast baseline was not recorded before forecast origin")

        try:
            snapshot = build_forecast_baseline_snapshot(self, design_id)
            components = compute_forecast_baseline_components(
                snapshot, baseline["prediction"]["value"]
            )
        except ForecastBaselineError as error:
            raise ProjectionError(str(error)) from error
        expected_receipt_fields = {
            "forecast_evaluation_design_sha256": canonical_sha256(
                snapshot["forecast_evaluation_design"]
            ),
            "scenario_sha256": canonical_sha256(snapshot["scenario"]),
            "input_snapshot_sha256": canonical_sha256(snapshot),
            "algorithm_id": FORECAST_BASELINE_ALGORITHM_ID,
            "implementation_sha256": forecast_baseline_implementation_sha256(),
            "outcome_sha256": canonical_sha256(components),
        }
        mismatched = [
            key for key, expected in expected_receipt_fields.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"forecast baseline receipt binding mismatch: {mismatched}")
        for key, expected in components.items():
            if baseline[key] != expected:
                raise ProjectionError(f"forecast baseline {key} does not match reference execution")

        self.forecast_baselines[baseline_id] = baseline
        self.forecast_baseline_receipts[receipt_id] = receipt
        self._design_forecast_baseline[design_id] = baseline_id
        self._advance_asset(asset_id, event)

    def _apply_forecast_readback_selection_plan_created(self, event: dict[str, Any]) -> None:
        plan = deepcopy(event["payload"]["readback_selection_plan"])
        plan_id = plan["id"]
        if plan_id in self.readback_selection_plans:
            raise ProjectionError(f"duplicate readback selection plan id: {plan_id}")
        baseline_id = plan["forecast_baseline_id"]
        if baseline_id not in self.forecast_baselines:
            raise ProjectionError(
                f"readback selection plan references unknown baseline: {baseline_id}"
            )
        if baseline_id in self._baseline_readback_selection_plan:
            raise ProjectionError("forecast baseline already has a readback selection plan")
        baseline = self.forecast_baselines[baseline_id]
        design = self.forecast_evaluation_designs[baseline["forecast_evaluation_design_id"]]
        asset_id = baseline["asset_entity_id"]
        if plan["asset_entity_id"] != asset_id:
            raise ProjectionError("readback selection plan asset binding mismatch")
        if plan["forecast_evaluation_design_id"] != design["id"]:
            raise ProjectionError("readback selection plan design binding mismatch")
        if plan["scenario_id"] != baseline["scenario_id"]:
            raise ProjectionError("readback selection plan scenario binding mismatch")
        if plan["initial_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("readback selection plan initial state version mismatch")
        if plan["created_at"] != event["occurred_at"]:
            raise ProjectionError("readback selection plan time must match ledger-recorded time")
        if plan["eligible_observer_frame_ids"] != sorted(plan["eligible_observer_frame_ids"]):
            raise ProjectionError("eligible observer frame ids must use sorted order")
        missing_frames = sorted(set(plan["eligible_observer_frame_ids"]) - self.frames.keys())
        if missing_frames:
            raise ProjectionError(
                f"readback selection plan references unknown frames: {missing_frames}"
            )
        expected_target = {
            "observation_type": design["target"]["observation_type"],
            "structured_field_path": design["target"]["structured_field_path"],
            "value_kind": "NUMBER",
            "unit": design["target"]["unit"],
            "unit_match_state": "USER_DECLARED_NOT_VERIFIED",
        }
        if plan["target"] != expected_target:
            raise ProjectionError("readback selection plan target binding mismatch")
        if plan["timing"]["forecast_origin"] != design["timing"]["forecast_origin"]:
            raise ProjectionError("readback selection plan forecast origin mismatch")
        if plan["timing"]["horizon_end"] != design["timing"]["horizon_end"]:
            raise ProjectionError("readback selection plan horizon mismatch")
        created_at = self._parse_timestamp(plan["created_at"])
        if created_at < self._parse_timestamp(baseline["recorded_at"]):
            raise ProjectionError("readback selection plan precedes its forecast baseline")
        if created_at >= self._parse_timestamp(design["timing"]["forecast_origin"]):
            raise ProjectionError("readback selection plan was not recorded before forecast origin")
        if self._parse_timestamp(plan["timing"]["observed_window_end"]) <= self._parse_timestamp(
            design["timing"]["horizon_end"]
        ):
            raise ProjectionError("readback observed window does not follow forecast horizon")
        if self._parse_timestamp(plan["timing"]["ledger_admission_cutoff"]) < self._parse_timestamp(
            plan["timing"]["observed_window_end"]
        ):
            raise ProjectionError("readback admission cutoff precedes observed window end")

        self.readback_selection_plans[plan_id] = plan
        self._baseline_readback_selection_plan[baseline_id] = plan_id
        self._advance_asset(asset_id, event)

    def _apply_forecast_readback_selection_completed(self, event: dict[str, Any]) -> None:
        run = deepcopy(event["payload"]["readback_selection_run"])
        run_id = run["id"]
        receipt = run["execution_receipt"]
        receipt_id = receipt["id"]
        if run_id in self.readback_selection_runs:
            raise ProjectionError(f"duplicate readback selection run id: {run_id}")
        if receipt_id in self.readback_selection_receipts:
            raise ProjectionError(f"duplicate readback selection receipt id: {receipt_id}")
        plan_id = run["readback_selection_plan_id"]
        if plan_id not in self.readback_selection_plans:
            raise ProjectionError(f"readback selection run references unknown plan: {plan_id}")
        if plan_id in self._plan_readback_selection_run:
            raise ProjectionError("readback selection plan already has a completed run")
        plan = self.readback_selection_plans[plan_id]
        asset_id = plan["asset_entity_id"]
        identity_fields = {
            "asset_entity_id": asset_id,
            "forecast_baseline_id": plan["forecast_baseline_id"],
            "forecast_evaluation_design_id": plan["forecast_evaluation_design_id"],
            "scenario_id": plan["scenario_id"],
        }
        if any(run[key] != expected for key, expected in identity_fields.items()):
            raise ProjectionError("readback selection run binding mismatch")
        if receipt["readback_selection_run_id"] != run_id:
            raise ProjectionError("readback selection receipt run binding mismatch")
        if receipt["readback_selection_plan_id"] != plan_id:
            raise ProjectionError("readback selection receipt plan binding mismatch")
        if any(receipt[key] != expected for key, expected in identity_fields.items()):
            raise ProjectionError("readback selection receipt identity mismatch")
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("readback selection receipt asset state version mismatch")
        if not (run["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("readback selection times must match ledger-recorded time")
        if self._parse_timestamp(run["recorded_at"]) < self._parse_timestamp(
            plan["timing"]["ledger_admission_cutoff"]
        ):
            raise ProjectionError("readback selection executed before admission cutoff")

        try:
            snapshot = build_readback_selection_snapshot(self, plan_id)
            components = compute_readback_selection_components(snapshot)
        except ReadbackSelectionError as error:
            raise ProjectionError(str(error)) from error
        expected_receipt_fields = {
            "plan_sha256": canonical_sha256(plan),
            "forecast_baseline_sha256": canonical_sha256(snapshot["forecast_baseline"]),
            "forecast_evaluation_design_sha256": canonical_sha256(
                snapshot["forecast_evaluation_design"]
            ),
            "scenario_sha256": canonical_sha256(snapshot["scenario"]),
            "eligible_observer_frame_ids": plan["eligible_observer_frame_ids"],
            "eligible_observer_frames_sha256": canonical_sha256(
                snapshot["eligible_observer_frames"]
            ),
            "input_snapshot_sha256": canonical_sha256(snapshot),
            "algorithm_id": READBACK_SELECTION_ALGORITHM_ID,
            "implementation_sha256": readback_selection_implementation_sha256(),
            "outcome_sha256": canonical_sha256(components),
        }
        mismatched = [
            key for key, expected in expected_receipt_fields.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"readback selection receipt binding mismatch: {mismatched}")
        for key, expected in components.items():
            if run[key] != expected:
                raise ProjectionError(
                    f"readback selection {key} does not match reference execution"
                )

        self.readback_selection_runs[run_id] = run
        self.readback_selection_receipts[receipt_id] = receipt
        self._plan_readback_selection_run[plan_id] = run_id
        self._advance_asset(asset_id, event)

    def _apply_forecast_residual_computed(self, event: dict[str, Any]) -> None:
        result = deepcopy(event["payload"]["forecast_residual"])
        result_id = result["id"]
        receipt = result["execution_receipt"]
        receipt_id = receipt["id"]
        if result_id in self.forecast_residuals:
            raise ProjectionError(f"duplicate forecast residual id: {result_id}")
        if receipt_id in self.forecast_residual_receipts:
            raise ProjectionError(f"duplicate forecast residual receipt id: {receipt_id}")
        selection_run_id = result["readback_selection_run_id"]
        if selection_run_id not in self.readback_selection_runs:
            raise ProjectionError(
                f"forecast residual references unknown selection run: {selection_run_id}"
            )
        if selection_run_id in self._selection_run_forecast_residual:
            raise ProjectionError("readback selection run already has a forecast residual")
        selection_run = self.readback_selection_runs[selection_run_id]
        identity_fields = {
            "asset_entity_id": selection_run["asset_entity_id"],
            "readback_selection_plan_id": selection_run["readback_selection_plan_id"],
            "forecast_baseline_id": selection_run["forecast_baseline_id"],
            "forecast_evaluation_design_id": selection_run["forecast_evaluation_design_id"],
            "scenario_id": selection_run["scenario_id"],
            "selected_observation_id": selection_run["selected_observation_id"],
        }
        if any(result[key] != expected for key, expected in identity_fields.items()):
            raise ProjectionError("forecast residual identity binding mismatch")
        if receipt["forecast_residual_id"] != result_id:
            raise ProjectionError("forecast residual receipt identity mismatch")
        if receipt["readback_selection_run_id"] != selection_run_id:
            raise ProjectionError("forecast residual receipt selection-run mismatch")
        if any(receipt[key] != expected for key, expected in identity_fields.items()):
            raise ProjectionError("forecast residual receipt input identity mismatch")
        asset_id = selection_run["asset_entity_id"]
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("forecast residual asset state version mismatch")
        if not (result["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("forecast residual times must match ledger-recorded time")
        if self._parse_timestamp(result["recorded_at"]) < self._parse_timestamp(
            selection_run["recorded_at"]
        ):
            raise ProjectionError("forecast residual precedes readback selection")

        try:
            snapshot = build_forecast_residual_snapshot(self, selection_run_id)
            components = compute_forecast_residual_components(snapshot)
        except ForecastResidualError as error:
            raise ProjectionError(str(error)) from error
        observation = snapshot["selected_observation"]
        expected_receipt_fields = {
            "selected_evidence_manifest_id": observation["source_artifact_id"],
            "selected_observer_frame_id": observation["observer_frame_id"],
            "readback_selection_run_sha256": canonical_sha256(selection_run),
            "readback_selection_plan_sha256": canonical_sha256(snapshot["selection_plan"]),
            "forecast_baseline_sha256": canonical_sha256(snapshot["forecast_baseline"]),
            "forecast_evaluation_design_sha256": canonical_sha256(
                snapshot["forecast_evaluation_design"]
            ),
            "scenario_sha256": canonical_sha256(snapshot["scenario"]),
            "selected_observation_sha256": canonical_sha256(observation),
            "selected_evidence_manifest_sha256": canonical_sha256(
                snapshot["selected_evidence_manifest"]
            ),
            "selected_observer_frame_sha256": canonical_sha256(snapshot["selected_observer_frame"]),
            "input_snapshot_sha256": canonical_sha256(snapshot),
            "algorithm_id": FORECAST_RESIDUAL_ALGORITHM_ID,
            "implementation_sha256": forecast_residual_implementation_sha256(),
            "outcome_sha256": canonical_sha256(components),
        }
        mismatched = [
            key for key, expected in expected_receipt_fields.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"forecast residual receipt binding mismatch: {mismatched}")
        for key, expected in components.items():
            if result[key] != expected:
                raise ProjectionError(
                    f"forecast residual {key} does not match reference arithmetic"
                )

        self.forecast_residuals[result_id] = result
        self.forecast_residual_receipts[receipt_id] = receipt
        self._selection_run_forecast_residual[selection_run_id] = result_id
        self._advance_asset(asset_id, event)

    def _apply_forecast_validity_update_assessed(self, event: dict[str, Any]) -> None:
        assessment = deepcopy(event["payload"]["forecast_validity_assessment"])
        assessment_id = assessment["id"]
        receipt = assessment["execution_receipt"]
        receipt_id = receipt["id"]
        if assessment_id in self.forecast_validity_assessments:
            raise ProjectionError(f"duplicate forecast validity assessment id: {assessment_id}")
        if receipt_id in self.forecast_validity_receipts:
            raise ProjectionError(f"duplicate forecast validity receipt id: {receipt_id}")
        residual_id = assessment["forecast_residual_id"]
        if residual_id not in self.forecast_residuals:
            raise ProjectionError(
                f"forecast validity assessment references unknown residual: {residual_id}"
            )
        if residual_id in self._residual_forecast_validity_assessment:
            raise ProjectionError("forecast residual already has a validity assessment")
        residual = self.forecast_residuals[residual_id]
        identity_fields = {
            "asset_entity_id": residual["asset_entity_id"],
            "readback_selection_run_id": residual["readback_selection_run_id"],
            "forecast_baseline_id": residual["forecast_baseline_id"],
            "forecast_evaluation_design_id": residual["forecast_evaluation_design_id"],
            "scenario_id": residual["scenario_id"],
        }
        if any(assessment[key] != expected for key, expected in identity_fields.items()):
            raise ProjectionError("forecast validity assessment identity mismatch")
        if receipt["forecast_validity_assessment_id"] != assessment_id:
            raise ProjectionError("forecast validity receipt identity mismatch")
        if receipt["forecast_residual_id"] != residual_id:
            raise ProjectionError("forecast validity receipt residual mismatch")
        if any(receipt[key] != expected for key, expected in identity_fields.items()):
            raise ProjectionError("forecast validity receipt input identity mismatch")
        asset_id = residual["asset_entity_id"]
        if receipt["asset_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("forecast validity asset state version mismatch")
        if not (assessment["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("forecast validity times must match ledger-recorded time")
        if self._parse_timestamp(assessment["recorded_at"]) < self._parse_timestamp(
            residual["recorded_at"]
        ):
            raise ProjectionError("forecast validity assessment precedes residual")

        try:
            snapshot = build_forecast_validity_snapshot(self, residual_id)
            components = compute_forecast_validity_components(snapshot)
        except ForecastValidityError as error:
            raise ProjectionError(str(error)) from error
        expected_receipt_fields = {
            "forecast_residual_sha256": canonical_sha256(residual),
            "readback_selection_run_sha256": canonical_sha256(snapshot["readback_selection_run"]),
            "forecast_baseline_sha256": canonical_sha256(snapshot["forecast_baseline"]),
            "forecast_evaluation_design_sha256": canonical_sha256(
                snapshot["forecast_evaluation_design"]
            ),
            "scenario_sha256": canonical_sha256(snapshot["scenario"]),
            "input_snapshot_sha256": canonical_sha256(snapshot),
            "algorithm_id": FORECAST_VALIDITY_ALGORITHM_ID,
            "implementation_sha256": forecast_validity_implementation_sha256(),
            "outcome_sha256": canonical_sha256(components),
        }
        mismatched = [
            key for key, expected in expected_receipt_fields.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"forecast validity receipt binding mismatch: {mismatched}")
        for key, expected in components.items():
            if assessment[key] != expected:
                raise ProjectionError(f"forecast validity {key} does not match reference gate")

        self.forecast_validity_assessments[assessment_id] = assessment
        self.forecast_validity_receipts[receipt_id] = receipt
        self._residual_forecast_validity_assessment[residual_id] = assessment_id
        self._advance_asset(asset_id, event)

    def _apply_forecast_fitter_specification_registered(self, event: dict[str, Any]) -> None:
        specification = deepcopy(event["payload"]["forecast_fitter_specification"])
        specification_id = specification["id"]
        if specification_id in self.forecast_fitter_specifications:
            raise ProjectionError(f"duplicate forecast fitter specification id: {specification_id}")
        asset_id = specification["asset_entity_id"]
        if asset_id not in self.assets:
            raise ProjectionError(
                f"forecast fitter specification references untracked asset: {asset_id}"
            )
        if (
            specification["initial_state_version"]
            != self.assets[asset_id]["epistemic_state_version"]
        ):
            raise ProjectionError("forecast fitter specification initial state version mismatch")
        if specification["registered_at"] != event["occurred_at"]:
            raise ProjectionError(
                "forecast fitter specification time must match ledger-recorded time"
            )
        feature_names = [item["name"] for item in specification["feature_contracts"]]
        if feature_names != sorted(feature_names):
            raise ProjectionError("forecast fitter feature contracts must use sorted name order")
        if len(feature_names) != len(set(feature_names)):
            raise ProjectionError("forecast fitter feature names must be unique")

        self.forecast_fitter_specifications[specification_id] = specification
        self._advance_asset(asset_id, event)

    def _apply_forecast_evaluation_design_created(self, event: dict[str, Any]) -> None:
        design = deepcopy(event["payload"]["forecast_evaluation_design"])
        design_id = design["id"]
        if design_id in self.forecast_evaluation_designs:
            raise ProjectionError(f"duplicate forecast evaluation design id: {design_id}")
        scenario_id = design["scenario_id"]
        if scenario_id not in self.scenarios:
            raise ProjectionError(
                f"forecast evaluation design references unknown scenario: {scenario_id}"
            )
        if scenario_id in self._scenario_forecast_evaluation_design:
            raise ProjectionError("bounded scenario already has a forecast evaluation design")
        scenario = self.scenarios[scenario_id]
        asset_id = scenario["asset_entity_id"]
        if design["asset_entity_id"] != asset_id:
            raise ProjectionError("forecast evaluation design asset binding mismatch")
        if design["initial_state_version"] != self.assets[asset_id]["epistemic_state_version"]:
            raise ProjectionError("forecast evaluation design initial state version mismatch")
        if design["created_at"] != event["occurred_at"]:
            raise ProjectionError("forecast evaluation design time must match ledger-recorded time")

        created_at = self._parse_timestamp(design["created_at"])
        training_cutoff = self._parse_timestamp(design["timing"]["training_cutoff"])
        forecast_origin = self._parse_timestamp(scenario["start_time"])
        horizon_end = forecast_origin + timedelta(days=scenario["horizon_days"])
        if training_cutoff > created_at:
            raise ProjectionError("forecast training cutoff follows design creation")
        if created_at >= forecast_origin:
            raise ProjectionError(
                "forecast evaluation design was not recorded before forecast origin"
            )
        expected_timing = {
            "forecast_origin": forecast_origin.isoformat().replace("+00:00", "Z"),
            "horizon_end": horizon_end.isoformat().replace("+00:00", "Z"),
        }
        mismatched = [
            key for key, expected in expected_timing.items() if design["timing"][key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"forecast evaluation design timing mismatch: {mismatched}")

        self.forecast_evaluation_designs[design_id] = design
        self._scenario_forecast_evaluation_design[scenario_id] = design_id
        self._advance_asset(asset_id, event)

    def _validate_fitter_receipt_identity(
        self,
        run: dict[str, Any],
        receipt: dict[str, Any],
        descriptor: dict[str, Any],
        event: dict[str, Any],
    ) -> None:
        expected_bindings = {
            "run_group_id": run["run_group_id"],
            "query_plan_id": run["query_plan_id"],
            "fitter_id": run["fitter_id"],
            "fitter_version": descriptor["version"],
            "implementation_sha256": descriptor["implementation_sha256"],
        }
        mismatched = [
            key for key, expected in expected_bindings.items() if receipt[key] != expected
        ]
        if mismatched:
            raise ProjectionError(f"fitter receipt binding mismatch: {mismatched}")
        if not (run["recorded_at"] == receipt["executed_at"] == event["occurred_at"]):
            raise ProjectionError("fitter execution times must match ledger-recorded time")

    def _validate_fit_result(
        self,
        result: dict[str, Any],
        receipt: dict[str, Any],
        descriptor: dict[str, Any],
        query_id: str,
        asset_id: str,
        expected_input_ids: dict[str, list[str]],
        components: dict[str, Any],
    ) -> None:
        expected_bindings = {
            "fitter_id": descriptor["id"],
            "fitter_version": descriptor["version"],
            "query_plan_id": query_id,
            "asset_entity_id": asset_id,
            "target_metric": descriptor["target_metric"],
            "execution_receipt_id": receipt["id"],
        }
        mismatched = [key for key, expected in expected_bindings.items() if result[key] != expected]
        if mismatched:
            raise ProjectionError(f"fit result binding mismatch: {mismatched}")
        for key, expected in expected_input_ids.items():
            if result[key] != expected:
                raise ProjectionError(f"fit result {key} does not match query input")
        if result["estimate"] != components["estimate"]:
            raise ProjectionError("fit result estimate does not match reference implementation")
        if result["distribution"] != components["distribution"]:
            raise ProjectionError("fit result distribution does not match reference implementation")
        if result["assumptions"] != components["assumptions"]:
            raise ProjectionError("fit result assumptions do not match reference implementation")
        expected_validity = {
            "status": descriptor["declared_validity"]["status"],
            "domain": descriptor["declared_validity"]["domain"],
            "boundary_proximity": None,
            "invalid_conditions": descriptor["declared_validity"]["invalid_conditions"],
        }
        if result["validity"] != expected_validity:
            raise ProjectionError("fit result validity does not match descriptor boundary")

    def _fitter_input_ids(self, query_result: dict[str, Any]) -> dict[str, list[str]]:
        return {
            "input_observation_ids": sorted(item["id"] for item in query_result["observations"]),
            "input_claim_ids": sorted(item["claim"]["id"] for item in query_result["claims"]),
            "input_relation_ids": sorted(item["id"] for item in query_result["relations"]),
            "input_evidence_manifest_ids": sorted(
                item["id"] for item in query_result["evidence_manifests"]
            ),
        }

    def _validate_temporal_scope(self, observation: dict[str, Any]) -> None:
        self._validate_interval(observation, "observation validity")

    def _validate_interval(self, record: dict[str, Any], label: str) -> None:
        valid_from = record["valid_from"]
        valid_until = record["valid_until"]
        if (
            valid_from
            and valid_until
            and datetime.fromisoformat(valid_from.replace("Z", "+00:00"))
            > datetime.fromisoformat(valid_until.replace("Z", "+00:00"))
        ):
            raise ProjectionError(f"{label} valid_from is after valid_until")

    def _validate_source_alignment(self, observation: dict[str, Any]) -> None:
        manifest = self.evidence[observation["source_artifact_id"]]
        frame = self.frames[observation["observer_frame_id"]]
        source_policy = observation["provenance"]["source_policy"]
        if source_policy != manifest["access_policy"]:
            raise ProjectionError("observation source policy does not match evidence manifest")
        if source_policy != frame["access_projection"]["scope"]:
            raise ProjectionError("observation source policy does not match observer frame")

        observation_uri = observation["provenance"]["source_uri"]
        manifest_uri = manifest["source"]["uri"]
        if observation_uri != manifest_uri:
            raise ProjectionError("observation source URI does not match evidence manifest")

    def _validate_observation_dependency_groups(self, observation: dict[str, Any]) -> None:
        artifact_id = observation["source_artifact_id"]
        for group_id in observation["epistemic"]["dependency_group_ids"]:
            if group_id not in self._dependency_groups:
                raise ProjectionError(
                    f"observation references unknown dependency group: {group_id}"
                )
            if artifact_id not in self._dependency_groups[group_id]:
                raise ProjectionError(
                    "observation artifact is not a member of its declared dependency group"
                )

    def _validate_resolution_signal(
        self,
        signal: dict[str, Any],
        candidate_entities: set[str],
    ) -> None:
        if signal["kind"] == "CONTRADICTION" and signal["polarity"] != "CHALLENGES_CANDIDACY":
            raise ProjectionError("CONTRADICTION signal must challenge candidacy")
        verification_status = signal["verification_status"]
        if signal["kind"] == "OBSERVATION_REFERENCE":
            if verification_status != "REFERENCE_VALIDATED":
                raise ProjectionError(
                    "OBSERVATION_REFERENCE signal requires REFERENCE_VALIDATED status"
                )
            self._validate_resolution_observation_reference(signal, candidate_entities)
            return
        if verification_status == "REFERENCE_VALIDATED":
            raise ProjectionError(
                "REFERENCE_VALIDATED status is limited to OBSERVATION_REFERENCE signals"
            )
        if verification_status == "ENTITY_RECORD_VALIDATED":
            self._validate_entity_record_resolution_signal(signal, candidate_entities)

    def _validate_resolution_observation_reference(
        self,
        signal: dict[str, Any],
        candidate_entities: set[str],
    ) -> None:
        observation_id = signal["observation_id"]
        if observation_id not in self.observations:
            raise ProjectionError(
                f"resolution signal references unknown observation: {observation_id}"
            )
        subjects = set(self.observations[observation_id]["subject_entities"])
        if not subjects.intersection(candidate_entities):
            raise ProjectionError("resolution signal observation concerns neither candidate entity")

    def _validate_entity_record_resolution_signal(
        self,
        signal: dict[str, Any],
        candidate_entities: set[str],
    ) -> None:
        if signal["kind"] not in {"SHARED_ALIAS", "SHARED_EXTERNAL_ID"}:
            raise ProjectionError(
                "ENTITY_RECORD_VALIDATED status is limited to exact shared entity-record fields"
            )
        left_entity_id, right_entity_id = sorted(candidate_entities)
        left = self.entities[left_entity_id]
        right = self.entities[right_entity_id]
        if signal["kind"] == "SHARED_ALIAS":
            left_names = {left["canonical_name"], *left["aliases"]}
            right_names = {right["canonical_name"], *right["aliases"]}
            if not left_names.intersection(right_names):
                raise ProjectionError(
                    "validated shared-alias signal has no exact entity-record match"
                )
            return

        left_ids = {(item["scheme"], item["value"]) for item in left["external_ids"]}
        right_ids = {(item["scheme"], item["value"]) for item in right["external_ids"]}
        if not left_ids.intersection(right_ids):
            raise ProjectionError(
                "validated shared-external-id signal has no exact entity-record match"
            )

    def _validate_evidence_link_axes(self, link: dict[str, Any]) -> None:
        warrant = link["warrant"]
        if warrant["status"] == "NOT_PROVIDED" and (
            warrant["statement"] is not None or warrant["basis"] is not None
        ):
            raise ProjectionError("NOT_PROVIDED warrant cannot contain a statement or basis")
        if warrant["status"] == "PROVIDED" and (
            warrant["statement"] is None or warrant["basis"] is None
        ):
            raise ProjectionError("PROVIDED warrant requires a statement and basis")

        appraisal = link["appraisal"]
        strength = link["strength"]
        if appraisal["status"] == "NOT_APPRAISED" and (
            appraisal["method"] is not None or appraisal["notes"] is not None
        ):
            raise ProjectionError("NOT_APPRAISED link cannot contain appraisal details")
        if appraisal["status"] == "APPRAISED" and appraisal["method"] is None:
            raise ProjectionError("APPRAISED link requires an appraisal method")
        if strength["status"] == "UNASSESSED" and strength["ordinal"] is not None:
            raise ProjectionError("UNASSESSED strength cannot contain an ordinal")
        if strength["status"] == "ASSESSED" and (
            strength["ordinal"] is None or appraisal["status"] != "APPRAISED"
        ):
            raise ProjectionError("ASSESSED strength requires an ordinal and completed appraisal")

    def _belief_path_exists(self, start: str, target: str) -> bool:
        pending = [start]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(self._belief_graph.get(current, set()) - visited)
        return False

    def _validate_scenario_plan(self, scenario: dict[str, Any]) -> None:
        assumption_ids = [item["id"] for item in scenario["assumptions"]]
        intervention_ids = [item["id"] for item in scenario["interventions"]]
        branch_ids = [item["id"] for item in scenario["branches"]]
        for label, values in (
            ("assumption", assumption_ids),
            ("intervention", intervention_ids),
            ("branch", branch_ids),
        ):
            if len(values) != len(set(values)):
                raise ProjectionError(f"scenario contains duplicate {label} ids")

        target_ids = set(scenario["target_entity_ids"])
        invalid_interventions = sorted(
            item["id"]
            for item in scenario["interventions"]
            if item["target_entity_id"] not in target_ids
        )
        if invalid_interventions:
            raise ProjectionError(
                f"scenario interventions target entities outside the plan: {invalid_interventions}"
            )

        revision_hypothesis_ids = {
            item["hypothesis_id"]
            for item in self.belief_revisions[scenario["belief_revision_id"]]["node_results"]
        }
        assumptions = set(assumption_ids)
        interventions = set(intervention_ids)
        branches = {item["id"]: item for item in scenario["branches"]}
        unknown = [item for item in scenario["branches"] if item["kind"] == "UNKNOWN_UNMODELED"]
        if len(unknown) != 1:
            raise ProjectionError("scenario requires exactly one unknown/unmodeled branch")
        unknown_id = unknown[0]["id"]
        if unknown[0]["parent_branch_id"] is not None:
            raise ProjectionError("unknown/unmodeled branch must remain a root")

        for branch in scenario["branches"]:
            parent = branch["parent_branch_id"]
            if parent == branch["id"]:
                raise ProjectionError("scenario branch cannot parent itself")
            if parent is not None and parent not in branches:
                raise ProjectionError(f"scenario branch references unknown parent: {parent}")
            if parent == unknown_id:
                raise ProjectionError("unknown/unmodeled branch cannot parent declared outcomes")
            if not set(branch["assumption_ids"]) <= assumptions:
                raise ProjectionError("scenario branch references unknown assumptions")
            if not set(branch["intervention_ids"]) <= interventions:
                raise ProjectionError("scenario branch references unknown interventions")
            if branch["kind"] == "UNKNOWN_UNMODELED":
                if branch["condition"] is not None:
                    raise ProjectionError("unknown/unmodeled branch cannot declare a condition")
                if branch["transition_support_state"] != "UNMODELED":
                    raise ProjectionError("unknown/unmodeled branch must remain unmodeled")
            else:
                if branch["condition"] is None:
                    raise ProjectionError("conditional scenario branch requires a condition")
                if branch["condition"]["hypothesis_id"] not in revision_hypothesis_ids:
                    raise ProjectionError(
                        "scenario branch condition is absent from the bound belief revision"
                    )
                if branch["transition_support_state"] != "USER_DEFINED_NOT_VALIDATED":
                    raise ProjectionError("conditional scenario transition cannot be promoted")

        depth_cache: dict[str, int] = {}

        def depth(branch_id: str, path: set[str]) -> int:
            if branch_id in depth_cache:
                return depth_cache[branch_id]
            if branch_id in path:
                raise ProjectionError("scenario branches contain a cycle")
            parent = branches[branch_id]["parent_branch_id"]
            result = 1 if parent is None else 1 + depth(parent, path | {branch_id})
            depth_cache[branch_id] = result
            return result

        if max(depth(branch_id, set()) for branch_id in branches) > 4:
            raise ProjectionError("scenario branch depth exceeds the bounded maximum of four")

    def _dependency_path_exists(self, start: str, target: str) -> bool:
        pending = [start]
        visited: set[str] = set()
        while pending:
            current = pending.pop()
            if current == target:
                return True
            if current in visited:
                continue
            visited.add(current)
            pending.extend(self._dependency_graph.get(current, set()) - visited)
        return False

    def _assets_for_evidence(self, evidence_ids: set[str]) -> set[str]:
        return {
            entity_id
            for observation in self.observations.values()
            if observation["source_artifact_id"] in evidence_ids
            for entity_id in observation["subject_entities"]
            if entity_id in self.assets
        }

    def _advance_asset(self, entity_id: str, event: dict[str, Any]) -> None:
        if entity_id not in self.assets:
            return
        self.assets[entity_id]["epistemic_state_version"] = event["event_id"]
        self.asset_versions.setdefault(entity_id, []).append(
            {
                "state_version": event["event_id"],
                "event_type": event["event_type"],
                "recorded_at": event["occurred_at"],
            }
        )

    def _claim_connects_entities(self, claim: dict[str, Any], source: str, target: str) -> bool:
        return (
            claim["subject"] == source
            and claim["object"]["kind"] == "ENTITY"
            and claim["object"]["entity_id"] == target
        )

    def asset_view(self, entity_id: str) -> dict[str, Any]:
        if entity_id not in self.assets:
            raise ProjectionError(f"unknown tracked asset: {entity_id}")

        observations = [
            deepcopy(observation)
            for observation in self.observations.values()
            if entity_id in observation["subject_entities"]
        ]
        observations.sort(key=lambda item: (item["observed_at"], item["id"]))
        claims = [
            self.claim_view(item)
            for item in self.claims
            if self.claims[item]["subject"] == entity_id
        ]
        relations = [
            deepcopy(relation)
            for relation in self.relations.values()
            if entity_id in {relation["source_entity"], relation["target_entity"]}
        ]
        relations.sort(key=lambda item: (item["created_at"], item["id"]))
        resolution_candidates = [
            self.resolution_candidate_view(candidate_id)
            for candidate_id, candidate in self.resolution_candidates.items()
            if entity_id in {candidate["left_entity_id"], candidate["right_entity_id"]}
        ]
        resolution_candidates.sort(
            key=lambda item: (
                item["candidate"]["recorded_at"],
                item["candidate"]["id"],
            )
        )
        cartographic_query_plans = [
            self.cartographic_query_plan_view(query_id)
            for query_id, plan in self.cartographic_query_plans.items()
            if plan["asset_entity_id"] == entity_id
        ]
        cartographic_query_plans.sort(
            key=lambda item: (item["ledger_recorded_at"], item["plan"]["id"])
        )
        multi_fitter_runs = [
            self.multi_fitter_run_view(group_id)
            for group_id, group in self._fitter_run_groups.items()
            if group["asset_entity_id"] == entity_id
        ]
        multi_fitter_runs.sort(key=lambda item: (item["recorded_at"], item["run_group_id"]))
        hypotheses = [
            self.hypothesis_view(hypothesis_id)
            for hypothesis_id, hypothesis in self.hypotheses.items()
            if hypothesis["asset_entity_id"] == entity_id
        ]
        hypotheses.sort(
            key=lambda item: (item["hypothesis"]["created_at"], item["hypothesis"]["id"])
        )
        belief_revisions = [
            self.belief_revision_view(revision_id)
            for revision_id, revision in self.belief_revisions.items()
            if revision["asset_entity_id"] == entity_id
        ]
        belief_revisions.sort(
            key=lambda item: (item["revision"]["recorded_at"], item["revision"]["id"])
        )
        scenarios = [
            self.scenario_view(scenario_id)
            for scenario_id, scenario in self.scenarios.items()
            if scenario["asset_entity_id"] == entity_id
        ]
        scenarios.sort(key=lambda item: (item["scenario"]["created_at"], item["scenario"]["id"]))
        discrimination_plans = [
            self.discrimination_plan_view(plan_id)
            for plan_id, plan in self.discrimination_plans.items()
            if plan["asset_entity_id"] == entity_id
        ]
        discrimination_plans.sort(key=lambda item: (item["plan"]["created_at"], item["plan"]["id"]))
        forecast_evaluation_designs = [
            self.forecast_evaluation_design_view(design_id)
            for design_id, design in self.forecast_evaluation_designs.items()
            if design["asset_entity_id"] == entity_id
        ]
        forecast_evaluation_designs.sort(
            key=lambda item: (item["design"]["created_at"], item["design"]["id"])
        )
        forecast_baselines = [
            self.forecast_baseline_view(baseline_id)
            for baseline_id, baseline in self.forecast_baselines.items()
            if baseline["asset_entity_id"] == entity_id
        ]
        forecast_baselines.sort(
            key=lambda item: (item["baseline"]["recorded_at"], item["baseline"]["id"])
        )
        readback_selection_plans = [
            self.readback_selection_plan_view(plan_id)
            for plan_id, plan in self.readback_selection_plans.items()
            if plan["asset_entity_id"] == entity_id
        ]
        readback_selection_plans.sort(
            key=lambda item: (item["plan"]["created_at"], item["plan"]["id"])
        )
        forecast_residuals = [
            self.forecast_residual_view(result_id)
            for result_id, result in self.forecast_residuals.items()
            if result["asset_entity_id"] == entity_id
        ]
        forecast_residuals.sort(
            key=lambda item: (
                item["forecast_residual"]["recorded_at"],
                item["forecast_residual"]["id"],
            )
        )
        forecast_validity_assessments = [
            self.forecast_validity_assessment_view(assessment_id)
            for assessment_id, assessment in self.forecast_validity_assessments.items()
            if assessment["asset_entity_id"] == entity_id
        ]
        forecast_validity_assessments.sort(
            key=lambda item: (
                item["forecast_validity_assessment"]["recorded_at"],
                item["forecast_validity_assessment"]["id"],
            )
        )
        forecast_fitter_specifications = [
            self.forecast_fitter_specification_view(specification_id)
            for specification_id, specification in self.forecast_fitter_specifications.items()
            if specification["asset_entity_id"] == entity_id
        ]
        forecast_fitter_specifications.sort(
            key=lambda item: (
                item["specification"]["registered_at"],
                item["specification"]["id"],
            )
        )
        residual_readbacks = [
            self.residual_readback_view(readback_id)
            for readback_id, readback in self.residual_readbacks.items()
            if readback["asset_entity_id"] == entity_id
        ]
        residual_readbacks.sort(
            key=lambda item: (item["readback"]["recorded_at"], item["readback"]["id"])
        )
        claim_ids = {item["claim"]["id"] for item in claims}
        links = [
            deepcopy(link) for link in self.evidence_links.values() if link["claim_id"] in claim_ids
        ]
        frame_ids = sorted({item["observer_frame_id"] for item in observations})
        artifact_ids = sorted(
            {item["source_artifact_id"] for item in observations}
            | {item["evidence_id"] for item in links}
        )
        dependency_group_ids = {
            item["dependency_group"] for item in links if item["dependency_group"]
        }
        dependencies = [
            deepcopy(dependency)
            for dependency in self.dependencies.values()
            if dependency["dependency_group_id"] in dependency_group_ids
        ]
        dependencies.sort(key=lambda item: (item["declared_at"], item["id"]))
        return {
            "entity": deepcopy(self.entities[entity_id]),
            "tracked_asset": deepcopy(self.assets[entity_id]),
            "observations": observations,
            "claims": claims,
            "relations": relations,
            "resolution_candidates": resolution_candidates,
            "cartographic_query_plans": cartographic_query_plans,
            "multi_fitter_runs": multi_fitter_runs,
            "hypotheses": hypotheses,
            "belief_revisions": belief_revisions,
            "scenarios": scenarios,
            "discrimination_plans": discrimination_plans,
            "forecast_evaluation_designs": forecast_evaluation_designs,
            "forecast_baselines": forecast_baselines,
            "readback_selection_plans": readback_selection_plans,
            "forecast_residuals": forecast_residuals,
            "forecast_validity_assessments": forecast_validity_assessments,
            "forecast_fitter_specifications": forecast_fitter_specifications,
            "residual_readbacks": residual_readbacks,
            "evidence_dependencies": dependencies,
            "observer_frames": [deepcopy(self.frames[item]) for item in frame_ids],
            "evidence_manifests": [deepcopy(self.evidence[item]) for item in artifact_ids],
            "state_history": deepcopy(self.asset_versions[entity_id]),
            "authority_state": "NO_AUTHORITY",
        }

    def cartographic_surface_view(self, surface_id: str) -> dict[str, Any]:
        if surface_id not in self.cartographic_surfaces:
            raise ProjectionError(f"unknown cartographic surface: {surface_id}")
        surface = deepcopy(self.cartographic_surfaces[surface_id])
        return {
            "surface": surface,
            "ledger_recorded_at": self._cartographic_surface_recorded_at[surface_id],
            "observer_frames": [
                deepcopy(self.frames[frame_id]) for frame_id in surface["observer_frame_ids"]
            ],
            "coverage_state": "NOT_ESTABLISHED",
            "completeness_claim": "NOT_MADE",
            "validity_evaluation_state": "NOT_EVALUATED",
            "authority_state": "NO_AUTHORITY",
        }

    def cartographic_query_plan_view(self, query_id: str) -> dict[str, Any]:
        if query_id not in self.cartographic_query_plans:
            raise ProjectionError(f"unknown cartographic query plan: {query_id}")
        plan = deepcopy(self.cartographic_query_plans[query_id])
        cutoff_value = plan["reconstruction"]["epistemic_cutoff"]
        cutoff = self._parse_timestamp(cutoff_value) if cutoff_value else None
        surface_ids_recorded_after_cutoff = sorted(
            surface_id
            for surface_id in plan["surface_ids"]
            if cutoff
            and self._parse_timestamp(self._cartographic_surface_recorded_at[surface_id]) > cutoff
        )
        plan_recorded_after_cutoff = bool(
            cutoff
            and self._parse_timestamp(self._cartographic_query_recorded_at[query_id]) > cutoff
        )
        return {
            "plan": plan,
            "ledger_recorded_at": self._cartographic_query_recorded_at[query_id],
            "surfaces": [
                self.cartographic_surface_view(surface_id) for surface_id in plan["surface_ids"]
            ],
            "query_lens": {
                "hindsight_basis": "LEDGER_RECORDED_AT",
                "plan_recorded_after_cutoff": plan_recorded_after_cutoff,
                "surface_ids_recorded_after_cutoff": surface_ids_recorded_after_cutoff,
                "hindsight_in_query_lens": bool(
                    plan_recorded_after_cutoff or surface_ids_recorded_after_cutoff
                ),
            },
            "authority_state": "NO_AUTHORITY",
        }

    def execute_cartographic_query(self, query_id: str) -> dict[str, Any]:
        """Execute a persisted backward plan against only the local immutable ledger."""

        plan_view = self.cartographic_query_plan_view(query_id)
        plan = plan_view["plan"]
        reconstruction = plan["reconstruction"]
        cutoff_value = reconstruction["epistemic_cutoff"]
        data_projection = self
        if reconstruction["mode"] == "AS_KNOWN_THEN" and cutoff_value is not None:
            cutoff = self._parse_timestamp(cutoff_value)
            bounded_events = [
                event
                for event in self._events
                if self._parse_timestamp(event["occurred_at"]) <= cutoff
            ]
            data_projection = ReadinProjection.replay(bounded_events)

        result = data_projection._execute_cartographic_plan(
            plan,
            [self.cartographic_surfaces[item] for item in plan["surface_ids"]],
            {
                frame_id: self.frames[frame_id]
                for surface_id in plan["surface_ids"]
                for frame_id in self.cartographic_surfaces[surface_id]["observer_frame_ids"]
            },
        )
        result["query_plan_ledger_recorded_at"] = plan_view["ledger_recorded_at"]
        result["cartographic_surfaces"] = plan_view["surfaces"]
        result["query_lens"] = plan_view["query_lens"]
        return result

    def _execute_cartographic_plan(
        self,
        plan: dict[str, Any],
        surfaces: list[dict[str, Any]],
        lens_frames: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        asset_id = plan["asset_entity_id"]
        if asset_id not in self.assets:
            raise ProjectionError(
                "cartographic asset is absent from the selected epistemic reconstruction"
            )

        selected_frame_ids = {
            frame_id for surface in surfaces for frame_id in surface["observer_frame_ids"]
        }
        traversal = plan["traversal"]
        visited_entities = {asset_id}
        frontier = {asset_id}
        included_relation_ids: set[str] = set()

        for _ in range(traversal["max_relation_hops"]):
            selected_observation_ids = {
                observation_id
                for observation_id, observation in self.observations.items()
                if observation["observer_frame_id"] in selected_frame_ids
                and visited_entities.intersection(observation["subject_entities"])
            }
            selected_claim_ids = {
                claim_id
                for claim_id, claim in self.claims.items()
                if claim["subject"] in visited_entities
                and selected_observation_ids.intersection(claim["derived_from"])
            }
            traversed_relations = {
                relation_id
                for relation_id, relation in self.relations.items()
                if relation["source_entity"] in frontier
                and selected_claim_ids.intersection(relation["claims"])
            }
            included_relation_ids.update(traversed_relations)
            next_entities = {
                self.relations[relation_id]["target_entity"] for relation_id in traversed_relations
            } - visited_entities
            if not next_entities:
                break
            visited_entities.update(next_entities)
            frontier = next_entities

        selected_observation_ids = {
            observation_id
            for observation_id, observation in self.observations.items()
            if observation["observer_frame_id"] in selected_frame_ids
            and visited_entities.intersection(observation["subject_entities"])
        }
        selected_claim_ids = {
            claim_id
            for claim_id, claim in self.claims.items()
            if claim["subject"] in visited_entities
            and selected_observation_ids.intersection(claim["derived_from"])
        }
        selected_artifact_ids = {
            self.observations[observation_id]["source_artifact_id"]
            for observation_id in selected_observation_ids
        }

        claims: list[dict[str, Any]] = []
        linked_artifact_ids: set[str] = set()
        for claim_id in sorted(selected_claim_ids):
            claim_view = self.claim_view(claim_id)
            claim = claim_view["claim"]
            claim_view["surface_matched_observation_ids"] = sorted(
                selected_observation_ids.intersection(claim["derived_from"])
            )
            claim_view["outside_surface_derivation_observation_ids"] = sorted(
                set(claim["derived_from"]) - selected_observation_ids
            )
            claim_view["off_surface_evidence_link_ids"] = sorted(
                link["id"]
                for link in claim_view["evidence_links"]
                if link["evidence_id"] not in selected_artifact_ids
            )
            linked_artifact_ids.update(link["evidence_id"] for link in claim_view["evidence_links"])
            claims.append(claim_view)

        dependency_ids, dependency_artifact_ids = self._evidence_dependency_closure(
            selected_artifact_ids | linked_artifact_ids
        )
        known_blind_regions = sorted(
            {blind_region for surface in surfaces for blind_region in surface["blind_regions"]}
            | {
                blind_region
                for frame_id in selected_frame_ids
                for blind_region in lens_frames[frame_id]["known_blind_regions"]
            }
        )
        excluded_asset_observations = [
            observation_id
            for observation_id, observation in self.observations.items()
            if asset_id in observation["subject_entities"]
            and observation["observer_frame_id"] not in selected_frame_ids
        ]

        observations = [
            deepcopy(self.observations[item]) for item in sorted(selected_observation_ids)
        ]
        relations = [deepcopy(self.relations[item]) for item in sorted(included_relation_ids)]
        return {
            "query_plan": deepcopy(plan),
            "data_reconstruction": deepcopy(plan["reconstruction"]),
            "execution": {
                "state": "LOCAL_LEDGER_REPLAY",
                "read_only": True,
                "network_access": False,
                "prediction_state": "NOT_REQUESTED",
            },
            "aperture": {
                "selected_surface_count": len(surfaces),
                "selected_observer_frame_count": len(selected_frame_ids),
                "visited_entity_count": len(visited_entities),
                "included_observation_count": len(observations),
                "excluded_asset_observation_count": len(excluded_asset_observations),
                "excluded_asset_observation_ids": sorted(excluded_asset_observations),
                "coverage_state": "NOT_ESTABLISHED",
                "completeness_claim": "NOT_MADE",
            },
            "blind_regions": {
                "known": known_blind_regions,
                "uncharacterized_surface_ids": sorted(
                    surface["id"]
                    for surface in surfaces
                    if surface["blind_region_state"] == "NOT_CHARACTERIZED"
                ),
            },
            "entities": [deepcopy(self.entities[item]) for item in sorted(visited_entities)],
            "lens_observer_frames": [
                deepcopy(lens_frames[item]) for item in sorted(selected_frame_ids)
            ],
            "data_observer_frame_ids": sorted(selected_frame_ids.intersection(self.frames)),
            "observations": observations,
            "claims": claims,
            "relations": relations,
            "evidence_manifests": [
                deepcopy(self.evidence[item]) for item in sorted(dependency_artifact_ids)
            ],
            "surface_evidence_manifest_ids": sorted(selected_artifact_ids),
            "linked_or_dependency_evidence_manifest_ids": sorted(
                dependency_artifact_ids - selected_artifact_ids
            ),
            "evidence_dependencies": [
                deepcopy(self.dependencies[item]) for item in sorted(dependency_ids)
            ],
            "missingness_policy": "PRESERVE",
            "conflict_policy": "PRESERVE",
            "surface_validity_evaluation_state": "NOT_EVALUATED",
            "authority_state": "NO_AUTHORITY",
        }

    def _evidence_dependency_closure(
        self, seed_artifact_ids: set[str]
    ) -> tuple[set[str], set[str]]:
        artifact_ids = set(seed_artifact_ids)
        dependency_ids: set[str] = set()
        changed = True
        while changed:
            changed = False
            for dependency_id, dependency in self.dependencies.items():
                endpoints = {
                    dependency["ancestor_evidence_id"],
                    dependency["descendant_evidence_id"],
                }
                if artifact_ids.intersection(endpoints) and (
                    dependency_id not in dependency_ids or not endpoints <= artifact_ids
                ):
                    dependency_ids.add(dependency_id)
                    artifact_ids.update(endpoints)
                    changed = True
        return dependency_ids, artifact_ids

    def fitter_view(self, fitter_id: str) -> dict[str, Any]:
        if fitter_id not in self.fitters:
            raise ProjectionError(f"unknown fitter: {fitter_id}")
        runs = [
            self.fitter_run_view(run_id)
            for run_id, run in self.fitter_runs.items()
            if run["fitter_id"] == fitter_id
        ]
        runs.sort(key=lambda item: (item["run"]["recorded_at"], item["run"]["id"]))
        return {
            "descriptor": deepcopy(self.fitters[fitter_id]),
            "ledger_recorded_at": self._fitter_recorded_at[fitter_id],
            "runs": runs,
            "empirical_validity_state": "NOT_ESTABLISHED",
            "authority_state": "NO_AUTHORITY",
        }

    def fitter_run_view(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.fitter_runs:
            raise ProjectionError(f"unknown fitter run: {run_id}")
        run = deepcopy(self.fitter_runs[run_id])
        return {
            "run": run,
            "descriptor": deepcopy(self.fitters[run["fitter_id"]]),
            "prediction_state": "NOT_REQUESTED",
            "residual_readback_state": "NOT_PERFORMED",
            "authority_state": "NO_AUTHORITY",
        }

    def multi_fitter_run_view(self, run_group_id: str) -> dict[str, Any]:
        if run_group_id not in self._fitter_run_groups:
            raise ProjectionError(f"unknown multi-fitter run group: {run_group_id}")
        group = deepcopy(self._fitter_run_groups[run_group_id])
        runs = [
            self.fitter_run_view(run_id)
            for run_id, run in self.fitter_runs.items()
            if run["run_group_id"] == run_group_id
        ]
        runs.sort(
            key=lambda item: (
                item["descriptor"]["fitter_class"],
                item["run"]["fitter_id"],
            )
        )
        fit_results = [item["run"]["fit_result"] for item in runs if item["run"]["fit_result"]]
        outcomes = [item["run"]["outcome"] for item in runs]
        completed_fitter_ids = sorted(item["run"]["fitter_id"] for item in runs)
        requested_fitter_ids = group["requested_fitter_ids"]
        missing_fitter_ids = sorted(set(requested_fitter_ids) - set(completed_fitter_ids))
        target_metrics = sorted({item["target_metric"] for item in fit_results})
        signals: list[str] = []
        if "INVALID" in outcomes:
            signals.append("MODEL_INVALIDITY_PRESENT")
        if "ABSTAINED" in outcomes:
            signals.append("ABSTENTION_PRESENT")
        if len(target_metrics) > 1:
            signals.append("OUTPUTS_INCOMMENSURATE")
        if not fit_results:
            signals.append("NO_ADMISSIBLE_RESULT")
        if not signals:
            signals.append("COMPARABLE_RESULTS_RETAINED")
        return {
            "run_group_id": run_group_id,
            "query_plan_id": group["query_plan_id"],
            "asset_entity_id": group["asset_entity_id"],
            "asset_state_version": group["asset_state_version"],
            "input_snapshot_sha256": group["input_snapshot_sha256"],
            "requested_fitter_ids": requested_fitter_ids,
            "completed_fitter_ids": completed_fitter_ids,
            "missing_fitter_ids": missing_fitter_ids,
            "completion_state": "PARTIAL" if missing_fitter_ids else "COMPLETE",
            "recorded_at": min(item["run"]["recorded_at"] for item in runs),
            "runs": runs,
            "outcome_counts": {
                "FIT": outcomes.count("FIT"),
                "ABSTAINED": outcomes.count("ABSTAINED"),
                "INVALID": outcomes.count("INVALID"),
            },
            "disagreement": {
                "primary_status": signals[0],
                "signals": signals,
                "target_metrics": target_metrics,
                "comparison_state": (
                    "NOT_COMPARABLE" if len(target_metrics) > 1 else "BOUNDED_COMPARISON_ONLY"
                ),
            },
            "consensus": {
                "state": "NOT_COMPUTED",
                "averaging_performed": False,
                "privileged_fitter_id": None,
            },
            "empirical_validity_state": "NOT_ESTABLISHED",
            "prediction_state": "NOT_REQUESTED",
            "residual_readback_state": "NOT_PERFORMED",
            "authority_state": "NO_AUTHORITY",
        }

    def hypothesis_view(self, hypothesis_id: str) -> dict[str, Any]:
        if hypothesis_id not in self.hypotheses:
            raise ProjectionError(f"unknown hypothesis: {hypothesis_id}")
        hypothesis = deepcopy(self.hypotheses[hypothesis_id])
        incoming = [
            deepcopy(edge)
            for edge in self.belief_edges.values()
            if edge["target_hypothesis_id"] == hypothesis_id
        ]
        outgoing = [
            deepcopy(edge)
            for edge in self.belief_edges.values()
            if edge["source_hypothesis_id"] == hypothesis_id
        ]
        incoming.sort(key=lambda item: item["id"])
        outgoing.sort(key=lambda item: item["id"])
        latest_revision_id = self._latest_belief_revision.get(hypothesis["asset_entity_id"])
        latest_result = None
        if latest_revision_id is not None:
            latest_result = next(
                (
                    deepcopy(item)
                    for item in self.belief_revisions[latest_revision_id]["node_results"]
                    if item["hypothesis_id"] == hypothesis_id
                ),
                None,
            )
        return {
            "hypothesis": hypothesis,
            "incoming_edges": incoming,
            "outgoing_edges": outgoing,
            "latest_belief_revision_id": latest_revision_id,
            "latest_result": latest_result,
            "probability_state": "NOT_COMPUTED",
            "authority_state": "NO_AUTHORITY",
        }

    def belief_revision_view(self, revision_id: str) -> dict[str, Any]:
        if revision_id not in self.belief_revisions:
            raise ProjectionError(f"unknown belief revision: {revision_id}")
        return {
            "revision": deepcopy(self.belief_revisions[revision_id]),
            "dependency_policy": "GROUP_BY_DECLARED_ANCESTRY",
            "interpretation": "DIAGNOSTIC_SIGNAL_BALANCE_NOT_TRUTH_PROBABILITY",
            "probability_state": "NOT_COMPUTED",
            "prediction_state": "NOT_REQUESTED",
            "authority_state": "NO_AUTHORITY",
        }

    def scenario_view(self, scenario_id: str) -> dict[str, Any]:
        if scenario_id not in self.scenarios:
            raise ProjectionError(f"unknown scenario: {scenario_id}")
        run_id = self._latest_scenario_run.get(scenario_id)
        return {
            "scenario": deepcopy(self.scenarios[scenario_id]),
            "run": self.scenario_run_view(run_id)["run"] if run_id is not None else None,
            "unknown_branch_visible": any(
                item["kind"] == "UNKNOWN_UNMODELED"
                for item in self.scenarios[scenario_id]["branches"]
            ),
            "likelihood_state": "NOT_COMPUTED",
            "trajectory_state": "NOT_SIMULATED",
            "prediction_state": "NOT_REQUESTED",
            "authority_state": "NO_AUTHORITY",
        }

    def scenario_run_view(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.scenario_runs:
            raise ProjectionError(f"unknown scenario run: {run_id}")
        run = deepcopy(self.scenario_runs[run_id])
        return {
            "run": run,
            "scenario": deepcopy(self.scenarios[run["scenario_id"]]),
            "likelihood_state": "NOT_COMPUTED",
            "trajectory_state": "NOT_SIMULATED",
            "prediction_state": "NOT_REQUESTED",
            "authority_state": "NO_AUTHORITY",
        }

    def discrimination_plan_view(self, plan_id: str) -> dict[str, Any]:
        if plan_id not in self.discrimination_plans:
            raise ProjectionError(f"unknown discrimination plan: {plan_id}")
        run_id = self._latest_discrimination_run.get(plan_id)
        return {
            "plan": deepcopy(self.discrimination_plans[plan_id]),
            "run": (deepcopy(self.discrimination_runs[run_id]) if run_id is not None else None),
            "collection_state": "NOT_STARTED",
            "acquisition_state": "NOT_ATTEMPTED",
            "source_independence_state": "NOT_ESTABLISHED",
            "expected_information_gain_state": "NOT_COMPUTED",
            "probability_state": "NOT_COMPUTED",
            "authority_state": "NO_AUTHORITY",
        }

    def discrimination_run_view(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.discrimination_runs:
            raise ProjectionError(f"unknown discrimination run: {run_id}")
        run = deepcopy(self.discrimination_runs[run_id])
        return {
            "run": run,
            "plan": deepcopy(self.discrimination_plans[run["plan_id"]]),
            "collection_state": "NOT_STARTED",
            "acquisition_state": "NOT_ATTEMPTED",
            "source_independence_state": "NOT_ESTABLISHED",
            "expected_information_gain_state": "NOT_COMPUTED",
            "probability_state": "NOT_COMPUTED",
            "authority_state": "NO_AUTHORITY",
        }

    def residual_readback_view(self, readback_id: str) -> dict[str, Any]:
        if readback_id not in self.residual_readbacks:
            raise ProjectionError(f"unknown residual readback: {readback_id}")
        readback = deepcopy(self.residual_readbacks[readback_id])
        scenario_run = deepcopy(self.scenario_runs[readback["scenario_run_id"]])
        return {
            "readback": readback,
            "scenario_run": scenario_run,
            "scenario": deepcopy(self.scenarios[scenario_run["scenario_id"]]),
            "forecast_evaluation_design": self.forecast_evaluation_design_view(
                readback["execution_receipt"]["forecast_evaluation_design_id"]
            )["design"],
            "observations": [
                deepcopy(self.observations[item]) for item in readback["observation_ids"]
            ],
            "forecast_baseline_state": "NOT_AVAILABLE",
            "residual_state": "NOT_COMPUTED",
            "validity_update_state": "NOT_APPLIED",
            "weighting_update_state": "NOT_APPLIED",
            "future_admissibility_update_state": "NOT_APPLIED",
            "learning_state": "NOT_STARTED",
            "authority_state": "NO_AUTHORITY",
        }

    def forecast_evaluation_design_view(self, design_id: str) -> dict[str, Any]:
        if design_id not in self.forecast_evaluation_designs:
            raise ProjectionError(f"unknown forecast evaluation design: {design_id}")
        design = deepcopy(self.forecast_evaluation_designs[design_id])
        scenario = deepcopy(self.scenarios[design["scenario_id"]])
        run_id = self._latest_scenario_run.get(design["scenario_id"])
        baseline_id = self._design_forecast_baseline.get(design_id)
        baseline = (
            deepcopy(self.forecast_baselines[baseline_id]) if baseline_id is not None else None
        )
        return {
            "design": design,
            "scenario": scenario,
            "scenario_run": (deepcopy(self.scenario_runs[run_id]) if run_id is not None else None),
            "forecast_baseline": baseline,
            "forecast_capable_fitter_state": "NO_ELIGIBLE_FITTER_REGISTERED",
            "eligible_fitter_ids": [],
            "forecast_baseline_state": "COMPLETED" if baseline is not None else "NOT_STARTED",
            "forecast_execution_state": (
                baseline["forecast_execution_state"] if baseline is not None else "NOT_STARTED"
            ),
            "prediction_state": (
                baseline["prediction"]["prediction_state"]
                if baseline is not None
                else "NOT_PRODUCED"
            ),
            "calibration_state": "NOT_ESTABLISHED",
            "authority_state": "NO_AUTHORITY",
        }

    def forecast_baseline_view(self, baseline_id: str) -> dict[str, Any]:
        if baseline_id not in self.forecast_baselines:
            raise ProjectionError(f"unknown forecast baseline: {baseline_id}")
        baseline = deepcopy(self.forecast_baselines[baseline_id])
        return {
            "baseline": baseline,
            "forecast_evaluation_design": deepcopy(
                self.forecast_evaluation_designs[baseline["forecast_evaluation_design_id"]]
            ),
            "scenario": deepcopy(self.scenarios[baseline["scenario_id"]]),
            "residual_scoring_state": "NOT_ENABLED",
            "calibration_state": "NOT_ESTABLISHED",
            "empirical_validity_state": "NOT_ESTABLISHED",
            "authority_state": "NO_AUTHORITY",
        }

    def readback_selection_plan_view(self, plan_id: str) -> dict[str, Any]:
        if plan_id not in self.readback_selection_plans:
            raise ProjectionError(f"unknown readback selection plan: {plan_id}")
        plan = deepcopy(self.readback_selection_plans[plan_id])
        run_id = self._plan_readback_selection_run.get(plan_id)
        return {
            "plan": plan,
            "run": (deepcopy(self.readback_selection_runs[run_id]) if run_id is not None else None),
            "forecast_baseline": deepcopy(self.forecast_baselines[plan["forecast_baseline_id"]]),
            "forecast_evaluation_design": deepcopy(
                self.forecast_evaluation_designs[plan["forecast_evaluation_design_id"]]
            ),
            "eligible_observer_frames": [
                deepcopy(self.frames[item]) for item in plan["eligible_observer_frame_ids"]
            ],
            "residual_scoring_state": "NOT_ENABLED",
            "authority_state": "NO_AUTHORITY",
        }

    def readback_selection_run_view(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.readback_selection_runs:
            raise ProjectionError(f"unknown readback selection run: {run_id}")
        run = deepcopy(self.readback_selection_runs[run_id])
        view = self.readback_selection_plan_view(run["readback_selection_plan_id"])
        return {
            "run": run,
            "plan": view["plan"],
            "forecast_baseline": view["forecast_baseline"],
            "forecast_evaluation_design": view["forecast_evaluation_design"],
            "eligible_observer_frames": view["eligible_observer_frames"],
            "selected_observation": (
                deepcopy(self.observations[run["selected_observation_id"]])
                if run["selected_observation_id"] is not None
                else None
            ),
            "residual_scoring_state": "NOT_ENABLED",
            "authority_state": "NO_AUTHORITY",
        }

    def forecast_residual_view(self, forecast_residual_id: str) -> dict[str, Any]:
        if forecast_residual_id not in self.forecast_residuals:
            raise ProjectionError(f"unknown forecast residual: {forecast_residual_id}")
        result = deepcopy(self.forecast_residuals[forecast_residual_id])
        selection_run = deepcopy(self.readback_selection_runs[result["readback_selection_run_id"]])
        plan = deepcopy(self.readback_selection_plans[result["readback_selection_plan_id"]])
        observation = deepcopy(self.observations[result["selected_observation_id"]])
        return {
            "forecast_residual": result,
            "readback_selection_run": selection_run,
            "readback_selection_plan": plan,
            "forecast_baseline": deepcopy(self.forecast_baselines[result["forecast_baseline_id"]]),
            "forecast_evaluation_design": deepcopy(
                self.forecast_evaluation_designs[result["forecast_evaluation_design_id"]]
            ),
            "scenario": deepcopy(self.scenarios[result["scenario_id"]]),
            "selected_observation": observation,
            "selected_observer_frame": deepcopy(self.frames[observation["observer_frame_id"]]),
            "selected_evidence_manifest": deepcopy(
                self.evidence[observation["source_artifact_id"]]
            ),
            "calibration_state": "NOT_ESTABLISHED",
            "empirical_validity_state": "NOT_ESTABLISHED",
            "authority_state": "NO_AUTHORITY",
        }

    def forecast_validity_assessment_view(
        self, forecast_validity_assessment_id: str
    ) -> dict[str, Any]:
        if forecast_validity_assessment_id not in self.forecast_validity_assessments:
            raise ProjectionError(
                f"unknown forecast validity assessment: {forecast_validity_assessment_id}"
            )
        assessment = deepcopy(self.forecast_validity_assessments[forecast_validity_assessment_id])
        residual = deepcopy(self.forecast_residuals[assessment["forecast_residual_id"]])
        return {
            "forecast_validity_assessment": assessment,
            "forecast_residual": residual,
            "readback_selection_run": deepcopy(
                self.readback_selection_runs[assessment["readback_selection_run_id"]]
            ),
            "forecast_baseline": deepcopy(
                self.forecast_baselines[assessment["forecast_baseline_id"]]
            ),
            "forecast_evaluation_design": deepcopy(
                self.forecast_evaluation_designs[assessment["forecast_evaluation_design_id"]]
            ),
            "scenario": deepcopy(self.scenarios[assessment["scenario_id"]]),
            "validity_update_state": "NOT_APPLIED",
            "learning_state": "NOT_STARTED",
            "authority_state": "NO_AUTHORITY",
        }

    def forecast_fitter_specification_view(self, specification_id: str) -> dict[str, Any]:
        if specification_id not in self.forecast_fitter_specifications:
            raise ProjectionError(f"unknown forecast fitter specification: {specification_id}")
        specification = deepcopy(self.forecast_fitter_specifications[specification_id])
        earlier_assessment_ids = sorted(
            assessment["id"]
            for assessment in self.forecast_validity_assessments.values()
            if assessment["asset_entity_id"] == specification["asset_entity_id"]
            and self._parse_timestamp(assessment["recorded_at"])
            <= self._parse_timestamp(specification["registered_at"])
        )
        return {
            "specification": specification,
            "earlier_validity_assessment_ids": earlier_assessment_ids,
            "retroactive_effect_state": "NONE",
            "training_state": "NOT_STARTED",
            "execution_state": "NOT_ENABLED",
            "authority_state": "NO_AUTHORITY",
        }

    def resolution_candidate_view(self, candidate_id: str) -> dict[str, Any]:
        if candidate_id not in self.resolution_candidates:
            raise ProjectionError(f"unknown resolution candidate: {candidate_id}")
        candidate = deepcopy(self.resolution_candidates[candidate_id])
        current_assessment_id = self._latest_resolution_assessment.get(candidate_id)
        assessment_lineage: list[dict[str, Any]] = []
        lineage_id = current_assessment_id
        while lineage_id is not None:
            assessment = self.resolution_assessments[lineage_id]
            assessment_lineage.append(deepcopy(assessment))
            lineage_id = assessment["supersedes_assessment_id"]
        assessments = list(reversed(assessment_lineage))
        current_assessment = (
            deepcopy(self.resolution_assessments[current_assessment_id])
            if current_assessment_id
            else None
        )
        return {
            "candidate": candidate,
            "assessments": assessments,
            "current_disposition": (
                current_assessment["disposition"] if current_assessment else "PENDING_REVIEW"
            ),
            "current_assessment": current_assessment,
            "reversible": True,
            "automatic_merge": False,
            "merge_state": "NOT_MERGED",
            "authority_state": "NO_AUTHORITY",
        }

    def claim_view(self, claim_id: str) -> dict[str, Any]:
        if claim_id not in self.claims:
            raise ProjectionError(f"unknown claim: {claim_id}")
        claim = deepcopy(self.claims[claim_id])
        links = [
            deepcopy(link) for link in self.evidence_links.values() if link["claim_id"] == claim_id
        ]
        links.sort(key=lambda item: (item["created_at"], item["id"]))
        role_counts: dict[str, int] = {}
        for link in links:
            role_counts[link["role"]] = role_counts.get(link["role"], 0) + 1
        dependency_groups = sorted(
            {link["dependency_group"] for link in links if link["dependency_group"] is not None}
        )
        return {
            "claim": claim,
            "evidence_links": links,
            "evidence_role_counts": role_counts,
            "dependency_groups": dependency_groups,
            "ungrouped_evidence_link_count": sum(
                link["dependency_group"] is None for link in links
            ),
            "independence_status": (
                "DEPENDENT_EVIDENCE_PRESENT"
                if dependency_groups
                else "INDEPENDENCE_NOT_ESTABLISHED"
            ),
            "epistemic_status": claim["epistemic_status"],
            "authority_state": "NO_AUTHORITY",
        }

    def timeline_view(
        self,
        entity_id: str,
        *,
        epistemic_cutoff: str | None = None,
        mode: str = "AS_KNOWN_THEN",
    ) -> dict[str, Any]:
        if entity_id not in self.assets:
            raise ProjectionError(f"unknown tracked asset: {entity_id}")
        if mode not in {"AS_KNOWN_THEN", "AS_RECONSTRUCTED_NOW"}:
            raise ProjectionError(f"unsupported reconstruction mode: {mode}")
        cutoff = self._parse_timestamp(epistemic_cutoff) if epistemic_cutoff else None

        entries: list[dict[str, Any]] = []
        versions = {item["state_version"] for item in self.asset_versions[entity_id]}
        for index, event in enumerate(self._events):
            if entity_id not in self._event_entities(event):
                continue
            recorded_at = self._parse_timestamp(event["occurred_at"])
            if cutoff and mode == "AS_KNOWN_THEN" and recorded_at > cutoff:
                continue
            entries.append(
                {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "recorded_at": event["occurred_at"],
                    "effective_at": self._effective_time(event),
                    "state_version": event["event_id"] if event["event_id"] in versions else None,
                    "hindsight": bool(cutoff and recorded_at > cutoff),
                    "ledger_order": index,
                    "authority_state": "NO_AUTHORITY",
                }
            )
        entries.sort(key=lambda item: (item["effective_at"], item["ledger_order"]))
        return {
            "entity_id": entity_id,
            "mode": mode,
            "epistemic_cutoff": epistemic_cutoff,
            "entries": entries,
            "hindsight_included": any(item["hindsight"] for item in entries),
            "authority_state": "NO_AUTHORITY",
        }

    def asset_view_at(
        self,
        entity_id: str,
        *,
        epistemic_cutoff: str | None = None,
        mode: str = "AS_KNOWN_THEN",
    ) -> dict[str, Any]:
        if mode not in {"AS_KNOWN_THEN", "AS_RECONSTRUCTED_NOW"}:
            raise ProjectionError(f"unsupported reconstruction mode: {mode}")
        if mode == "AS_KNOWN_THEN" and epistemic_cutoff:
            cutoff = self._parse_timestamp(epistemic_cutoff)
            events = [
                event
                for event in self._events
                if self._parse_timestamp(event["occurred_at"]) <= cutoff
            ]
            bounded = ReadinProjection.replay(events)
            view = bounded.asset_view(entity_id)
            timeline = bounded.timeline_view(
                entity_id, mode=mode, epistemic_cutoff=epistemic_cutoff
            )
        else:
            view = self.asset_view(entity_id)
            timeline = self.timeline_view(entity_id, mode=mode, epistemic_cutoff=epistemic_cutoff)
        view["reconstruction"] = {
            "mode": mode,
            "epistemic_cutoff": epistemic_cutoff,
            "hindsight_included": timeline["hindsight_included"],
        }
        view["timeline"] = timeline["entries"]
        return view

    def _event_entities(self, event: dict[str, Any]) -> set[str]:
        event_type = event["event_type"]
        payload = event["payload"]
        if event_type == "entity.created":
            return {payload["entity"]["id"]}
        if event_type == "asset.tracking_started":
            return {payload["tracked_asset"]["entity_id"]}
        if event_type == "observation.admitted":
            return set(payload["observation"]["subject_entities"])
        if event_type == "claim.created":
            return {payload["claim"]["subject"]}
        if event_type == "relation.created":
            relation = payload["relation"]
            return {relation["source_entity"], relation["target_entity"]}
        if event_type == "entity.resolution_candidate_recorded":
            candidate = payload["resolution_candidate"]
            return {candidate["left_entity_id"], candidate["right_entity_id"]}
        if event_type == "entity.resolution_candidate_assessed":
            candidate_id = payload["resolution_assessment"]["candidate_id"]
            if candidate_id not in self.resolution_candidates:
                return set()
            candidate = self.resolution_candidates[candidate_id]
            return {candidate["left_entity_id"], candidate["right_entity_id"]}
        if event_type == "cartography.query_planned":
            return {payload["cartographic_query_plan"]["asset_entity_id"]}
        if event_type == "cartography.surface_registered":
            surface_id = payload["cartographic_surface"]["id"]
            return {
                plan["asset_entity_id"]
                for plan in self.cartographic_query_plans.values()
                if surface_id in plan["surface_ids"]
            }
        if event_type == "fitter.run_completed":
            query_id = payload["fitter_run"]["query_plan_id"]
            if query_id not in self.cartographic_query_plans:
                return set()
            return {self.cartographic_query_plans[query_id]["asset_entity_id"]}
        if event_type == "hypothesis.created":
            hypothesis = payload["hypothesis"]
            return {hypothesis["asset_entity_id"], *hypothesis["target_entity_ids"]}
        if event_type == "belief.edge_created":
            source_id = payload["belief_edge"]["source_hypothesis_id"]
            if source_id not in self.hypotheses:
                return set()
            return {self.hypotheses[source_id]["asset_entity_id"]}
        if event_type == "belief.revision_completed":
            return {payload["belief_revision"]["asset_entity_id"]}
        if event_type == "scenario.created":
            scenario = payload["scenario"]
            return {scenario["asset_entity_id"], *scenario["target_entity_ids"]}
        if event_type == "scenario.run_completed":
            return {payload["scenario_run"]["asset_entity_id"]}
        if event_type == "collection.discrimination_plan_created":
            return {payload["discrimination_plan"]["asset_entity_id"]}
        if event_type == "collection.discrimination_run_completed":
            return {payload["discrimination_run"]["asset_entity_id"]}
        if event_type == "forecast.evaluation_design_created":
            return {payload["forecast_evaluation_design"]["asset_entity_id"]}
        if event_type == "forecast.baseline_completed":
            return {payload["forecast_baseline"]["asset_entity_id"]}
        if event_type == "forecast.readback_selection_plan_created":
            return {payload["readback_selection_plan"]["asset_entity_id"]}
        if event_type == "forecast.readback_selection_completed":
            return {payload["readback_selection_run"]["asset_entity_id"]}
        if event_type == "forecast.residual_computed":
            return {payload["forecast_residual"]["asset_entity_id"]}
        if event_type == "forecast.validity_update_assessed":
            return {payload["forecast_validity_assessment"]["asset_entity_id"]}
        if event_type == "forecast.fitter_specification_registered":
            return {payload["forecast_fitter_specification"]["asset_entity_id"]}
        if event_type == "residual.readback_completed":
            return {payload["residual_readback"]["asset_entity_id"]}
        if event_type == "evidence.linked":
            claim_id = payload["evidence_link"]["claim_id"]
            return {self.claims[claim_id]["subject"]} if claim_id in self.claims else set()
        if event_type == "evidence.dependency_declared":
            dependency = payload["dependency"]
            return self._assets_for_evidence(
                {dependency["ancestor_evidence_id"], dependency["descendant_evidence_id"]}
            )
        return set()

    def _effective_time(self, event: dict[str, Any]) -> str:
        event_type = event["event_type"]
        if event_type == "observation.admitted":
            return event["payload"]["observation"]["observed_at"]
        if event_type == "claim.created":
            claim = event["payload"]["claim"]
            return claim["temporal_scope"]["valid_from"] or claim["created_at"]
        if event_type == "relation.created":
            relation = event["payload"]["relation"]
            return relation["valid_from"] or relation["created_at"]
        if event_type == "evidence.dependency_declared":
            return event["payload"]["dependency"]["declared_at"]
        if event_type == "evidence.linked":
            return event["payload"]["evidence_link"]["created_at"]
        if event_type == "entity.resolution_candidate_recorded":
            return event["payload"]["resolution_candidate"]["recorded_at"]
        if event_type == "entity.resolution_candidate_assessed":
            return event["payload"]["resolution_assessment"]["assessed_at"]
        if event_type == "cartography.surface_registered":
            return event["payload"]["cartographic_surface"]["registered_at"]
        if event_type == "cartography.query_planned":
            return event["payload"]["cartographic_query_plan"]["created_at"]
        if event_type == "fitter.registered":
            return event["payload"]["fitter_descriptor"]["registered_at"]
        if event_type == "fitter.run_completed":
            return event["payload"]["fitter_run"]["recorded_at"]
        if event_type == "hypothesis.created":
            return event["payload"]["hypothesis"]["created_at"]
        if event_type == "belief.edge_created":
            return event["payload"]["belief_edge"]["created_at"]
        if event_type == "belief.revision_completed":
            return event["payload"]["belief_revision"]["recorded_at"]
        if event_type == "scenario.created":
            return event["payload"]["scenario"]["created_at"]
        if event_type == "scenario.run_completed":
            return event["payload"]["scenario_run"]["recorded_at"]
        if event_type == "collection.discrimination_plan_created":
            return event["payload"]["discrimination_plan"]["created_at"]
        if event_type == "collection.discrimination_run_completed":
            return event["payload"]["discrimination_run"]["recorded_at"]
        if event_type == "forecast.evaluation_design_created":
            return event["payload"]["forecast_evaluation_design"]["created_at"]
        if event_type == "forecast.baseline_completed":
            return event["payload"]["forecast_baseline"]["recorded_at"]
        if event_type == "forecast.readback_selection_plan_created":
            return event["payload"]["readback_selection_plan"]["created_at"]
        if event_type == "forecast.readback_selection_completed":
            return event["payload"]["readback_selection_run"]["recorded_at"]
        if event_type == "forecast.residual_computed":
            return event["payload"]["forecast_residual"]["recorded_at"]
        if event_type == "forecast.validity_update_assessed":
            return event["payload"]["forecast_validity_assessment"]["recorded_at"]
        if event_type == "forecast.fitter_specification_registered":
            return event["payload"]["forecast_fitter_specification"]["registered_at"]
        if event_type == "residual.readback_completed":
            return event["payload"]["residual_readback"]["recorded_at"]
        return event["occurred_at"]

    def _parse_timestamp(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def catalog_view(self) -> list[dict[str, Any]]:
        return [
            {
                "entity": deepcopy(self.entities[entity_id]),
                "tracked_asset": deepcopy(asset),
                "observation_count": sum(
                    entity_id in observation["subject_entities"]
                    for observation in self.observations.values()
                ),
                "claim_count": sum(entity_id == claim["subject"] for claim in self.claims.values()),
                "relation_count": sum(
                    entity_id in {relation["source_entity"], relation["target_entity"]}
                    for relation in self.relations.values()
                ),
                "resolution_candidate_count": sum(
                    entity_id in {candidate["left_entity_id"], candidate["right_entity_id"]}
                    for candidate in self.resolution_candidates.values()
                ),
                "cartographic_query_plan_count": sum(
                    entity_id == plan["asset_entity_id"]
                    for plan in self.cartographic_query_plans.values()
                ),
                "multi_fitter_run_group_count": sum(
                    entity_id == group["asset_entity_id"]
                    for group in self._fitter_run_groups.values()
                ),
                "fit_result_count": sum(
                    entity_id
                    == self.cartographic_query_plans[result["query_plan_id"]]["asset_entity_id"]
                    for result in self.fit_results.values()
                ),
                "hypothesis_count": sum(
                    entity_id == hypothesis["asset_entity_id"]
                    for hypothesis in self.hypotheses.values()
                ),
                "belief_revision_count": sum(
                    entity_id == revision["asset_entity_id"]
                    for revision in self.belief_revisions.values()
                ),
                "scenario_count": sum(
                    entity_id == scenario["asset_entity_id"] for scenario in self.scenarios.values()
                ),
                "scenario_run_count": sum(
                    entity_id == run["asset_entity_id"] for run in self.scenario_runs.values()
                ),
                "discrimination_plan_count": sum(
                    entity_id == plan["asset_entity_id"]
                    for plan in self.discrimination_plans.values()
                ),
                "discrimination_run_count": sum(
                    entity_id == run["asset_entity_id"] for run in self.discrimination_runs.values()
                ),
                "forecast_evaluation_design_count": sum(
                    entity_id == design["asset_entity_id"]
                    for design in self.forecast_evaluation_designs.values()
                ),
                "forecast_baseline_count": sum(
                    entity_id == baseline["asset_entity_id"]
                    for baseline in self.forecast_baselines.values()
                ),
                "readback_selection_plan_count": sum(
                    entity_id == plan["asset_entity_id"]
                    for plan in self.readback_selection_plans.values()
                ),
                "readback_selection_run_count": sum(
                    entity_id == run["asset_entity_id"]
                    for run in self.readback_selection_runs.values()
                ),
                "forecast_residual_count": sum(
                    entity_id == result["asset_entity_id"]
                    for result in self.forecast_residuals.values()
                ),
                "forecast_validity_assessment_count": sum(
                    entity_id == assessment["asset_entity_id"]
                    for assessment in self.forecast_validity_assessments.values()
                ),
                "forecast_fitter_specification_count": sum(
                    entity_id == specification["asset_entity_id"]
                    for specification in self.forecast_fitter_specifications.values()
                ),
                "residual_readback_count": sum(
                    entity_id == readback["asset_entity_id"]
                    for readback in self.residual_readbacks.values()
                ),
                "authority_state": "NO_AUTHORITY",
            }
            for entity_id, asset in sorted(self.assets.items())
        ]
