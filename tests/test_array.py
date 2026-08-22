from __future__ import annotations

from copy import deepcopy

import pytest

from readin.events import (
    create_claim_created,
    create_evidence_dependency_declared,
    create_evidence_linked,
    create_evidence_manifested,
    create_observation_admitted,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase0_events, phase1_events


def test_phase1_loop_preserves_unresolved_claim_and_evidence_dependence() -> None:
    events = phase1_events()
    projection = ReadinProjection.replay(events)
    entity_id = events[0]["payload"]["entity"]["id"]
    claim_id = events[12]["payload"]["claim"]["id"]

    view = projection.asset_view(entity_id)
    claim_view = projection.claim_view(claim_id)

    assert len(events) == 17
    assert len(view["claims"]) == 1
    assert len(view["relations"]) == 1
    assert len(view["evidence_dependencies"]) == 2
    assert claim_view["epistemic_status"] == "unresolved"
    assert claim_view["evidence_role_counts"] == {"supports": 3}
    assert len(claim_view["dependency_groups"]) == 1
    assert claim_view["independence_status"] == "DEPENDENT_EVIDENCE_PRESENT"
    assert claim_view["authority_state"] == "NO_AUTHORITY"


def test_dependency_cycle_is_rejected() -> None:
    events = phase1_events()
    reverse_edge = create_evidence_dependency_declared(
        "12121212-1212-4121-8121-121212121212",
        "66666666-6666-4666-8666-666666666666",
        "33333333-3333-4333-8333-333333333333",
        "UNKNOWN_SHARED_ANCESTRY",
        dependency_id="13131313-1313-4131-8131-131313131313",
        event_id="14141414-1414-4141-8141-141414141414",
        occurred_at="2026-08-21T12:00:11Z",
    )

    with pytest.raises(ProjectionError, match="cycle"):
        ReadinProjection.replay([*events[:11], reverse_edge])


def test_event_admission_time_cannot_move_backward() -> None:
    events = phase1_events()
    changed = deepcopy(events[5])
    changed["occurred_at"] = "2026-08-21T12:00:03Z"

    with pytest.raises(ProjectionError, match="precedes the prior ledger event"):
        ReadinProjection.replay([*events[:5], changed])


def test_verified_dependency_must_be_bound_by_manifest() -> None:
    events = phase1_events()
    changed = deepcopy(events[10])
    changed["payload"]["dependency"]["ancestor_evidence_id"] = (
        "77777777-7777-4777-8777-777777777777"
    )

    with pytest.raises(ProjectionError, match="not bound"):
        ReadinProjection.replay([*events[:10], changed])


def test_manifest_basis_requires_verified_dependency_status() -> None:
    events = phase1_events()
    changed = deepcopy(events[10])
    changed["payload"]["dependency"]["verification_status"] = "ASSERTED_NOT_VERIFIED"

    with pytest.raises(ProjectionError, match="requires VERIFIED_FROM_MANIFEST"):
        ReadinProjection.replay([*events[:10], changed])


def test_manifest_verification_rejects_non_derivative_relationship() -> None:
    events = phase1_events()
    changed = deepcopy(events[10])
    changed["payload"]["dependency"]["relationship"] = "CITES"

    with pytest.raises(ProjectionError, match="incompatible"):
        ReadinProjection.replay([*events[:10], changed])


def test_evidence_link_requires_registered_dependency_group() -> None:
    events = phase1_events()
    changed = deepcopy(events[13])
    changed["payload"]["evidence_link"]["dependency_group"] = "15151515-1515-4151-8151-151515151515"

    with pytest.raises(ProjectionError, match="unknown dependency group"):
        ReadinProjection.replay([*events[:13], changed])


def test_observation_dependency_group_must_exist() -> None:
    events = phase0_events()
    changed = deepcopy(events[-1])
    changed["payload"]["observation"]["epistemic"]["dependency_group_ids"] = [
        "15151515-1515-4151-8151-151515151515"
    ]

    with pytest.raises(ProjectionError, match="unknown dependency group"):
        ReadinProjection.replay([*events[:-1], changed])


def test_observation_can_reference_a_declared_artifact_dependency_group() -> None:
    events = phase1_events()
    observation = create_observation_admitted(
        ["11111111-1111-4111-8111-111111111111"],
        "22222222-2222-4222-8222-222222222222",
        "33333333-3333-4333-8333-333333333333",
        "public_record.program_reported",
        {"reported_status": "restated"},
        "2026-08-21T11:59:30Z",
        source_uri="urn:readin:synthetic:public-record-001",
        dependency_group_ids=["dddddddd-dddd-4ddd-8ddd-dddddddddddd"],
        observation_id="18181818-1818-4181-8181-181818181818",
        event_id="19191919-1919-4191-8191-191919191919",
        occurred_at="2026-08-21T12:00:12Z",
    )

    projection = ReadinProjection.replay([*events[:12], observation])

    assert projection.observations["18181818-1818-4181-8181-181818181818"]["epistemic"][
        "dependency_group_ids"
    ] == ["dddddddd-dddd-4ddd-8ddd-dddddddddddd"]


def test_strength_assessment_requires_completed_appraisal() -> None:
    events = phase1_events()
    link = create_evidence_linked(
        "33333333-3333-4333-8333-333333333333",
        "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "challenges",
        strength_status="ASSESSED",
        strength_ordinal="STRONG",
        link_id="16161616-1616-4161-8161-161616161616",
        event_id="17171717-1717-4171-8171-171717171717",
        occurred_at="2026-08-21T12:00:13Z",
    )

    with pytest.raises(ProjectionError, match="completed appraisal"):
        ReadinProjection.replay([*events[:13], link])


def test_derives_link_must_reference_a_claim_derivation_artifact() -> None:
    events = phase1_events()
    unrelated_evidence = create_evidence_manifested(
        "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        "text/plain",
        1,
        "Unrelated synthetic artifact",
        source_uri="urn:readin:synthetic:unrelated-001",
        artifact_id="20202020-2020-4202-8202-202020202020",
        event_id="21212121-2121-4212-8212-212121212121",
        occurred_at="2026-08-21T12:00:13Z",
    )
    link = create_evidence_linked(
        "20202020-2020-4202-8202-202020202020",
        "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        "derives",
        link_id="22222222-2222-4222-8222-222222222229",
        event_id="23232323-2323-4232-8232-232323232323",
        occurred_at="2026-08-21T12:00:14Z",
    )

    with pytest.raises(ProjectionError, match="not an artifact"):
        ReadinProjection.replay([*events[:13], unrelated_evidence, link])


def test_causality_cannot_be_silently_promoted() -> None:
    events = phase1_events()
    changed = deepcopy(events[-1])
    changed["payload"]["relation"]["relation_type"] = "CAUSES"

    with pytest.raises(ProjectionError, match="explicitly provisional"):
        ReadinProjection.replay([*events[:-1], changed])


def test_every_relation_claim_must_connect_the_declared_entities() -> None:
    events = phase1_events()
    unrelated_claim = create_claim_created(
        "11111111-1111-4111-8111-111111111111",
        "reported_status",
        {"kind": "LITERAL", "value": "announced"},
        ["44444444-4444-4444-8444-444444444444"],
        claim_id="24242424-2424-4242-8242-242424242424",
        event_id="25252525-2525-4252-8252-252525252525",
        occurred_at="2026-08-21T12:00:13Z",
    )
    changed = deepcopy(events[-1])
    changed["payload"]["relation"]["claims"].append("24242424-2424-4242-8242-242424242424")

    with pytest.raises(ProjectionError, match="do not connect"):
        ReadinProjection.replay([*events[:13], unrelated_claim, changed])


def test_asset_state_history_advances_with_array_events() -> None:
    events = phase1_events()
    projection = ReadinProjection.replay(events)
    entity_id = events[0]["payload"]["entity"]["id"]
    view = projection.asset_view(entity_id)

    assert view["tracked_asset"]["epistemic_state_version"] == events[-1]["event_id"]
    assert view["state_history"][-1]["event_type"] == "relation.created"
    assert len(view["state_history"]) == 11


def test_historical_reconstruction_labels_hindsight() -> None:
    events = phase1_events()
    projection = ReadinProjection.replay(events)
    entity_id = events[0]["payload"]["entity"]["id"]
    cutoff = "2026-08-21T12:00:11Z"

    known_then = projection.asset_view_at(
        entity_id,
        mode="AS_KNOWN_THEN",
        epistemic_cutoff=cutoff,
    )
    reconstructed = projection.asset_view_at(
        entity_id,
        mode="AS_RECONSTRUCTED_NOW",
        epistemic_cutoff=cutoff,
    )

    assert known_then["claims"] == []
    assert known_then["relations"] == []
    assert known_then["reconstruction"]["hindsight_included"] is False
    assert len(reconstructed["claims"]) == 1
    assert len(reconstructed["relations"]) == 1
    assert reconstructed["reconstruction"]["hindsight_included"] is True
    assert any(
        item["event_type"] == "claim.created" and item["hindsight"]
        for item in reconstructed["timeline"]
    )
