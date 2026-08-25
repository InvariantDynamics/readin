"""Validate the schema, Phase 8B loop, and fail-closed negative vectors."""

from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator

from readin.contracts import ContractViolation, load_event_schema, validate_event
from readin.fitters import canonical_sha256
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase8_events
from readin.workbench import WorkbenchError, build_workbench_snapshot, validate_loopback_host


def _must_reject_contract(event: dict[str, object]) -> None:
    try:
        validate_event(event)
    except ContractViolation:
        return
    raise AssertionError("negative contract vector was accepted")


def main() -> None:
    schema = load_event_schema()
    Draft202012Validator.check_schema(schema)
    events = phase8_events()
    for event in events:
        validate_event(event)
    projection = ReadinProjection.replay(events)

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

    invalid_residual_contract = deepcopy(events[43])
    invalid_residual_contract["payload"]["residual_readback"]["residual_state"] = "COMPUTED"
    _must_reject_contract(invalid_residual_contract)

    invalid_validity_update = deepcopy(events[43])
    invalid_validity_update["payload"]["residual_readback"]["validity_update_state"] = "APPLIED"
    _must_reject_contract(invalid_validity_update)

    try:
        ReadinProjection.replay([events[4]])
    except ProjectionError:
        pass
    else:
        raise AssertionError("semantic negative vector was accepted")

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
        raise AssertionError("forecast design implied an eligible fitter")
    if design_view["prediction_state"] != "NOT_PRODUCED":
        raise AssertionError("forecast design promoted preregistration to prediction")

    invalid_residual = deepcopy(events[43])
    invalid_residual["payload"]["residual_readback"]["execution_receipt"][
        "observation_snapshot_sha256"
    ] = "0" * 64
    try:
        ReadinProjection.replay([*events[:43], invalid_residual])
    except ProjectionError:
        pass
    else:
        raise AssertionError("residual readback with invalid observation digest was accepted")

    readback_view = projection.residual_readback_view("b1b1b1b1-b1b1-41b1-81b1-b1b1b1b1b1b1")
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
    readback = workbench["selected_asset"]["readback"]["latest"]
    if readback["residual_state"] != "NOT_COMPUTED":
        raise AssertionError("workbench promoted readback to a computed residual")
    if readback["learning_state"] != "NOT_STARTED":
        raise AssertionError("workbench promoted readback abstention to learning")
    forecast_design = workbench["selected_asset"]["forecasting"]["latest_evaluation_design"]
    if forecast_design["prediction_state"] != "NOT_PRODUCED":
        raise AssertionError("workbench promoted evaluation design to prediction")

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
        f"PASS schemas=1 positive_events={len(events)} negative_contract_vectors=11 "
        f"negative_semantic_vectors=17 tracked_assets={len(projection.assets)} "
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
        f"residual_readbacks={len(projection.residual_readbacks)} "
        "workbench_contracts=1 negative_workbench_vectors=2"
    )


if __name__ == "__main__":
    main()
