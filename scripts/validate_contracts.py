"""Validate the schema, Phase 7 loop, and fail-closed negative vectors."""

from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator

from readin.contracts import ContractViolation, load_event_schema, validate_event
from readin.fitters import canonical_sha256
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase7_events
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
    events = phase7_events()
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
        f"PASS schemas=1 positive_events={len(events)} negative_contract_vectors=7 "
        f"negative_semantic_vectors=15 tracked_assets={len(projection.assets)} "
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
        "workbench_contracts=1 negative_workbench_vectors=2"
    )


if __name__ == "__main__":
    main()
