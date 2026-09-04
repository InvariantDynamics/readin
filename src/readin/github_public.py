"""Credential-free acquisition of one exact public GitHub repository record.

This module deliberately implements a very small network boundary.  It accepts
only GitHub owner and repository slugs, constructs the API URL itself, and does
not inherit proxy, cookie, or authentication state.  The raw response remains
available as evidence while ``observation`` contains only an allowlisted subset
of repository-level metadata.
"""

from __future__ import annotations

import ipaddress
import json
import math
import re
import socket
import ssl
import time
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    ProxyHandler,
    Request,
    build_opener,
)

_API_HOST = "api.github.com"
_API_VERSION = "2026-03-10"
_OWNER_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
_REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,100}\Z")
_SELECTED_RESPONSE_HEADERS = (
    "etag",
    "last-modified",
    "x-github-request-id",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-used",
    "x-ratelimit-reset",
    "x-ratelimit-resource",
)


class GitHubPublicError(RuntimeError):
    """A fail-closed public GitHub acquisition error."""


@dataclass(frozen=True, slots=True)
class PublicRepositoryCapture:
    """One immutable binding of raw response bytes and derived repository metadata."""

    body: bytes
    payload: dict[str, Any]
    request_url: str
    retrieved_at: str
    http_status: int
    media_type: str
    response_headers: dict[str, str]
    observation: dict[str, Any]


class _DeadlineBudget:
    """One shrinking monotonic budget with an optional wall-clock cutoff."""

    def __init__(
        self,
        timeout_seconds: float,
        *,
        wall_clock_deadline: datetime | None,
        wall_clock: Callable[[], datetime] | datetime | None,
        monotonic: Callable[[], float] | None,
    ) -> None:
        if wall_clock_deadline is not None and (
            not isinstance(wall_clock_deadline, datetime)
            or wall_clock_deadline.tzinfo is None
            or wall_clock_deadline.utcoffset() is None
        ):
            raise GitHubPublicError("wall_clock_deadline must be a timezone-aware datetime")
        self.wall_clock_deadline = (
            wall_clock_deadline.astimezone(UTC) if wall_clock_deadline is not None else None
        )
        self.wall_clock = wall_clock
        self.monotonic = time.monotonic if monotonic is None else monotonic
        self.started_at = self._monotonic_now()
        self.last_monotonic = self.started_at
        if self.wall_clock_deadline is not None:
            initial_wall_remaining = (
                self.wall_clock_deadline - _clock_moment(self.wall_clock)
            ).total_seconds()
            if initial_wall_remaining <= 0:
                raise GitHubPublicError("GitHub acquisition deadline expired")
            # A backward wall-clock correction must never enlarge the initial
            # policy-derived budget. Forward jumps are still caught below.
            self.timeout_seconds = min(timeout_seconds, initial_wall_remaining)
        else:
            self.timeout_seconds = timeout_seconds

    def _monotonic_now(self) -> float:
        try:
            value = self.monotonic()
        except Exception as error:
            raise GitHubPublicError("monotonic acquisition clock failed") from error
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise GitHubPublicError("monotonic acquisition clock returned an invalid value")
        return float(value)

    def remaining(self) -> float:
        current = self._monotonic_now()
        if current < self.last_monotonic:
            raise GitHubPublicError("monotonic acquisition clock moved backward")
        self.last_monotonic = current
        remaining = self.timeout_seconds - (current - self.started_at)
        if self.wall_clock_deadline is not None:
            wall_remaining = (
                self.wall_clock_deadline - _clock_moment(self.wall_clock)
            ).total_seconds()
            remaining = min(remaining, wall_remaining)
        if remaining <= 0:
            raise GitHubPublicError("GitHub acquisition deadline expired")
        return remaining


class _RejectRedirects(HTTPRedirectHandler):
    """Prevent urllib from converting a 3xx into a second request."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        raise GitHubPublicError(f"GitHub public API redirect refused (HTTP {code})")


def _resolve_api_github_addresses(
    resolver: Callable[..., list[tuple[Any, ...]]] | None = None,
) -> tuple[str, ...]:
    """Resolve the fixed API host and reject any non-global result.

    ``resolver`` exists to make the DNS safety decision directly testable.  A
    caller cannot use it to select a different hostname.
    """

    resolve = socket.getaddrinfo if resolver is None else resolver
    try:
        records = resolve(
            _API_HOST,
            443,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except (OSError, TypeError, ValueError) as exc:
        raise GitHubPublicError("GitHub API DNS resolution failed") from exc

    addresses: set[str] = set()
    for record in records:
        try:
            raw_address = str(record[4][0]).split("%", maxsplit=1)[0]
            address = ipaddress.ip_address(raw_address)
        except (IndexError, TypeError, ValueError) as exc:
            raise GitHubPublicError(
                "GitHub API DNS resolution returned an invalid address"
            ) from exc
        if not address.is_global:
            raise GitHubPublicError("GitHub API DNS resolution returned a non-global address")
        addresses.add(address.compressed)

    if not addresses:
        raise GitHubPublicError("GitHub API DNS resolution returned no addresses")
    return tuple(sorted(addresses))


def _default_opener() -> Any:
    # An explicit empty ProxyHandler prevents environment and macOS proxy
    # settings from routing this credential-free acquisition through an
    # ambient proxy.  No cookie or authentication handlers are installed.
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return build_opener(ProxyHandler({}), HTTPSHandler(context=context), _RejectRedirects())


def _validate_target(owner: str, repository: str) -> None:
    if not isinstance(owner, str) or _OWNER_PATTERN.fullmatch(owner) is None or "--" in owner:
        raise GitHubPublicError("invalid GitHub owner slug")
    if (
        not isinstance(repository, str)
        or _REPOSITORY_PATTERN.fullmatch(repository) is None
        or repository in {".", ".."}
        or repository.lower().endswith(".git")
    ):
        raise GitHubPublicError("invalid GitHub repository slug")


def validate_public_repository_target(owner: str, repository: str) -> None:
    """Validate the only target coordinates accepted by this adapter."""

    _validate_target(owner, repository)


def _response_header_values(headers: Any) -> dict[str, list[str]]:
    try:
        items = headers.items()
    except AttributeError as exc:
        raise GitHubPublicError("GitHub response headers are unavailable") from exc

    result: dict[str, list[str]] = {}
    for name, value in items:
        normalized_name = str(name).strip().lower()
        raw_value = str(value)
        if not normalized_name:
            continue
        if any(character in raw_value for character in ("\r", "\n", "\x00")):
            raise GitHubPublicError("GitHub response contains an invalid header value")
        result.setdefault(normalized_name, []).append(raw_value.strip())
    return result


def _one_header(headers: dict[str, list[str]], name: str, *, required: bool = False) -> str | None:
    values = headers.get(name, [])
    if not values:
        if required:
            raise GitHubPublicError(f"GitHub response is missing {name}")
        return None
    if len(values) != 1:
        raise GitHubPublicError(f"GitHub response contains ambiguous {name}")
    return values[0]


def _set_response_timeout(response: Any, timeout_seconds: float) -> bool:
    """Apply a shrinking timeout to a direct fake or CPython urllib socket."""

    candidates = [response]
    seen: set[int] = set()
    for _ in range(5):
        next_candidates: list[Any] = []
        for candidate in candidates:
            identity = id(candidate)
            if identity in seen:
                continue
            seen.add(identity)
            setter = getattr(candidate, "settimeout", None)
            if callable(setter):
                try:
                    setter(timeout_seconds)
                except (OSError, TypeError, ValueError) as error:
                    raise GitHubPublicError("could not apply the response read deadline") from error
                return True
            for attribute in ("fp", "raw", "_sock", "sock"):
                nested = getattr(candidate, attribute, None)
                if nested is not None:
                    next_candidates.append(nested)
        candidates = next_candidates
    return False


def _read_limited(
    response: Any,
    max_bytes: int,
    declared_length: int | None,
    *,
    remaining: Callable[[], float],
    require_transport_timeout: bool,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while total <= max_bytes:
        # ``HTTPResponse`` may detach its file/socket immediately after a read
        # satisfies Content-Length. The message is complete at that point, so
        # do not demand a timeout-capable transport for a redundant EOF read.
        if declared_length is not None and total == declared_length:
            break
        timeout_seconds = remaining()
        timeout_applied = _set_response_timeout(response, timeout_seconds)
        if require_transport_timeout and not timeout_applied:
            raise GitHubPublicError("response transport does not support deadline enforcement")
        requested = min(64 * 1024, max_bytes + 1 - total)
        read = getattr(response, "read1", None)
        chunk = read(requested) if callable(read) else response.read(requested)
        remaining()
        if not isinstance(chunk, bytes):
            raise GitHubPublicError("GitHub response body is not bytes")
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > max_bytes:
            raise GitHubPublicError("GitHub response exceeds the configured byte limit")

    body = b"".join(chunks)
    if declared_length is not None and len(body) != declared_length:
        raise GitHubPublicError("GitHub response length does not match Content-Length")
    return body


def _json_object(body: bytes) -> dict[str, Any]:
    try:
        text = body.decode("utf-8", errors="strict")

        def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError("duplicate JSON object key")
                value[key] = item
            return value

        def reject_nonstandard_number(value: str) -> Any:
            raise ValueError(f"non-standard JSON number: {value}")

        payload = json.loads(
            text,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_nonstandard_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise GitHubPublicError("GitHub response is not a valid UTF-8 JSON document") from exc
    if not isinstance(payload, dict):
        raise GitHubPublicError("GitHub response JSON must be an object")
    try:
        depth = _json_depth(payload)
    except RecursionError as error:
        raise GitHubPublicError("GitHub response JSON exceeds the nesting limit") from error
    if depth > 16:
        raise GitHubPublicError("GitHub response JSON exceeds the nesting limit")
    return payload


def _json_depth(value: Any) -> int:
    if isinstance(value, dict):
        return 1 + max((_json_depth(item) for item in value.values()), default=0)
    if isinstance(value, list):
        return 1 + max((_json_depth(item) for item in value), default=0)
    return 0


def _require_matching_target(payload: dict[str, Any], owner: str, repository: str) -> None:
    payload_owner = payload.get("owner")
    owner_login = payload_owner.get("login") if isinstance(payload_owner, dict) else None
    owner_type = payload_owner.get("type") if isinstance(payload_owner, dict) else None
    name = payload.get("name")
    full_name = payload.get("full_name")
    expected_full_name = f"{owner}/{repository}"
    repository_id = payload.get("id")
    node_id = payload.get("node_id")
    owner_id = payload_owner.get("id") if isinstance(payload_owner, dict) else None
    if (
        not isinstance(owner_login, str)
        or owner_login.casefold() != owner.casefold()
        or not isinstance(name, str)
        or name.casefold() != repository.casefold()
        or not isinstance(full_name, str)
        or full_name.casefold() != expected_full_name.casefold()
    ):
        raise GitHubPublicError("GitHub response identity does not match the requested repository")
    if (
        not _positive_integer(repository_id)
        or not isinstance(node_id, str)
        or not 1 <= len(node_id) <= 256
        or not _positive_integer(owner_id)
        or owner_type not in {"Organization", "User"}
    ):
        raise GitHubPublicError("GitHub response is missing stable repository identity fields")
    if payload.get("private") is not False or payload.get("visibility") != "public":
        raise GitHubPublicError("GitHub response does not describe a public repository")
    _require_exact_public_url(
        payload.get("url"),
        host="api.github.com",
        expected_path=f"/repos/{full_name}",
        label="API",
    )
    _require_exact_public_url(
        payload.get("html_url"),
        host="github.com",
        expected_path=f"/{full_name}",
        label="HTML",
    )


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _require_exact_public_url(value: Any, *, host: str, expected_path: str, label: str) -> None:
    if not isinstance(value, str) or len(value) > 512:
        raise GitHubPublicError(f"GitHub response contains an invalid repository {label} URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise GitHubPublicError(
            f"GitHub response contains an invalid repository {label} URL"
        ) from error
    if (
        parsed.scheme != "https"
        or parsed.hostname != host
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path.casefold() != expected_path.casefold()
        or parsed.query
        or parsed.fragment
    ):
        raise GitHubPublicError(f"GitHub response contains an invalid repository {label} URL")


def _bounded_string(maximum: int, *, optional: bool = False) -> Callable[[Any], bool]:
    def validate(value: Any) -> bool:
        if optional and value is None:
            return True
        return isinstance(value, str) and 1 <= len(value) <= maximum

    return validate


def _valid_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _selected_headers(headers: dict[str, list[str]]) -> dict[str, str]:
    selected: dict[str, str] = {}
    for name in _SELECTED_RESPONSE_HEADERS:
        values = headers.get(name, [])
        if not values:
            continue
        if len(values) != 1:
            raise GitHubPublicError(f"GitHub response contains ambiguous {name}")
        value = values[0]
        if len(value) > 512 or any(ord(character) < 0x20 for character in value):
            raise GitHubPublicError(f"GitHub response contains an invalid {name}")
        selected[name] = value
    return selected


def _repository_observation(payload: dict[str, Any], owner: str, repository: str) -> dict[str, Any]:
    repository_metadata: dict[str, Any] = {}
    validators: dict[str, Callable[[Any], bool]] = {
        "id": _valid_integer,
        "node_id": _bounded_string(256),
        "name": _bounded_string(100),
        "full_name": _bounded_string(202),
        "description": _bounded_string(1024, optional=True),
        "private": lambda value: isinstance(value, bool),
        "fork": lambda value: isinstance(value, bool),
        "archived": lambda value: isinstance(value, bool),
        "disabled": lambda value: isinstance(value, bool),
        "visibility": _bounded_string(32),
        "default_branch": _bounded_string(255),
        "language": _bounded_string(100, optional=True),
        "created_at": _bounded_string(64),
        "updated_at": _bounded_string(64),
        "pushed_at": _bounded_string(64, optional=True),
        "size": _valid_integer,
        "stargazers_count": _valid_integer,
        "watchers_count": _valid_integer,
        "forks_count": _valid_integer,
        "open_issues_count": _valid_integer,
    }
    for field, validator in validators.items():
        if field not in payload:
            continue
        value = payload[field]
        if not validator(value):
            raise GitHubPublicError(
                f"GitHub response contains an invalid repository field: {field}"
            )
        repository_metadata[field] = value

    if "topics" in payload:
        topics = payload["topics"]
        if (
            not isinstance(topics, list)
            or len(topics) > 20
            or not all(isinstance(topic, str) and 1 <= len(topic) <= 50 for topic in topics)
        ):
            raise GitHubPublicError("GitHub response contains invalid repository topics")
        repository_metadata["topics"] = list(topics)

    if "license" in payload:
        license_record = payload["license"]
        if license_record is None:
            repository_metadata["license_spdx_id"] = None
        elif isinstance(license_record, dict) and _bounded_string(64, optional=True)(
            license_record.get("spdx_id")
        ):
            repository_metadata["license_spdx_id"] = license_record.get("spdx_id")
        else:
            raise GitHubPublicError("GitHub response contains invalid repository license metadata")

    return {
        "schema_version": "readin.github-public-repository-observation.v0.1",
        "source_kind": "GITHUB_PUBLIC_REPOSITORY_API",
        "target": {"owner": owner, "repository": repository},
        "owner": {
            "login": payload["owner"]["login"],
            "id": payload["owner"]["id"],
            "type": payload["owner"]["type"],
        },
        "repository": repository_metadata,
        "authority_state": "NO_AUTHORITY",
        "verification_state": "CAPTURED_NOT_INDEPENDENTLY_VERIFIED",
        "coverage_state": "SINGLE_ENDPOINT_RESPONSE_ONLY",
    }


def parse_public_repository_response(
    body: bytes,
    owner: str,
    repository: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate stored response bytes and reproduce their allowlisted observation."""

    validate_public_repository_target(owner, repository)
    if not isinstance(body, bytes):
        raise GitHubPublicError("GitHub response body is not bytes")
    payload = _json_object(body)
    _require_matching_target(payload, owner, repository)
    return payload, _repository_observation(payload, owner, repository)


def _retrieved_at(now: Callable[[], datetime] | datetime | None) -> str:
    moment = _clock_moment(now)
    return moment.isoformat().replace("+00:00", "Z")


def _clock_moment(now: Callable[[], datetime] | datetime | None) -> datetime:
    try:
        moment = datetime.now(UTC) if now is None else (now() if callable(now) else now)
    except Exception as error:
        raise GitHubPublicError("retrieval clock failed") from error
    if not isinstance(moment, datetime) or moment.tzinfo is None or moment.utcoffset() is None:
        raise GitHubPublicError("retrieval clock must return a timezone-aware datetime")
    return moment.astimezone(UTC)


def fetch_public_repository(
    owner: str,
    repository: str,
    *,
    max_bytes: int = 1_048_576,
    timeout_seconds: float = 15.0,
    wall_clock_deadline: datetime | None = None,
    opener: Any = None,
    now: Callable[[], datetime] | datetime | None = None,
    monotonic: Callable[[], float] | None = None,
) -> PublicRepositoryCapture:
    """Fetch metadata for one exact public repository without credentials.

    The function performs one GET and no retries. ``timeout_seconds`` is one
    aggregate monotonic admission budget beginning before DNS. It accepts only
    a successful 200 response from the exact URL and intentionally omits
    response bodies from all error messages.
    """

    validate_public_repository_target(owner, repository)
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise GitHubPublicError("max_bytes must be a positive integer")
    if (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, (int, float))
        or not math.isfinite(timeout_seconds)
        or timeout_seconds <= 0
    ):
        raise GitHubPublicError("timeout_seconds must be positive and finite")

    budget = _DeadlineBudget(
        float(timeout_seconds),
        wall_clock_deadline=wall_clock_deadline,
        wall_clock=now,
        monotonic=monotonic,
    )
    budget.remaining()
    _resolve_api_github_addresses()
    request_url = f"https://{_API_HOST}/repos/{owner}/{repository}"
    request = Request(
        request_url,
        method="GET",
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
            "User-Agent": "READIN/0.1",
            "Accept-Encoding": "identity",
        },
    )
    client = _default_opener() if opener is None else opener

    try:
        request_timeout = budget.remaining()
        if hasattr(client, "open"):
            response = client.open(request, timeout=request_timeout)
        elif callable(client):
            response = client(request, timeout=request_timeout)
        else:
            raise GitHubPublicError("opener must be callable or provide open()")
    except GitHubPublicError:
        raise
    except HTTPError as exc:
        exc.close()
        raise GitHubPublicError(f"GitHub public API returned HTTP {exc.code}") from None
    except (HTTPException, URLError, OSError, TimeoutError):
        raise GitHubPublicError("GitHub public API request failed") from None

    try:
        with closing(response):
            budget.remaining()
            status = getattr(response, "status", None)
            if status is None and hasattr(response, "getcode"):
                status = response.getcode()
            if status != 200:
                raise GitHubPublicError(f"GitHub public API returned HTTP {status}")

            if hasattr(response, "geturl") and response.geturl() != request_url:
                raise GitHubPublicError("GitHub public API response URL does not match the request")

            headers = _response_header_values(response.headers)
            raw_content_type = _one_header(headers, "content-type", required=True)
            assert raw_content_type is not None
            content_type_parts = [part.strip() for part in raw_content_type.split(";")]
            media_type = content_type_parts[0].lower()
            if media_type != "application/json" and not media_type.endswith("+json"):
                raise GitHubPublicError("GitHub response is not a JSON media type")
            for parameter in content_type_parts[1:]:
                name, separator, value = parameter.partition("=")
                if name.lower() == "charset" and (
                    not separator or value.strip('"').lower() not in {"utf-8", "utf8"}
                ):
                    raise GitHubPublicError("GitHub response declares a non-UTF-8 charset")

            content_encoding = _one_header(headers, "content-encoding")
            if content_encoding is not None and content_encoding.lower() != "identity":
                raise GitHubPublicError("GitHub response uses an unsupported content encoding")

            raw_length = _one_header(headers, "content-length")
            declared_length: int | None = None
            if raw_length is not None:
                if not raw_length.isdecimal():
                    raise GitHubPublicError("GitHub response has an invalid Content-Length")
                declared_length = int(raw_length)
                if declared_length > max_bytes:
                    raise GitHubPublicError("GitHub response exceeds the configured byte limit")

            body = _read_limited(
                response,
                max_bytes,
                declared_length,
                remaining=budget.remaining,
                require_transport_timeout=opener is None,
            )
    except GitHubPublicError:
        raise
    except (HTTPException, URLError, OSError, TimeoutError):
        raise GitHubPublicError("GitHub public API response read failed") from None

    budget.remaining()
    retrieved_at = _retrieved_at(now)
    if wall_clock_deadline is not None and datetime.fromisoformat(
        retrieved_at.replace("Z", "+00:00")
    ) >= wall_clock_deadline.astimezone(UTC):
        raise GitHubPublicError("GitHub acquisition deadline expired")
    payload, observation = parse_public_repository_response(body, owner, repository)
    selected_headers = _selected_headers(headers)

    return PublicRepositoryCapture(
        body=body,
        payload=payload,
        request_url=request_url,
        retrieved_at=retrieved_at,
        http_status=200,
        media_type=media_type,
        response_headers=selected_headers,
        observation=observation,
    )
