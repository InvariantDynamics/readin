"""Read-only inventory of implemented source paths, grant readiness, and admitted data."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from readin.asset_catalog import load_asset_catalog_source_schema
from readin.connector_grants import CONNECTOR_GRANT_OBSERVATION_TYPE, ConnectorGrantError
from readin.local_source_exports import LOCAL_SOURCE_EXPORT_ADAPTER, _matching_grant
from readin.native_source_exports import NATIVE_SOURCE_ADAPTER, PARSER_VERSION, PARSERS
from readin.projection import ReadinProjection

IMPORTED_SOURCE_ADAPTERS = frozenset({LOCAL_SOURCE_EXPORT_ADAPTER, NATIVE_SOURCE_ADAPTER})


def source_parser_catalog() -> list[dict[str, Any]]:
    return [
        {
            "parser": parser,
            "version": PARSER_VERSION,
            **deepcopy(spec),
            "input": "NATIVE_LOCAL_FILE",
        }
        for parser, spec in PARSERS.items()
    ] + [
        {
            "parser": "GENERIC_JSON_OBSERVATION_BATCH",
            "version": "0.1.0",
            "label": "Prepared social profile JSON",
            "asset_class": "SOCIAL_ACCOUNT",
            "platform": None,
            "data_category": "ACCOUNT_PROFILE_METADATA",
            "observation_type": "social.profile_metadata",
            "media_type": "application/json",
            "max_bytes": 1048576,
            "input": "PREPARED_LOCAL_FILE",
        }
    ]


def build_source_capabilities(projection: ReadinProjection) -> dict[str, Any]:
    parsers = source_parser_catalog()
    classes = load_asset_catalog_source_schema()["$defs"]["declaredAsset"]["properties"][
        "asset_class"
    ]["enum"]
    imports = [
        o
        for o in projection.observations.values()
        if o["provenance"]["adapter"] in IMPORTED_SOURCE_ADAPTERS
    ]
    grants = [
        o
        for o in projection.observations.values()
        if o["observation_type"] == CONNECTOR_GRANT_OBSERVATION_TYPE
    ]
    assets = []
    for asset_id in sorted(projection.assets):
        entity = projection.entities[asset_id]
        binding = entity["attributes"].get("asset_catalog_binding")
        if not isinstance(binding, dict):
            continue
        available = [
            p
            for p in parsers
            if p["asset_class"] == binding["asset_class"]
            and (
                p["platform"] is None or p["platform"].casefold() == binding["platform"].casefold()
            )
        ]
        asset_imports = [o for o in imports if asset_id in o["subject_entities"]]
        grant_ids = []
        for observation in grants:
            payload = observation["content"]["structured_payload"].get("connector_grant")
            if isinstance(payload, dict) and payload.get("asset_entity_id") == asset_id:
                grant_ids.append(payload.get("grant_id"))
        parser_rows = []
        for parser in available:
            compatible = []
            for grant_id in grant_ids:
                try:
                    _matching_grant(
                        {"grant_id": grant_id, "asset_entity_id": asset_id},
                        projection,
                        asset_class=parser["asset_class"],
                        data_category=parser["data_category"],
                        observation_type=parser["observation_type"],
                        validate_profile=False,
                    )
                except (ConnectorGrantError, KeyError, TypeError, AttributeError):
                    continue
                compatible.append(grant_id)
            parser_rows.append(
                {
                    "parser": parser["parser"],
                    "label": parser["label"],
                    "input": parser["input"],
                    "compatible_grant_ids": compatible,
                    "state": "READY_FOR_LOCAL_IMPORT"
                    if compatible
                    else "INCOMPATIBLE_GRANT"
                    if grant_ids
                    else "GRANT_REQUIRED",
                    "observation_type": parser["observation_type"],
                    "data_category": parser["data_category"],
                }
            )
        assets.append(
            {
                "asset_entity_id": asset_id,
                "name": entity["canonical_name"],
                "asset_class": binding["asset_class"],
                "platform": binding["platform"],
                "parser_state": "SUPPORTED" if available else "PARSER_NOT_IMPLEMENTED",
                "parsers": parser_rows,
                "imported_record_count": len(asset_imports),
                "admitted_observation_types": sorted(
                    {o["observation_type"] for o in asset_imports}
                ),
                "latest_import_at": max(
                    (o["provenance"]["acquisition_time"] for o in asset_imports), default=None
                ),
            }
        )
    class_rows = [
        {
            "asset_class": asset_class,
            "catalog_asset_count": sum(a["asset_class"] == asset_class for a in assets),
            "imported_asset_count": sum(
                a["asset_class"] == asset_class and a["imported_record_count"] > 0 for a in assets
            ),
            "parser_state": "SUPPORTED_FOR_LISTED_FORMATS"
            if any(p["asset_class"] == asset_class for p in parsers)
            else "PARSER_NOT_IMPLEMENTED",
            "supported_formats": [p["label"] for p in parsers if p["asset_class"] == asset_class],
        }
        for asset_class in classes
    ]
    return {
        "schema_version": "readin.source-capabilities.v0.1",
        "authority_state": "NO_AUTHORITY",
        "coverage_state": "NOT_ESTABLISHED",
        "live_account_connections": "NOT_IMPLEMENTED",
        "catalog_asset_count": len(assets),
        "imported_asset_count": sum(a["imported_record_count"] > 0 for a in assets),
        "local_imported_record_count": sum(a["imported_record_count"] for a in assets),
        "parsers": parsers,
        "asset_classes": class_rows,
        "assets": assets,
        "separate_public_repository_runner": {
            "command": "collect-github-public-repository-case",
            "mode": "EXACT_TARGET_ONE_SHOT_CASE_POLICY",
            "recorded_observation_count": sum(
                o["provenance"]["adapter"] == "github-public-rest"
                for o in projection.observations.values()
            ),
        },
    }
