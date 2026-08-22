"""Validate the schema, positive event loop, and fail-closed negative vectors."""

from __future__ import annotations

from copy import deepcopy

from jsonschema import Draft202012Validator

from readin.contracts import ContractViolation, load_event_schema, validate_event
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase0_events


def _must_reject_contract(event: dict[str, object]) -> None:
    try:
        validate_event(event)
    except ContractViolation:
        return
    raise AssertionError("negative contract vector was accepted")


def main() -> None:
    schema = load_event_schema()
    Draft202012Validator.check_schema(schema)
    events = phase0_events()
    for event in events:
        validate_event(event)
    projection = ReadinProjection.replay(events)

    unknown_field = deepcopy(events[0])
    unknown_field["unexpected"] = True
    _must_reject_contract(unknown_field)

    invalid_authority = deepcopy(events[0])
    invalid_authority["authority_state"] = "EXECUTE_ACTION"
    _must_reject_contract(invalid_authority)

    try:
        ReadinProjection.replay([events[-1]])
    except ProjectionError:
        pass
    else:
        raise AssertionError("semantic negative vector was accepted")

    print(
        "PASS schemas=1 positive_events=5 negative_contract_vectors=2 "
        f"negative_semantic_vectors=1 tracked_assets={len(projection.assets)}"
    )


if __name__ == "__main__":
    main()
