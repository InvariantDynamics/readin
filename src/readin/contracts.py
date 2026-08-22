"""JSON Schema loading and validation for READIN events."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


class ContractViolation(ValueError):
    """Raised when an event fails the closed READIN contract."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__("; ".join(messages))


def _development_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "v0.1" / "readin-event.schema.json"


@lru_cache(maxsize=1)
def load_event_schema() -> dict[str, Any]:
    """Load the packaged schema, falling back to the source-tree contract."""

    packaged = files("readin").joinpath("schemas/v0.1/readin-event.schema.json")
    if packaged.is_file():
        return json.loads(packaged.read_text(encoding="utf-8"))

    source_path = _development_schema_path()
    if not source_path.is_file():
        raise FileNotFoundError(f"READIN event schema not found: {source_path}")
    return json.loads(source_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def event_validator() -> Draft202012Validator:
    schema = load_event_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_event(event: dict[str, Any]) -> None:
    """Validate one event and retain every validation failure."""

    errors = sorted(event_validator().iter_errors(event), key=lambda error: list(error.path))
    if not errors:
        return

    messages: list[str] = []
    for error in errors:
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        messages.append(f"{location}: {error.message}")
    raise ContractViolation(messages)
