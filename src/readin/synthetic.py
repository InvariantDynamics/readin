"""Closed synthetic events for validation and the local demonstration."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from readin.events import (
    create_entity_created,
    create_evidence_manifested,
    create_observation_admitted,
    create_observer_frame_registered,
    create_tracking_started,
)


def phase0_events() -> list[dict[str, Any]]:
    """Return one deterministic, synthetic Phase 0 event loop."""

    entity_id = "11111111-1111-4111-8111-111111111111"
    frame_id = "22222222-2222-4222-8222-222222222222"
    artifact_id = "33333333-3333-4333-8333-333333333333"
    event_time = "2026-08-21T12:00:00Z"
    payload = {
        "reported_program": "Synthetic compute research initiative",
        "reported_status": "announced",
    }
    artifact_bytes = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    source_uri = "urn:readin:synthetic:public-record-001"

    return [
        create_entity_created(
            "Example Research Cooperative",
            "Organization",
            aliases=["ERC Synthetic"],
            entity_id=entity_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
            occurred_at=event_time,
        ),
        create_tracking_started(
            entity_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
            occurred_at="2026-08-21T12:00:01Z",
        ),
        create_observer_frame_registered(
            "Synthetic public record",
            "public_record",
            access_description="Closed synthetic public-record fixture",
            known_blind_regions=["No independent operational verification"],
            validity_conditions=["Valid only for the bundled synthetic fixture"],
            frame_id=frame_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
            occurred_at="2026-08-21T12:00:02Z",
        ),
        create_evidence_manifested(
            hashlib.sha256(artifact_bytes).hexdigest(),
            "application/json",
            len(artifact_bytes),
            "Bundled synthetic public record",
            source_uri=source_uri,
            license_name="Apache-2.0",
            artifact_id=artifact_id,
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
            occurred_at="2026-08-21T12:00:03Z",
        ),
        create_observation_admitted(
            [entity_id],
            frame_id,
            artifact_id,
            "public_record.program_reported",
            payload,
            "2026-08-21T11:59:00Z",
            source_uri=source_uri,
            uncertainty={"disposition": "NOT_EVALUATED"},
            observation_id="44444444-4444-4444-8444-444444444444",
            event_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5",
            occurred_at="2026-08-21T12:00:04Z",
        ),
    ]
