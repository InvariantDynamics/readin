from __future__ import annotations

from copy import deepcopy

import pytest

from readin.projection import ProjectionError, ReadinProjection
from readin.synthetic import phase0_events


def test_phase0_loop_projects_complete_asset_view() -> None:
    events = phase0_events()
    projection = ReadinProjection.replay(events)
    entity_id = events[0]["payload"]["entity"]["id"]

    view = projection.asset_view(entity_id)

    assert view["entity"]["canonical_name"] == "Example Research Cooperative"
    assert view["tracked_asset"]["epistemic_state_version"] == events[-1]["event_id"]
    assert len(view["observations"]) == 1
    assert len(view["observer_frames"]) == 1
    assert len(view["evidence_manifests"]) == 1
    assert view["authority_state"] == "NO_AUTHORITY"


def test_observation_requires_prior_entity_tracking_frame_and_evidence() -> None:
    with pytest.raises(ProjectionError, match="untracked entities"):
        ReadinProjection.replay([phase0_events()[-1]])


def test_observation_source_policy_must_match_manifest_and_frame() -> None:
    events = phase0_events()
    changed = deepcopy(events[-1])
    changed["payload"]["observation"]["provenance"]["source_policy"] = "LICENSED"
    changed["payload"]["observation"]["epistemic"]["access_scope"] = "LICENSED"

    with pytest.raises(ProjectionError, match="does not match evidence manifest"):
        ReadinProjection.replay([*events[:-1], changed])


def test_observation_epistemic_access_scope_must_match_source_policy() -> None:
    events = phase0_events()
    changed = deepcopy(events[-1])
    changed["payload"]["observation"]["epistemic"]["access_scope"] = "LICENSED"

    with pytest.raises(ProjectionError, match="access scope does not match source policy"):
        ReadinProjection.replay([*events[:-1], changed])


def test_duplicate_evidence_digest_is_rejected() -> None:
    events = phase0_events()
    duplicate = deepcopy(events[3])
    duplicate["event_id"] = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1"
    duplicate["payload"]["evidence_manifest"]["id"] = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2"

    with pytest.raises(ProjectionError, match="digest already manifested"):
        ReadinProjection.replay([*events[:4], duplicate])


def test_invalid_temporal_scope_is_rejected() -> None:
    events = phase0_events()
    changed = deepcopy(events[-1])
    observation = changed["payload"]["observation"]
    observation["valid_from"] = "2026-08-22T00:00:00Z"
    observation["valid_until"] = "2026-08-21T00:00:00Z"

    with pytest.raises(ProjectionError, match="valid_from is after"):
        ReadinProjection.replay([*events[:-1], changed])
