"""Validate the schema, Phase 3 loop, and fail-closed negative vectors."""

from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator

from readin.contracts import ContractViolation, load_event_schema, validate_event
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase3_events


def _must_reject_contract(event: dict[str, object]) -> None:
    try:
        validate_event(event)
    except ContractViolation:
        return
    raise AssertionError("negative contract vector was accepted")


def main() -> None:
    schema = load_event_schema()
    Draft202012Validator.check_schema(schema)
    events = phase3_events()
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

    print(
        f"PASS schemas=1 positive_events={len(events)} negative_contract_vectors=3 "
        f"negative_semantic_vectors=8 tracked_assets={len(projection.assets)} "
        f"claims={len(projection.claims)} relations={len(projection.relations)} "
        f"resolution_candidates={len(projection.resolution_candidates)} "
        f"cartographic_surfaces={len(projection.cartographic_surfaces)} "
        f"cartographic_query_plans={len(projection.cartographic_query_plans)}"
    )


if __name__ == "__main__":
    main()
