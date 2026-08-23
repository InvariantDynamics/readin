"""Bounded Phase 3 cartographic surface and backward-query behavior."""

from __future__ import annotations

from copy import deepcopy

import pytest

from readin.events import (
    create_cartographic_query_planned,
    create_cartographic_surface_registered,
    create_claim_created,
)
from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase3_events

ASSET_ID = "11111111-1111-4111-8111-111111111111"
PUBLIC_FRAME_ID = "22222222-2222-4222-8222-222222222222"
ANALYST_FRAME_ID = "32323232-3232-4323-8323-323232323232"
SURFACE_ID = "37373737-3737-4373-8373-373737373737"
QUERY_ID = "39393939-3939-4393-8393-393939393939"


def test_phase3_backward_query_is_bounded_auditable_and_deterministic() -> None:
    events = phase3_events()
    projection = ReadinProjection.replay(events)

    first = projection.execute_cartographic_query(QUERY_ID)
    second = projection.execute_cartographic_query(QUERY_ID)

    assert len(events) == 25
    assert first == second
    assert first["execution"] == {
        "state": "LOCAL_LEDGER_REPLAY",
        "read_only": True,
        "network_access": False,
        "prediction_state": "NOT_REQUESTED",
    }
    assert first["data_reconstruction"] == {
        "mode": "AS_KNOWN_THEN",
        "epistemic_cutoff": "2026-08-21T12:00:22Z",
    }
    assert first["query_plan_ledger_recorded_at"] == "2026-08-21T12:00:24Z"
    assert first["cartographic_surfaces"][0]["ledger_recorded_at"] == ("2026-08-21T12:00:23Z")
    assert first["aperture"]["included_observation_count"] == 3
    assert first["aperture"]["excluded_asset_observation_count"] == 1
    assert first["aperture"]["coverage_state"] == "NOT_ESTABLISHED"
    assert first["aperture"]["completeness_claim"] == "NOT_MADE"
    assert len(first["entities"]) == 2
    assert len(first["claims"]) == 1
    assert len(first["relations"]) == 1
    assert len(first["evidence_manifests"]) == 3
    assert len(first["evidence_dependencies"]) == 2
    assert first["claims"][0]["independence_status"] == "DEPENDENT_EVIDENCE_PRESENT"
    assert first["claims"][0]["outside_surface_derivation_observation_ids"] == []
    assert first["blind_regions"]["known"] == ["No independent operational verification"]
    assert first["missingness_policy"] == "PRESERVE"
    assert first["conflict_policy"] == "PRESERVE"
    assert first["authority_state"] == "NO_AUTHORITY"
    assert first["query_lens"] == {
        "hindsight_basis": "LEDGER_RECORDED_AT",
        "plan_recorded_after_cutoff": True,
        "surface_ids_recorded_after_cutoff": [SURFACE_ID],
        "hindsight_in_query_lens": True,
    }


def test_surface_and_query_are_inspectable_without_coverage_or_action_authority() -> None:
    projection = ReadinProjection.replay(phase3_events())

    surface = projection.cartographic_surface_view(SURFACE_ID)
    query = projection.cartographic_query_plan_view(QUERY_ID)
    asset = projection.asset_view(ASSET_ID)

    assert surface["surface"]["observer_frame_ids"] == [PUBLIC_FRAME_ID]
    assert surface["coverage_state"] == "NOT_ESTABLISHED"
    assert surface["completeness_claim"] == "NOT_MADE"
    assert surface["validity_evaluation_state"] == "NOT_EVALUATED"
    assert surface["authority_state"] == "NO_AUTHORITY"
    assert query["plan"]["direction"] == "BACKWARD"
    assert query["plan"]["execution_state"] == "PLANNED_READ_ONLY"
    assert query["plan"]["prediction_state"] == "NOT_REQUESTED"
    assert len(asset["cartographic_query_plans"]) == 1
    assert projection.catalog_view()[0]["cartographic_query_plan_count"] == 1


def test_query_lens_hindsight_uses_ledger_time_not_backdatable_domain_time() -> None:
    events = phase3_events()
    events[23]["payload"]["cartographic_surface"]["registered_at"] = "2026-08-21T12:00:00Z"
    events[24]["payload"]["cartographic_query_plan"]["created_at"] = "2026-08-21T12:00:00Z"

    lens = ReadinProjection.replay(events).cartographic_query_plan_view(QUERY_ID)["query_lens"]

    assert lens["hindsight_basis"] == "LEDGER_RECORDED_AT"
    assert lens["plan_recorded_after_cutoff"] is True
    assert lens["surface_ids_recorded_after_cutoff"] == [SURFACE_ID]


def test_surface_requires_known_frames_and_consistent_blind_region_state() -> None:
    events = phase3_events()
    prefix = events[:23]

    unknown_frame = deepcopy(events[23])
    unknown_frame["payload"]["cartographic_surface"]["observer_frame_ids"] = [
        "41414141-4141-4414-8414-414141414141"
    ]
    with pytest.raises(ProjectionError, match="unknown observer frames"):
        ReadinProjection.replay([*prefix, unknown_frame])

    empty_declared = deepcopy(events[23])
    empty_declared["payload"]["cartographic_surface"]["blind_regions"] = []
    with pytest.raises(ProjectionError, match="requires at least one blind region"):
        ReadinProjection.replay([*prefix, empty_declared])

    uncharacterized_with_region = deepcopy(events[23])
    surface = uncharacterized_with_region["payload"]["cartographic_surface"]
    surface["blind_region_state"] = "NOT_CHARACTERIZED"
    with pytest.raises(ProjectionError, match="cannot declare blind regions"):
        ReadinProjection.replay([*prefix, uncharacterized_with_region])


def test_query_requires_known_surface_and_coherent_relation_traversal() -> None:
    events = phase3_events()

    unknown_surface = deepcopy(events[24])
    unknown_surface["payload"]["cartographic_query_plan"]["surface_ids"] = [
        "42424242-4242-4424-8424-424242424242"
    ]
    with pytest.raises(ProjectionError, match="unknown surfaces"):
        ReadinProjection.replay([*events[:23], unknown_surface])

    zero_hop_relation_traversal = deepcopy(events[24])
    zero_hop_relation_traversal["payload"]["cartographic_query_plan"]["traversal"][
        "max_relation_hops"
    ] = 0
    with pytest.raises(ProjectionError, match="requires at least one relation hop"):
        ReadinProjection.replay([*events[:24], zero_hop_relation_traversal])


def test_query_rejects_historical_cutoff_before_asset_tracking() -> None:
    events = phase3_events()
    query = deepcopy(events[24])
    query["payload"]["cartographic_query_plan"]["reconstruction"]["epistemic_cutoff"] = (
        "2026-08-21T12:00:00Z"
    )

    with pytest.raises(ProjectionError, match="cutoff precedes asset tracking"):
        ReadinProjection.replay([*events[:24], query])


def test_disabled_relation_traversal_stays_on_the_tracked_asset() -> None:
    projection = ReadinProjection.replay(phase3_events())
    query_id = "43434343-4343-4434-8434-434343434343"
    projection.apply(
        create_cartographic_query_planned(
            ASSET_ID,
            [SURFACE_ID],
            reconstruction_mode="AS_RECONSTRUCTED_NOW",
            max_relation_hops=0,
            include_relations=False,
            query_id=query_id,
            event_id="44444444-4444-4444-8444-444444444441",
            occurred_at="2026-08-21T12:00:25Z",
        )
    )

    result = projection.execute_cartographic_query(query_id)

    assert [item["id"] for item in result["entities"]] == [ASSET_ID]
    assert result["relations"] == []
    assert len(result["claims"]) == 1


def test_mixed_frame_claim_preserves_outside_surface_derivation() -> None:
    events = phase3_events()
    mixed_claim_id = "53535353-5353-4535-8535-535353535353"
    mixed_claim = create_claim_created(
        ASSET_ID,
        "has_mixed_frame_interpretation",
        {"kind": "LITERAL", "value": "fixture-only"},
        [
            "44444444-4444-4444-8444-444444444444",
            "35353535-3535-4353-8353-353535353535",
        ],
        claim_id=mixed_claim_id,
        event_id="54545454-5454-4545-8545-545454545454",
        occurred_at="2026-08-21T12:00:22.500000Z",
    )
    query = deepcopy(events[24])
    query["payload"]["cartographic_query_plan"]["reconstruction"]["epistemic_cutoff"] = (
        "2026-08-21T12:00:22.500000Z"
    )
    projection = ReadinProjection.replay([*events[:23], mixed_claim, events[23], query])

    result = projection.execute_cartographic_query(QUERY_ID)
    mixed_view = next(item for item in result["claims"] if item["claim"]["id"] == mixed_claim_id)

    assert mixed_view["surface_matched_observation_ids"] == ["44444444-4444-4444-8444-444444444444"]
    assert mixed_view["outside_surface_derivation_observation_ids"] == [
        "35353535-3535-4353-8353-353535353535"
    ]


def test_post_cutoff_frame_can_define_a_hindsight_lens_without_backfilling_data() -> None:
    projection = ReadinProjection.replay(phase3_events())
    surface_id = "45454545-4545-4454-8454-454545454545"
    query_id = "46464646-4646-4464-8464-464646464646"
    projection.apply(
        create_cartographic_surface_registered(
            "Analyst-only hindsight surface",
            "A surface whose frame did not yet exist at the data cutoff",
            [ANALYST_FRAME_ID],
            blind_region_state="NOT_CHARACTERIZED",
            surface_id=surface_id,
            event_id="47474747-4747-4474-8474-474747474747",
            occurred_at="2026-08-21T12:00:25Z",
        )
    )
    projection.apply(
        create_cartographic_query_planned(
            ASSET_ID,
            [surface_id],
            epistemic_cutoff="2026-08-21T12:00:19Z",
            max_relation_hops=0,
            include_relations=False,
            query_id=query_id,
            event_id="48484848-4848-4484-8484-484848484848",
            occurred_at="2026-08-21T12:00:26Z",
        )
    )

    result = projection.execute_cartographic_query(query_id)

    assert result["observations"] == []
    assert result["lens_observer_frames"][0]["id"] == ANALYST_FRAME_ID
    assert result["data_observer_frame_ids"] == []
    assert result["blind_regions"]["uncharacterized_surface_ids"] == [surface_id]
    assert result["query_lens"]["hindsight_in_query_lens"] is True
    assert result["aperture"]["coverage_state"] == "NOT_ESTABLISHED"
