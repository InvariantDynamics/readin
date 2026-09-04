"""Validate the schema, Phase 8G fitter specification, and fail-closed vectors."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime

from jsonschema import Draft202012Validator

from readin.asset_catalog import (
    AssetCatalogContractError,
    build_asset_catalog_events,
    load_asset_catalog_source_schema,
    validate_asset_catalog_source,
)
from readin.contracts import ContractViolation, load_event_schema, validate_event
from readin.fitters import canonical_sha256
from readin.projection import ProjectionError, ReadinProjection
from readin.real_asset_cases import (
    RealAssetPolicyError,
    build_github_public_repository_policy,
    load_real_asset_policy_schema,
    validate_real_asset_case_policy,
)
from readin.residuals import ResidualRuntimeError, build_residual_snapshot
from readin.synthetic import phase8_events, phase8g_events
from readin.workbench import WorkbenchError, build_workbench_snapshot, validate_loopback_host


def _must_reject_contract(event: dict[str, object]) -> None:
    try:
        validate_event(event)
    except ContractViolation:
        return
    raise AssertionError("negative contract vector was accepted")


def _asset_catalog_source() -> dict[str, object]:
    return {
        "schema_version": "readin.asset-catalog-source.v0.1",
        "catalog_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "catalog_name": "Contract validation catalog",
        "declared_at": "2026-09-04T12:00:00Z",
        "owner": {
            "label": "Local operator",
            "attestation": "USER_ATTESTED_NOT_VERIFIED",
            "scope": "SELF_OR_CONTROLLED_ASSETS_ONLY",
        },
        "purpose": {
            "kind": "PERSONAL_ASSET_CATALOG",
            "statement": "Validate local asset-catalog onboarding without live collection.",
            "secondary_use": "PROHIBITED",
        },
        "authority": {
            "state": "NO_AUTHORITY",
            "collection": "NOT_GRANTED",
            "external_actions": "PROHIBITED",
            "credential_storage": "PROHIBITED",
            "network_access": False,
            "people_targeting": "PROHIBITED",
        },
        "source": {
            "kind": "USER_DECLARED_LOCAL_MANIFEST",
            "network_access": False,
            "credential_material": "ABSENT",
            "path_retention": "NOT_RECORDED_IN_LEDGER",
        },
        "assets": [
            {
                "asset_class": "SOCIAL_ACCOUNT",
                "display_name": "Example social account",
                "platform": "ExampleSocial",
                "account_identifier": "operator",
                "source_uri": "https://social.example/operator",
                "authorization_basis": "USER_OWNED_ACCOUNT_ATTESTED",
                "collection_mode": "API_CONNECTION_REQUIRES_SEPARATE_GRANT",
                "connector_intent": {
                    "connector_kind": "OAUTH_API",
                    "connection_state": "OAUTH_REQUIRED_NOT_REQUESTED",
                    "credential_state": "NONE",
                    "oauth_state": "NOT_REQUESTED",
                    "live_collection_state": "DISABLED",
                    "external_action_state": "PROHIBITED",
                    "terms_review_state": "REQUIRES_REVIEW",
                },
            }
        ],
    }


def main() -> None:
    schema = load_event_schema()
    Draft202012Validator.check_schema(schema)
    policy_schema = load_real_asset_policy_schema()
    Draft202012Validator.check_schema(policy_schema)
    asset_catalog_schema = load_asset_catalog_source_schema()
    Draft202012Validator.check_schema(asset_catalog_schema)
    asset_catalog_source = _asset_catalog_source()
    validate_asset_catalog_source(asset_catalog_source)
    promoted_catalog = deepcopy(asset_catalog_source)
    promoted_catalog["authority"]["network_access"] = True  # type: ignore[index]
    try:
        validate_asset_catalog_source(promoted_catalog)
    except AssetCatalogContractError:
        pass
    else:
        raise AssertionError("asset catalog source network promotion was accepted")
    connected_catalog = deepcopy(asset_catalog_source)
    connected_catalog["assets"][0]["connector_intent"]["connection_state"] = "OAUTH_CONNECTED"  # type: ignore[index]
    try:
        validate_asset_catalog_source(connected_catalog)
    except AssetCatalogContractError:
        pass
    else:
        raise AssertionError("asset catalog source accepted an OAuth-connected state")
    asset_catalog_events = build_asset_catalog_events(
        asset_catalog_source,
        source_sha256="0" * 64,
        source_size=1024,
    )
    for event in asset_catalog_events:
        validate_event(event)
    asset_catalog_projection = ReadinProjection.replay(asset_catalog_events)
    if len(asset_catalog_projection.assets) != 1:
        raise AssertionError("asset catalog source did not replay into a tracked asset")
    policy = build_github_public_repository_policy(
        "InvariantDynamics",
        "readin",
        "Validate the bounded public repository policy contract.",
        declared_at=datetime(2026, 9, 3, tzinfo=UTC),
    )
    validate_real_asset_case_policy(policy)
    promoted_policy = deepcopy(policy)
    promoted_policy["authority"]["collection"] = "UNRESTRICTED"
    try:
        validate_real_asset_case_policy(promoted_policy)
    except RealAssetPolicyError:
        pass
    else:
        raise AssertionError("real-asset policy authority promotion was accepted")
    events = phase8g_events()
    residual_events = phase8_events()
    for event in events:
        validate_event(event)
    for event in residual_events:
        validate_event(event)
    projection = ReadinProjection.replay(events)
    residual_projection = ReadinProjection.replay(residual_events)

    unknown_field = deepcopy(events[0])
    unknown_field["unexpected"] = True
    _must_reject_contract(unknown_field)

    invalid_authority = deepcopy(events[0])
    invalid_authority["authority_state"] = "EXECUTE_ACTION"
    _must_reject_contract(invalid_authority)

    invalid_merge = deepcopy(events[18])
    invalid_merge["payload"]["resolution_candidate"]["merge_state"] = "MERGED"
    _must_reject_contract(invalid_merge)

    invalid_belief_contract = deepcopy(events[34])
    invalid_belief_contract["payload"]["belief_revision"]["probability_state"] = "COMPUTED"
    _must_reject_contract(invalid_belief_contract)

    invalid_scenario_contract = deepcopy(events[35])
    invalid_scenario_contract["payload"]["scenario"]["prediction_state"] = "FORECAST"
    _must_reject_contract(invalid_scenario_contract)

    invalid_collection_contract = deepcopy(events[38])
    invalid_collection_contract["payload"]["discrimination_plan"]["collection_state"] = "STARTED"
    _must_reject_contract(invalid_collection_contract)

    invalid_discrimination_probability = deepcopy(events[39])
    invalid_discrimination_probability["payload"]["discrimination_run"]["probability_state"] = (
        "COMPUTED"
    )
    _must_reject_contract(invalid_discrimination_probability)

    invalid_forecast_contract = deepcopy(events[40])
    invalid_forecast_contract["payload"]["forecast_evaluation_design"]["prediction_state"] = (
        "PRODUCED"
    )
    _must_reject_contract(invalid_forecast_contract)

    invalid_leakage_contract = deepcopy(events[40])
    invalid_leakage_contract["payload"]["forecast_evaluation_design"]["timing"][
        "post_cutoff_input_policy"
    ] = "INCLUDE"
    _must_reject_contract(invalid_leakage_contract)

    invalid_baseline_scoring = deepcopy(events[41])
    invalid_baseline_scoring["payload"]["forecast_baseline"]["residual_scoring_state"] = "ENABLED"
    _must_reject_contract(invalid_baseline_scoring)

    invalid_baseline_calibration = deepcopy(events[41])
    invalid_baseline_calibration["payload"]["forecast_baseline"]["calibration_state"] = (
        "ESTABLISHED"
    )
    _must_reject_contract(invalid_baseline_calibration)

    invalid_baseline_input = deepcopy(events[41])
    invalid_baseline_input["payload"]["forecast_baseline"]["input_boundary"][
        "selected_input_observation_ids"
    ] = ["44444444-4444-4444-8444-444444444444"]
    _must_reject_contract(invalid_baseline_input)

    invalid_residual_contract = deepcopy(residual_events[43])
    invalid_residual_contract["payload"]["residual_readback"]["residual_state"] = "COMPUTED"
    _must_reject_contract(invalid_residual_contract)

    invalid_validity_update = deepcopy(residual_events[43])
    invalid_validity_update["payload"]["residual_readback"]["validity_update_state"] = "APPLIED"
    _must_reject_contract(invalid_validity_update)

    invalid_selection_aggregation = deepcopy(events[42])
    invalid_selection_aggregation["payload"]["readback_selection_plan"]["selection_policy"][
        "aggregation_policy"
    ] = "AVERAGE"
    _must_reject_contract(invalid_selection_aggregation)

    invalid_selection_scoring = deepcopy(events[45])
    invalid_selection_scoring["payload"]["readback_selection_run"]["residual_state"] = "COMPUTED"
    _must_reject_contract(invalid_selection_scoring)

    invalid_selection_network = deepcopy(events[45])
    invalid_selection_network["payload"]["readback_selection_run"]["execution_receipt"][
        "network_access"
    ] = True
    _must_reject_contract(invalid_selection_network)

    invalid_forecast_residual_calibration = deepcopy(events[46])
    invalid_forecast_residual_calibration["payload"]["forecast_residual"]["calibration_state"] = (
        "ESTABLISHED"
    )
    _must_reject_contract(invalid_forecast_residual_calibration)

    invalid_forecast_residual_validity = deepcopy(events[46])
    invalid_forecast_residual_validity["payload"]["forecast_residual"]["validity_update_state"] = (
        "APPLIED"
    )
    _must_reject_contract(invalid_forecast_residual_validity)

    invalid_forecast_residual_unit = deepcopy(events[46])
    invalid_forecast_residual_unit["payload"]["forecast_residual"]["score"]["unit_match_state"] = (
        "VERIFIED"
    )
    _must_reject_contract(invalid_forecast_residual_unit)

    invalid_forecast_residual_network = deepcopy(events[46])
    invalid_forecast_residual_network["payload"]["forecast_residual"]["execution_receipt"][
        "network_access"
    ] = True
    _must_reject_contract(invalid_forecast_residual_network)

    invalid_forecast_validity_update = deepcopy(events[47])
    invalid_forecast_validity_update["payload"]["forecast_validity_assessment"][
        "validity_update_state"
    ] = "APPLIED"
    _must_reject_contract(invalid_forecast_validity_update)

    invalid_forecast_validity_fitter = deepcopy(events[47])
    invalid_forecast_validity_fitter["payload"]["forecast_validity_assessment"][
        "target_fitter_id"
    ] = "55555555-5555-4555-8555-555555555551"
    _must_reject_contract(invalid_forecast_validity_fitter)

    invalid_forecast_validity_network = deepcopy(events[47])
    invalid_forecast_validity_network["payload"]["forecast_validity_assessment"][
        "execution_receipt"
    ]["network_access"] = True
    _must_reject_contract(invalid_forecast_validity_network)

    invalid_forecast_fitter_training = deepcopy(events[48])
    invalid_forecast_fitter_training["payload"]["forecast_fitter_specification"][
        "training_contract"
    ]["training_state"] = "COMPLETED"
    _must_reject_contract(invalid_forecast_fitter_training)

    invalid_forecast_fitter_retroactivity = deepcopy(events[48])
    invalid_forecast_fitter_retroactivity["payload"]["forecast_fitter_specification"][
        "applicability"
    ]["retroactive_application_state"] = "ALLOWED"
    _must_reject_contract(invalid_forecast_fitter_retroactivity)

    invalid_forecast_fitter_network = deepcopy(events[48])
    invalid_forecast_fitter_network["payload"]["forecast_fitter_specification"][
        "network_access"
    ] = True
    _must_reject_contract(invalid_forecast_fitter_network)

    try:
        ReadinProjection.replay([events[4]])
    except ProjectionError:
        pass
    else:
        raise AssertionError("semantic negative vector was accepted")

    invalid_access_scope = deepcopy(events[4])
    invalid_access_scope["payload"]["observation"]["epistemic"]["access_scope"] = "LICENSED"
    try:
        ReadinProjection.replay([*events[:4], invalid_access_scope])
    except ProjectionError:
        pass
    else:
        raise AssertionError("observation epistemic access-scope drift was accepted")

    invalid_dependency = deepcopy(events[10])
    invalid_dependency["payload"]["dependency"]["ancestor_evidence_id"] = (
        "77777777-7777-4777-8777-777777777777"
    )
    try:
        ReadinProjection.replay([*events[:10], invalid_dependency])
    except ProjectionError:
        pass
    else:
        raise AssertionError("invalid verified dependency was accepted")

    invalid_link = deepcopy(events[13])
    invalid_link["payload"]["evidence_link"]["appraisal"] = {
        "status": "NOT_APPRAISED",
        "method": "unsupported appraisal",
        "notes": None,
    }
    try:
        ReadinProjection.replay([*events[:13], invalid_link])
    except ProjectionError:
        pass
    else:
        raise AssertionError("incoherent evidence appraisal was accepted")

    backdated_event = deepcopy(events[5])
    backdated_event["occurred_at"] = "2026-08-21T12:00:03Z"
    try:
        ReadinProjection.replay([*events[:5], backdated_event])
    except ProjectionError:
        pass
    else:
        raise AssertionError("backdated ledger event was accepted")

    invalid_candidate = deepcopy(events[18])
    invalid_candidate["payload"]["resolution_candidate"]["right_entity_id"] = invalid_candidate[
        "payload"
    ]["resolution_candidate"]["left_entity_id"]
    try:
        ReadinProjection.replay([*events[:18], invalid_candidate])
    except ProjectionError:
        pass
    else:
        raise AssertionError("self-resolution candidate was accepted")

    invalid_assessment = deepcopy(events[19])
    invalid_assessment["payload"]["resolution_assessment"]["candidate_id"] = (
        "40404040-4040-4404-8404-404040404040"
    )
    try:
        ReadinProjection.replay([*events[:19], invalid_assessment])
    except ProjectionError:
        pass
    else:
        raise AssertionError("assessment of an unknown candidate was accepted")

    invalid_surface = deepcopy(events[23])
    invalid_surface["payload"]["cartographic_surface"]["blind_regions"] = []
    try:
        ReadinProjection.replay([*events[:23], invalid_surface])
    except ProjectionError:
        pass
    else:
        raise AssertionError("incoherent cartographic blind-region state was accepted")

    invalid_query = deepcopy(events[24])
    invalid_query["payload"]["cartographic_query_plan"]["surface_ids"] = [
        "50505050-5050-4505-8505-505050505050"
    ]
    try:
        ReadinProjection.replay([*events[:23], invalid_query])
    except ProjectionError:
        pass
    else:
        raise AssertionError("query with unknown cartographic surface was accepted")

    query_result = projection.execute_cartographic_query("39393939-3939-4393-8393-393939393939")
    if query_result["authority_state"] != "NO_AUTHORITY":
        raise AssertionError("cartographic query acquired action authority")
    if query_result["aperture"]["coverage_state"] != "NOT_ESTABLISHED":
        raise AssertionError("cartographic query promoted bounded aperture to coverage")

    invalid_fitter = deepcopy(events[25])
    invalid_fitter["payload"]["fitter_descriptor"]["implementation_sha256"] = "0" * 64
    try:
        ReadinProjection.replay([*events[:25], invalid_fitter])
    except ProjectionError:
        pass
    else:
        raise AssertionError("non-reference fitter implementation was accepted")

    invalid_fit = deepcopy(events[28])
    fitter_run = invalid_fit["payload"]["fitter_run"]
    fitter_run["fit_result"]["estimate"]["posterior_mean"] = 0.99
    fitter_run["execution_receipt"]["outcome_sha256"] = canonical_sha256(
        {
            "outcome": fitter_run["outcome"],
            "admissibility": fitter_run["admissibility"],
            "fit_result": fitter_run["fit_result"],
        }
    )
    try:
        ReadinProjection.replay([*events[:28], invalid_fit])
    except ProjectionError:
        pass
    else:
        raise AssertionError("non-reference fitter estimate was accepted")

    fitter_view = projection.multi_fitter_run_view("65656565-6565-4656-8565-656565656565")
    if fitter_view["consensus"]["state"] != "NOT_COMPUTED":
        raise AssertionError("multi-fitter runtime forced consensus")
    if fitter_view["outcome_counts"]["INVALID"] != 1:
        raise AssertionError("multi-fitter runtime suppressed model invalidity")

    invalid_belief = deepcopy(events[34])
    invalid_belief["payload"]["belief_revision"]["execution_receipt"]["input_snapshot_sha256"] = (
        "0" * 64
    )
    try:
        ReadinProjection.replay([*events[:34], invalid_belief])
    except ProjectionError:
        pass
    else:
        raise AssertionError("belief revision with invalid input digest was accepted")

    invalid_scenario = deepcopy(events[35])
    invalid_scenario["payload"]["scenario"]["branches"] = [
        branch
        for branch in invalid_scenario["payload"]["scenario"]["branches"]
        if branch["kind"] != "UNKNOWN_UNMODELED"
    ]
    try:
        ReadinProjection.replay([*events[:35], invalid_scenario])
    except ProjectionError:
        pass
    else:
        raise AssertionError("scenario without an unknown branch was accepted")

    invalid_scenario_run = deepcopy(events[36])
    invalid_scenario_run["payload"]["scenario_run"]["branch_results"][0]["antecedent_state"] = (
        "CONDITION_NOT_MATCHED"
    )
    try:
        ReadinProjection.replay([*events[:36], invalid_scenario_run])
    except ProjectionError:
        pass
    else:
        raise AssertionError("non-reference scenario evaluation was accepted")

    scenario_view = projection.scenario_run_view("89898989-8989-4989-8989-898989898981")
    if not scenario_view["run"]["summary"]["unknown_branch_visible"]:
        raise AssertionError("scenario runtime suppressed the unmodeled region")
    if scenario_view["prediction_state"] != "NOT_REQUESTED":
        raise AssertionError("scenario runtime promoted branch evaluation to prediction")

    invalid_discrimination_plan = deepcopy(events[38])
    invalid_discrimination_plan["payload"]["discrimination_plan"]["candidates"][0][
        "declared_blind_region_targets"
    ] = ["Invented blind region"]
    try:
        ReadinProjection.replay([*events[:38], invalid_discrimination_plan])
    except ProjectionError:
        pass
    else:
        raise AssertionError("discrimination plan targeted an unknown blind region")

    invalid_discrimination_run = deepcopy(events[39])
    invalid_discrimination_run["payload"]["discrimination_run"]["candidate_scores"][0]["rank"] = 2
    try:
        ReadinProjection.replay([*events[:39], invalid_discrimination_run])
    except ProjectionError:
        pass
    else:
        raise AssertionError("non-reference discrimination ranking was accepted")

    discrimination_view = projection.discrimination_run_view("94949494-9494-4494-8494-949494949491")
    if discrimination_view["acquisition_state"] != "NOT_ATTEMPTED":
        raise AssertionError("discrimination planning promoted ranking to acquisition")
    if discrimination_view["run"]["execution_receipt"]["network_access"]:
        raise AssertionError("discrimination planning acquired network access")

    invalid_forecast_timing = deepcopy(events[40])
    invalid_forecast_timing["payload"]["forecast_evaluation_design"]["timing"]["horizon_end"] = (
        "2026-09-22T00:00:00Z"
    )
    try:
        ReadinProjection.replay([*events[:40], invalid_forecast_timing])
    except ProjectionError:
        pass
    else:
        raise AssertionError("forecast evaluation design with horizon drift was accepted")

    design_view = projection.forecast_evaluation_design_view("a0a0a0a0-a0a0-40a0-80a0-a0a0a0a0a0a0")
    if design_view["forecast_capable_fitter_state"] != "NO_ELIGIBLE_FITTER_REGISTERED":
        raise AssertionError("reference baseline was incorrectly promoted to an eligible fitter")
    if design_view["forecast_baseline_state"] != "COMPLETED":
        raise AssertionError("forecast design did not expose its bounded reference baseline")
    if design_view["prediction_state"] != "PRODUCED_UNCALIBRATED_BASELINE":
        raise AssertionError("forecast baseline did not preserve its uncalibrated state")

    invalid_baseline = deepcopy(events[41])
    invalid_baseline["payload"]["forecast_baseline"]["execution_receipt"][
        "input_snapshot_sha256"
    ] = "0" * 64
    try:
        ReadinProjection.replay([*events[:41], invalid_baseline])
    except ProjectionError:
        pass
    else:
        raise AssertionError("forecast baseline with an invalid input digest was accepted")

    invalid_selection_plan = deepcopy(events[42])
    invalid_selection_plan["payload"]["readback_selection_plan"]["target"]["unit"] = "post-hoc-unit"
    try:
        ReadinProjection.replay([*events[:42], invalid_selection_plan])
    except ProjectionError:
        pass
    else:
        raise AssertionError("readback selection plan with target drift was accepted")

    invalid_selection_run = deepcopy(events[45])
    invalid_selection_run["payload"]["readback_selection_run"]["execution_receipt"][
        "input_snapshot_sha256"
    ] = "0" * 64
    try:
        ReadinProjection.replay([*events[:45], invalid_selection_run])
    except ProjectionError:
        pass
    else:
        raise AssertionError("readback selection with an invalid snapshot digest was accepted")

    invalid_forecast_residual_receipt = deepcopy(events[46])
    invalid_forecast_residual_receipt["payload"]["forecast_residual"]["execution_receipt"][
        "input_snapshot_sha256"
    ] = "0" * 64
    try:
        ReadinProjection.replay([*events[:46], invalid_forecast_residual_receipt])
    except ProjectionError:
        pass
    else:
        raise AssertionError("forecast residual with an invalid snapshot digest was accepted")

    invalid_forecast_residual_arithmetic = deepcopy(events[46])
    invalid_forecast_residual_arithmetic["payload"]["forecast_residual"]["score"][
        "absolute_error"
    ] = 0.5
    try:
        ReadinProjection.replay([*events[:46], invalid_forecast_residual_arithmetic])
    except ProjectionError:
        pass
    else:
        raise AssertionError("non-reference forecast residual arithmetic was accepted")

    invalid_forecast_validity_receipt = deepcopy(events[47])
    invalid_forecast_validity_receipt["payload"]["forecast_validity_assessment"][
        "execution_receipt"
    ]["input_snapshot_sha256"] = "0" * 64
    try:
        ReadinProjection.replay([*events[:47], invalid_forecast_validity_receipt])
    except ProjectionError:
        pass
    else:
        raise AssertionError("forecast validity gate accepted an invalid snapshot digest")

    invalid_forecast_validity_identity = deepcopy(events[47])
    invalid_forecast_validity_identity["payload"]["forecast_validity_assessment"]["scenario_id"] = (
        "00000000-0000-4000-8000-000000000000"
    )
    try:
        ReadinProjection.replay([*events[:47], invalid_forecast_validity_identity])
    except ProjectionError:
        pass
    else:
        raise AssertionError("forecast validity gate accepted identity drift")

    invalid_forecast_fitter_state = deepcopy(events[48])
    invalid_forecast_fitter_state["payload"]["forecast_fitter_specification"][
        "initial_state_version"
    ] = "00000000-0000-4000-8000-000000000000"
    try:
        ReadinProjection.replay([*events[:48], invalid_forecast_fitter_state])
    except ProjectionError:
        pass
    else:
        raise AssertionError("forecast fitter specification accepted state drift")

    invalid_forecast_fitter_features = deepcopy(events[48])
    duplicate_feature = deepcopy(
        invalid_forecast_fitter_features["payload"]["forecast_fitter_specification"][
            "feature_contracts"
        ][0]
    )
    duplicate_feature["structured_field_path"] = ["different_activity_score"]
    invalid_forecast_fitter_features["payload"]["forecast_fitter_specification"][
        "feature_contracts"
    ].append(duplicate_feature)
    try:
        ReadinProjection.replay([*events[:48], invalid_forecast_fitter_features])
    except ProjectionError:
        pass
    else:
        raise AssertionError("forecast fitter specification accepted duplicate feature names")

    baseline_view = projection.forecast_baseline_view("c0c0c0c0-c0c0-40c0-80c0-c0c0c0c0c0c0")
    if baseline_view["baseline"]["residual_scoring_state"] != "NOT_ENABLED":
        raise AssertionError("forecast baseline enabled residual scoring")
    if baseline_view["baseline"]["execution_receipt"]["network_access"]:
        raise AssertionError("forecast baseline acquired network access")
    forecast_residual_view = projection.forecast_residual_view(
        "e4e4e4e4-e4e4-44e4-84e4-e4e4e4e4e4e0"
    )
    forecast_residual = forecast_residual_view["forecast_residual"]
    if forecast_residual["score"]["signed_residual"] != 0.25:
        raise AssertionError("forecast residual did not preserve signed arithmetic")
    if forecast_residual["residual_state"] != "COMPUTED_DESCRIPTIVE_REFERENCE_ONLY":
        raise AssertionError("forecast residual exceeded its descriptive boundary")
    if forecast_residual["calibration_state"] != "NOT_ESTABLISHED":
        raise AssertionError("single readback promoted forecast calibration")
    if forecast_residual["validity_update_state"] != "NOT_APPLIED":
        raise AssertionError("descriptive residual changed fitter validity")
    if forecast_residual["learning_state"] != "NOT_STARTED":
        raise AssertionError("descriptive residual initiated learning")
    if forecast_residual["execution_receipt"]["network_access"]:
        raise AssertionError("forecast residual acquired network access")
    validity_view = projection.forecast_validity_assessment_view(
        "f0f0f0f0-f0f0-40f0-80f0-f0f0f0f0f0f0"
    )
    validity = validity_view["forecast_validity_assessment"]
    if validity["eligibility_state"] != "INELIGIBLE_VALIDITY_UPDATE":
        raise AssertionError("forecast validity gate suppressed ineligibility")
    if validity["decision_state"] != "ABSTAINED":
        raise AssertionError("forecast validity gate failed to abstain")
    forecast_fitter_view = projection.forecast_fitter_specification_view(
        "f3f3f3f3-f3f3-43f3-83f3-f3f3f3f3f3f3"
    )
    forecast_fitter = forecast_fitter_view["specification"]
    if forecast_fitter["registration_state"] != "REGISTERED_SPECIFICATION_ONLY":
        raise AssertionError("forecast fitter registration exceeded specification scope")
    if forecast_fitter["training_contract"]["training_state"] != "NOT_STARTED":
        raise AssertionError("forecast fitter specification initiated training")
    if forecast_fitter["execution_state"] != "NOT_ENABLED":
        raise AssertionError("forecast fitter specification enabled execution")
    if forecast_fitter_view["retroactive_effect_state"] != "NONE":
        raise AssertionError("forecast fitter specification rewrote historical validity")
    if validity["target_fitter_id"] is not None:
        raise AssertionError("forecast validity gate invented a target fitter")
    if validity["validity_update_state"] != "NOT_APPLIED":
        raise AssertionError("forecast validity gate applied an unsupported update")
    if validity["learning_state"] != "NOT_STARTED":
        raise AssertionError("forecast validity gate initiated learning")
    if validity["execution_receipt"]["network_access"]:
        raise AssertionError("forecast validity gate acquired network access")
    try:
        build_residual_snapshot(
            projection,
            "89898989-8989-4989-8989-898989898981",
            ["a2a2a2a2-a2a2-42a2-82a2-a2a2a2a2a2a2"],
        )
    except ResidualRuntimeError:
        pass
    else:
        raise AssertionError("Phase 8A path accepted a baseline-bound forecast residual")

    invalid_residual = deepcopy(residual_events[43])
    invalid_residual["payload"]["residual_readback"]["execution_receipt"][
        "observation_snapshot_sha256"
    ] = "0" * 64
    try:
        ReadinProjection.replay([*residual_events[:43], invalid_residual])
    except ProjectionError:
        pass
    else:
        raise AssertionError("residual readback with invalid observation digest was accepted")

    readback_view = residual_projection.residual_readback_view(
        "b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1"
    )
    if readback_view["residual_state"] != "NOT_COMPUTED":
        raise AssertionError("readback promoted an ineligible baseline to a residual")
    if readback_view["validity_update_state"] != "NOT_APPLIED":
        raise AssertionError("readback changed validity without an eligible residual")
    if readback_view["readback"]["execution_receipt"]["network_access"]:
        raise AssertionError("residual readback acquired network access")

    workbench = build_workbench_snapshot(projection, "11111111-1111-4111-8111-111111111111")
    if workbench["authority"]["state"] != "NO_AUTHORITY":
        raise AssertionError("workbench projection acquired action authority")
    if workbench["epistemic_limits"]["coverage_state"] != "NOT_ESTABLISHED":
        raise AssertionError("workbench projection promoted bounded aperture to coverage")
    if workbench["selected_asset"]["fitters"]["latest_run"]["outcome_counts"]["INVALID"] != 1:
        raise AssertionError("workbench projection suppressed fitter invalidity")
    if not any(
        branch["kind"] == "UNKNOWN_UNMODELED"
        for branch in workbench["selected_asset"]["scenarios"][0]["branches"]
    ):
        raise AssertionError("workbench projection suppressed the unmodeled region")
    collection = workbench["selected_asset"]["collection"]["latest_discrimination"]
    if collection["acquisition_state"] != "NOT_ATTEMPTED":
        raise AssertionError("workbench promoted observation planning to acquisition")
    if collection["expected_information_gain_state"] != "NOT_COMPUTED":
        raise AssertionError("workbench promoted ordinal ranking to information gain")
    baseline = workbench["selected_asset"]["forecasting"]["latest_baseline"]
    if baseline["residual_scoring_state"] != "NOT_ENABLED":
        raise AssertionError("workbench promoted forecast baseline to residual scoring")
    if baseline["learning_state"] != "NOT_STARTED":
        raise AssertionError("workbench promoted forecast baseline to learning")
    selection = workbench["selected_asset"]["readback"]["latest_selection"]
    if selection["selection_state"] != "UNIQUE_MATCH_SELECTED":
        raise AssertionError("workbench suppressed deterministic readback selection")
    if selection["residual_state"] != "NOT_COMPUTED":
        raise AssertionError("workbench promoted readback selection to residual scoring")
    if selection["aggregation_state"] != "NOT_PERFORMED":
        raise AssertionError("workbench aggregated readback observations")
    workbench_residual = workbench["selected_asset"]["readback"]["latest_forecast_residual"]
    if workbench_residual["absolute_error"] != 0.25:
        raise AssertionError("workbench suppressed descriptive residual arithmetic")
    if workbench_residual["empirical_validity_state"] != "NOT_ESTABLISHED":
        raise AssertionError("workbench promoted one residual to empirical validity")
    if workbench_residual["learning_state"] != "NOT_STARTED":
        raise AssertionError("workbench promoted descriptive arithmetic to learning")
    workbench_validity = workbench["selected_asset"]["readback"]["latest_validity_assessment"]
    if workbench_validity["decision_state"] != "ABSTAINED":
        raise AssertionError("workbench suppressed validity-update abstention")
    if workbench_validity["target_fitter_id"] is not None:
        raise AssertionError("workbench exposed an invented target fitter")
    if workbench_validity["validity_update_state"] != "NOT_APPLIED":
        raise AssertionError("workbench promoted the validity assessment to an update")
    workbench_fitter = workbench["selected_asset"]["forecasting"]["latest_fitter_specification"]
    if workbench_fitter["training_state"] != "NOT_STARTED":
        raise AssertionError("workbench promoted fitter specification to training")
    if workbench_fitter["retroactive_application_state"] != "PROHIBITED":
        raise AssertionError("workbench permitted retroactive fitter application")
    readback_workbench = build_workbench_snapshot(
        residual_projection, "11111111-1111-4111-8111-111111111111"
    )
    readback = readback_workbench["selected_asset"]["readback"]["latest"]
    if readback["residual_state"] != "NOT_COMPUTED":
        raise AssertionError("workbench promoted readback to a computed residual")
    if readback["learning_state"] != "NOT_STARTED":
        raise AssertionError("workbench promoted readback abstention to learning")
    forecast_design = workbench["selected_asset"]["forecasting"]["latest_evaluation_design"]
    if forecast_design["prediction_state"] != "PRODUCED_UNCALIBRATED_BASELINE":
        raise AssertionError("workbench suppressed the bounded baseline prediction state")

    try:
        build_workbench_snapshot(projection, "unknown-asset")
    except WorkbenchError:
        pass
    else:
        raise AssertionError("workbench accepted an unknown asset")
    try:
        validate_loopback_host("0.0.0.0")
    except WorkbenchError:
        pass
    else:
        raise AssertionError("workbench accepted a non-loopback host")

    print(
        f"PASS schemas=3 positive_events={len(events)} "
        f"asset_catalog_events={len(asset_catalog_events)} "
        f"residual_fixture_events={len(residual_events)} "
        f"negative_contract_vectors=29 negative_semantic_vectors=28 "
        f"tracked_assets={len(projection.assets)} "
        f"claims={len(projection.claims)} relations={len(projection.relations)} "
        f"resolution_candidates={len(projection.resolution_candidates)} "
        f"cartographic_surfaces={len(projection.cartographic_surfaces)} "
        f"cartographic_query_plans={len(projection.cartographic_query_plans)} "
        f"fitters={len(projection.fitters)} fitter_runs={len(projection.fitter_runs)} "
        f"fit_results={len(projection.fit_results)} hypotheses={len(projection.hypotheses)} "
        f"belief_revisions={len(projection.belief_revisions)} "
        f"scenarios={len(projection.scenarios)} scenario_runs={len(projection.scenario_runs)} "
        f"discrimination_plans={len(projection.discrimination_plans)} "
        f"discrimination_runs={len(projection.discrimination_runs)} "
        f"forecast_evaluation_designs={len(projection.forecast_evaluation_designs)} "
        f"forecast_baselines={len(projection.forecast_baselines)} "
        f"readback_selection_plans={len(projection.readback_selection_plans)} "
        f"readback_selection_runs={len(projection.readback_selection_runs)} "
        f"forecast_residuals={len(projection.forecast_residuals)} "
        f"forecast_validity_assessments={len(projection.forecast_validity_assessments)} "
        f"forecast_fitter_specifications={len(projection.forecast_fitter_specifications)} "
        f"residual_readbacks={len(projection.residual_readbacks)} "
        "workbench_contracts=1 negative_workbench_vectors=2 "
        "real_asset_policy_vectors=2 asset_catalog_policy_vectors=2"
    )


if __name__ == "__main__":
    main()
