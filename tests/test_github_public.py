from __future__ import annotations

import io
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from http.client import IncompleteRead
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request

import pytest

import readin.github_public as github_public
from readin.github_public import (
    GitHubPublicError,
    PublicRepositoryCapture,
    fetch_public_repository,
)


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        status: int = 200,
        headers: dict[str, str] | list[tuple[str, str]] | None = None,
        url: str = "https://api.github.com/repos/InvariantDynamics/readin",
        ignore_read_limit: bool = False,
    ) -> None:
        self.body = body
        self.status = status
        self.headers = dict({"Content-Type": "application/json"} if headers is None else headers)
        self.url = url
        self.ignore_read_limit = ignore_read_limit
        self.offset = 0
        self.read_sizes: list[int] = []
        self.closed = False

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        if self.offset >= len(self.body):
            return b""
        end = len(self.body) if self.ignore_read_limit else self.offset + size
        chunk = self.body[self.offset : end]
        self.offset += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self.url

    def close(self) -> None:
        self.closed = True


class FakeOpener:
    def __init__(self, result: FakeResponse | BaseException) -> None:
        self.result = result
        self.calls: list[tuple[Request, float]] = []

    def open(self, request: Request, *, timeout: float) -> FakeResponse:
        self.calls.append((request, timeout))
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


@pytest.fixture(autouse=True)
def allow_test_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        github_public,
        "_resolve_api_github_addresses",
        lambda: ("140.82.112.5",),
    )


def repository_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": 1234,
        "node_id": "R_repo",
        "name": "readin",
        "full_name": "InvariantDynamics/readin",
        "owner": {
            "login": "InvariantDynamics",
            "id": 9876,
            "type": "Organization",
            "html_url": "https://github.com/InvariantDynamics",
            "email": "not-for-observation@example.invalid",
        },
        "description": "Public READIN repository",
        "private": False,
        "fork": False,
        "archived": False,
        "disabled": False,
        "visibility": "public",
        "default_branch": "main",
        "language": "Python",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-09-03T12:00:00Z",
        "pushed_at": "2026-09-03T11:00:00Z",
        "size": 42,
        "stargazers_count": 3,
        "watchers_count": 3,
        "forks_count": 1,
        "open_issues_count": 0,
        "topics": ["osint", "provenance"],
        "license": {
            "spdx_id": "Apache-2.0",
            "url": "https://api.github.com/licenses/apache-2.0",
        },
        "html_url": "https://github.com/InvariantDynamics/readin",
        "url": "https://api.github.com/repos/InvariantDynamics/readin",
        "contributors_url": ("https://api.github.com/repos/InvariantDynamics/readin/contributors"),
        "subscribers": [{"login": "excluded-person"}],
    }
    payload.update(updates)
    return payload


def encoded_payload(**updates: Any) -> bytes:
    return json.dumps(repository_payload(**updates), separators=(",", ":")).encode()


def test_fetch_uses_exact_credential_free_request_and_returns_capture() -> None:
    body = encoded_payload()
    response = FakeResponse(
        body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(body)),
            "Content-Encoding": "identity",
            "ETag": 'W/"record-1"',
            "X-GitHub-Request-Id": "REQ:123",
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "59",
            "X-RateLimit-Used": "1",
            "X-RateLimit-Reset": "1788451200",
            "X-RateLimit-Resource": "core",
            "Set-Cookie": "must-not-be-persisted=1",
        },
    )
    opener = FakeOpener(response)

    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        opener=opener,
        now=datetime(2026, 9, 3, 12, 34, 56, tzinfo=UTC),
        monotonic=lambda: 0.0,
    )

    assert isinstance(capture, PublicRepositoryCapture)
    assert capture.body == body
    assert capture.payload["html_url"] == "https://github.com/InvariantDynamics/readin"
    assert capture.request_url == "https://api.github.com/repos/InvariantDynamics/readin"
    assert capture.retrieved_at == "2026-09-03T12:34:56Z"
    assert capture.http_status == 200
    assert capture.media_type == "application/json"
    assert capture.response_headers == {
        "etag": 'W/"record-1"',
        "x-github-request-id": "REQ:123",
        "x-ratelimit-limit": "60",
        "x-ratelimit-remaining": "59",
        "x-ratelimit-used": "1",
        "x-ratelimit-reset": "1788451200",
        "x-ratelimit-resource": "core",
    }
    assert response.closed is True

    assert len(opener.calls) == 1
    request, timeout = opener.calls[0]
    assert request.full_url == "https://api.github.com/repos/InvariantDynamics/readin"
    assert request.get_method() == "GET"
    assert timeout == 15.0
    request_headers = {name.lower(): value for name, value in request.header_items()}
    assert request_headers == {
        "accept": "application/vnd.github+json",
        "x-github-api-version": "2026-03-10",
        "user-agent": "READIN/0.1",
        "accept-encoding": "identity",
    }
    assert "authorization" not in request_headers
    assert "cookie" not in request_headers


def test_observation_is_repository_only_and_omits_people_and_url_fields() -> None:
    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        opener=FakeOpener(FakeResponse(encoded_payload())),
        now=lambda: datetime(2026, 9, 3, tzinfo=UTC),
    )

    assert capture.observation == {
        "schema_version": "readin.github-public-repository-observation.v0.1",
        "source_kind": "GITHUB_PUBLIC_REPOSITORY_API",
        "target": {"owner": "InvariantDynamics", "repository": "readin"},
        "owner": {"login": "InvariantDynamics", "id": 9876, "type": "Organization"},
        "repository": {
            "id": 1234,
            "node_id": "R_repo",
            "name": "readin",
            "full_name": "InvariantDynamics/readin",
            "description": "Public READIN repository",
            "private": False,
            "fork": False,
            "archived": False,
            "disabled": False,
            "visibility": "public",
            "default_branch": "main",
            "language": "Python",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-09-03T12:00:00Z",
            "pushed_at": "2026-09-03T11:00:00Z",
            "size": 42,
            "stargazers_count": 3,
            "watchers_count": 3,
            "forks_count": 1,
            "open_issues_count": 0,
            "topics": ["osint", "provenance"],
            "license_spdx_id": "Apache-2.0",
        },
        "authority_state": "NO_AUTHORITY",
        "verification_state": "CAPTURED_NOT_INDEPENDENTLY_VERIFIED",
        "coverage_state": "SINGLE_ENDPOINT_RESPONSE_ONLY",
    }
    serialized = json.dumps(capture.observation)
    assert "contributors" not in serialized
    assert "subscribers" not in serialized
    assert "html_url" not in serialized
    assert "email" not in serialized


def test_capture_dataclass_rejects_field_reassignment() -> None:
    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        opener=FakeOpener(FakeResponse(encoded_payload())),
    )

    with pytest.raises(FrozenInstanceError):
        capture.http_status = 201  # type: ignore[misc]


@pytest.mark.parametrize(
    ("owner", "repository"),
    [
        ("", "readin"),
        ("-owner", "readin"),
        ("owner-", "readin"),
        ("owner--name", "readin"),
        ("owner/name", "readin"),
        ("owner%2Fname", "readin"),
        ("owner", ""),
        ("owner", "../secret"),
        ("owner", "repo?ref=other"),
        ("owner", "repo%2Fother"),
        ("owner", "répo"),
        ("owner", "."),
        ("owner", ".."),
        ("owner", "repository.git"),
    ],
)
def test_invalid_target_is_rejected_before_network(owner: str, repository: str) -> None:
    opener = FakeOpener(FakeResponse(encoded_payload()))

    with pytest.raises(GitHubPublicError, match="invalid GitHub"):
        fetch_public_repository(owner, repository, opener=opener)

    assert opener.calls == []


def test_resolver_returns_only_global_addresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()

    def resolver(*args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        assert args == ("api.github.com", 443)
        assert kwargs == {
            "family": github_public.socket.AF_UNSPEC,
            "type": github_public.socket.SOCK_STREAM,
            "proto": github_public.socket.IPPROTO_TCP,
        }
        return [
            (2, 1, 6, "", ("140.82.112.5", 443)),
            (10, 1, 6, "", ("2606:50c0:8000::154", 443, 0, 0)),
            (2, 1, 6, "", ("140.82.112.5", 443)),
        ]

    assert github_public._resolve_api_github_addresses(resolver) == (
        "140.82.112.5",
        "2606:50c0:8000::154",
    )


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1"])
def test_resolver_rejects_any_non_global_address(
    address: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.undo()
    records = [
        (2, 1, 6, "", ("140.82.112.5", 443)),
        (2, 1, 6, "", (address, 443)),
    ]

    with pytest.raises(GitHubPublicError, match="non-global"):
        github_public._resolve_api_github_addresses(lambda *args, **kwargs: records)


def test_resolver_rejects_empty_and_invalid_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()

    with pytest.raises(GitHubPublicError, match="no addresses"):
        github_public._resolve_api_github_addresses(lambda *args, **kwargs: [])
    with pytest.raises(GitHubPublicError, match="invalid address"):
        github_public._resolve_api_github_addresses(
            lambda *args, **kwargs: [(2, 1, 6, "", ("not-an-ip", 443))]
        )


def test_non_200_is_rejected_without_reading_or_exposing_body() -> None:
    response = FakeResponse(b'{"secret":"response body"}', status=403)

    with pytest.raises(GitHubPublicError, match="HTTP 403") as error:
        fetch_public_repository("InvariantDynamics", "readin", opener=FakeOpener(response))

    assert "response body" not in str(error.value)
    assert response.read_sizes == []
    assert response.closed is True


def test_http_error_is_sanitized_and_not_retried() -> None:
    error = HTTPError(
        "https://api.github.com/repos/InvariantDynamics/readin",
        404,
        "response body must not escape",
        {},
        io.BytesIO(b'{"secret":"response body"}'),
    )
    opener = FakeOpener(error)

    with pytest.raises(GitHubPublicError, match="HTTP 404") as raised:
        fetch_public_repository("InvariantDynamics", "readin", opener=opener)

    assert "response body" not in str(raised.value)
    assert len(opener.calls) == 1


def test_transport_error_is_sanitized_and_not_retried() -> None:
    opener = FakeOpener(URLError("credential-bearing diagnostic"))

    with pytest.raises(GitHubPublicError, match="request failed") as raised:
        fetch_public_repository("InvariantDynamics", "readin", opener=opener)

    assert "credential-bearing" not in str(raised.value)
    assert len(opener.calls) == 1


def test_response_read_error_does_not_expose_partial_body() -> None:
    class BrokenResponse(FakeResponse):
        def read(self, size: int) -> bytes:
            raise IncompleteRead(b"partial secret response body", 20)

    response = BrokenResponse(encoded_payload())

    with pytest.raises(GitHubPublicError, match="response read failed") as raised:
        fetch_public_repository("InvariantDynamics", "readin", opener=FakeOpener(response))

    assert "partial secret" not in str(raised.value)
    assert response.closed is True


def test_changed_response_url_is_rejected() -> None:
    response = FakeResponse(
        encoded_payload(),
        url="https://example.invalid/repos/InvariantDynamics/readin",
    )

    with pytest.raises(GitHubPublicError, match="response URL"):
        fetch_public_repository("InvariantDynamics", "readin", opener=FakeOpener(response))


@pytest.mark.parametrize(
    ("headers", "message"),
    [
        ({}, "missing content-type"),
        ({"Content-Type": "text/html"}, "not a JSON media type"),
        (
            {"Content-Type": "application/json", "Content-Encoding": "gzip"},
            "unsupported content encoding",
        ),
        (
            {"Content-Type": "application/json", "Content-Length": "not-a-number"},
            "invalid Content-Length",
        ),
    ],
)
def test_response_contract_rejects_invalid_headers(headers: dict[str, str], message: str) -> None:
    response = FakeResponse(encoded_payload(), headers=headers)

    with pytest.raises(GitHubPublicError, match=message):
        fetch_public_repository("InvariantDynamics", "readin", opener=FakeOpener(response))


def test_declared_oversize_is_rejected_before_body_read() -> None:
    response = FakeResponse(
        encoded_payload(),
        headers={"Content-Type": "application/json", "Content-Length": "11"},
    )

    with pytest.raises(GitHubPublicError, match="exceeds"):
        fetch_public_repository(
            "InvariantDynamics", "readin", max_bytes=10, opener=FakeOpener(response)
        )

    assert response.read_sizes == []


def test_streaming_limit_reads_at_most_max_plus_one() -> None:
    response = FakeResponse(b"x" * 11, ignore_read_limit=True)

    with pytest.raises(GitHubPublicError, match="exceeds"):
        fetch_public_repository(
            "InvariantDynamics", "readin", max_bytes=10, opener=FakeOpener(response)
        )

    assert response.read_sizes == [11]


def test_content_length_must_match_actual_body() -> None:
    body = encoded_payload()
    response = FakeResponse(
        body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body) + 1)},
    )

    with pytest.raises(GitHubPublicError, match="does not match"):
        fetch_public_repository("InvariantDynamics", "readin", opener=FakeOpener(response))


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"\xff", "not a valid UTF-8 JSON"),
        (b"{not json}", "not a valid UTF-8 JSON"),
        (
            b'{"name":"readin","full_name":"InvariantDynamics/readin",'
            b'"owner":{"login":"InvariantDynamics"},"unexpected":NaN}',
            "not a valid UTF-8 JSON",
        ),
        (b"[]", "must be an object"),
        (
            b'{"name":"readin","name":"other","full_name":"InvariantDynamics/readin",'
            b'"owner":{"login":"InvariantDynamics"}}',
            "not a valid UTF-8 JSON",
        ),
    ],
)
def test_invalid_json_is_rejected(body: bytes, message: str) -> None:
    with pytest.raises(GitHubPublicError, match=message):
        fetch_public_repository(
            "InvariantDynamics", "readin", opener=FakeOpener(FakeResponse(body))
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"name": "different"},
        {"full_name": "SomeoneElse/readin"},
        {"owner": {"login": "SomeoneElse"}},
        {"owner": None},
    ],
)
def test_response_identity_must_match_exact_target(updates: dict[str, Any]) -> None:
    with pytest.raises(GitHubPublicError, match="identity does not match"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=FakeOpener(FakeResponse(encoded_payload(**updates))),
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"private": True},
        {"visibility": "private"},
        {"id": 0},
        {"node_id": ""},
        {"owner": {"login": "InvariantDynamics", "id": 0}},
        {"url": "https://127.0.0.1/repos/InvariantDynamics/readin"},
        {"html_url": "https://github.com/InvariantDynamics/other"},
    ],
)
def test_response_must_be_a_stably_identified_public_repository(
    updates: dict[str, Any],
) -> None:
    with pytest.raises(GitHubPublicError):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=FakeOpener(FakeResponse(encoded_payload(**updates))),
        )


def test_canonical_response_case_may_differ_from_case_insensitive_target() -> None:
    capture = fetch_public_repository(
        "invariantdynamics",
        "READIN",
        opener=FakeOpener(
            FakeResponse(
                encoded_payload(),
                url="https://api.github.com/repos/invariantdynamics/READIN",
            )
        ),
    )

    assert capture.payload["full_name"] == "InvariantDynamics/readin"
    assert capture.observation["target"] == {
        "owner": "invariantdynamics",
        "repository": "READIN",
    }


@pytest.mark.parametrize(
    "updates",
    [
        {"id": True},
        {"private": "false"},
        {"topics": ["valid", 3]},
        {"license": {"spdx_id": 7}},
        {"stargazers_count": -1},
    ],
)
def test_invalid_allowlisted_repository_field_is_rejected(updates: dict[str, Any]) -> None:
    with pytest.raises(GitHubPublicError, match="GitHub response"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=FakeOpener(FakeResponse(encoded_payload(**updates))),
        )


@pytest.mark.parametrize(
    ("max_bytes", "timeout_seconds", "message"),
    [
        (0, 15.0, "max_bytes"),
        (True, 15.0, "max_bytes"),
        (100, 0, "timeout_seconds"),
        (100, float("inf"), "timeout_seconds"),
        (100, True, "timeout_seconds"),
    ],
)
def test_invalid_resource_limits_are_rejected(
    max_bytes: Any, timeout_seconds: Any, message: str
) -> None:
    with pytest.raises(GitHubPublicError, match=message):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            max_bytes=max_bytes,
            timeout_seconds=timeout_seconds,
            opener=FakeOpener(FakeResponse(encoded_payload())),
        )


def test_retrieval_clock_must_be_timezone_aware() -> None:
    with pytest.raises(GitHubPublicError, match="timezone-aware"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=FakeOpener(FakeResponse(encoded_payload())),
            now=datetime(2026, 9, 3),
        )


def test_retrieval_timestamp_preserves_subsecond_ordering() -> None:
    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        opener=FakeOpener(FakeResponse(encoded_payload())),
        now=datetime(2026, 9, 3, 12, 34, 56, 123456, tzinfo=UTC),
    )

    assert capture.retrieved_at == "2026-09-03T12:34:56.123456Z"


def test_wall_clock_deadline_expiring_during_dns_refuses_http_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cutoff = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    clock = {"now": datetime(2026, 9, 4, 11, 59, 59, 999999, tzinfo=UTC)}
    opener = FakeOpener(FakeResponse(encoded_payload()))

    def resolve_then_expire() -> tuple[str, ...]:
        clock["now"] = cutoff
        return ("140.82.112.5",)

    monkeypatch.setattr(github_public, "_resolve_api_github_addresses", resolve_then_expire)

    with pytest.raises(GitHubPublicError, match="deadline expired"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=opener,
            now=lambda: clock["now"],
            monotonic=lambda: 0.0,
            wall_clock_deadline=cutoff,
        )

    assert opener.calls == []


def test_dns_time_is_deducted_from_the_single_monotonic_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"monotonic": 0.0}
    opener = FakeOpener(FakeResponse(encoded_payload()))

    def resolve_after_three_quarters_of_budget() -> tuple[str, ...]:
        clock["monotonic"] = 0.75
        return ("140.82.112.5",)

    monkeypatch.setattr(
        github_public,
        "_resolve_api_github_addresses",
        resolve_after_three_quarters_of_budget,
    )

    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        opener=opener,
        timeout_seconds=1.0,
        monotonic=lambda: clock["monotonic"],
    )

    assert capture.http_status == 200
    assert len(opener.calls) == 1
    assert opener.calls[0][1] == pytest.approx(0.25)


def test_dns_consuming_entire_monotonic_budget_refuses_http_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"monotonic": 0.0}
    opener = FakeOpener(FakeResponse(encoded_payload()))

    def resolve_after_budget() -> tuple[str, ...]:
        clock["monotonic"] = 1.0
        return ("140.82.112.5",)

    monkeypatch.setattr(github_public, "_resolve_api_github_addresses", resolve_after_budget)

    with pytest.raises(GitHubPublicError, match="deadline expired"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=opener,
            timeout_seconds=1.0,
            monotonic=lambda: clock["monotonic"],
        )

    assert opener.calls == []


def test_backward_wall_clock_step_cannot_expand_initial_policy_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cutoff = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    clock = {
        "monotonic": 0.0,
        "wall": datetime(2026, 9, 4, 11, 59, 59, 900000, tzinfo=UTC),
    }
    response = FakeResponse(encoded_payload())

    class RollbackOpener(FakeOpener):
        def open(self, request: Request, *, timeout: float) -> FakeResponse:
            result = super().open(request, timeout=timeout)
            clock["monotonic"] = 0.11
            return result

    opener = RollbackOpener(response)

    def resolve_after_wall_rollback() -> tuple[str, ...]:
        clock["monotonic"] = 0.04
        clock["wall"] = datetime(2026, 9, 4, 10, 59, 59, 900000, tzinfo=UTC)
        return ("140.82.112.5",)

    monkeypatch.setattr(
        github_public,
        "_resolve_api_github_addresses",
        resolve_after_wall_rollback,
    )

    with pytest.raises(GitHubPublicError, match="deadline expired"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=opener,
            timeout_seconds=15.0,
            wall_clock_deadline=cutoff,
            now=lambda: clock["wall"],
            monotonic=lambda: clock["monotonic"],
        )

    assert len(opener.calls) == 1
    assert opener.calls[0][1] == pytest.approx(0.06)
    assert response.closed is True


def test_slow_drip_body_exhausts_total_budget_and_closes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = {"monotonic": 0.0}

    class SlowDripResponse(FakeResponse):
        def __init__(self) -> None:
            super().__init__(encoded_payload())
            self.applied_timeouts: list[float] = []

        def settimeout(self, timeout: float) -> None:
            self.applied_timeouts.append(timeout)

        def read1(self, size: int) -> bytes:
            self.read_sizes.append(size)
            clock["monotonic"] += 0.4
            if self.offset >= len(self.body):
                return b""
            chunk = self.body[self.offset : self.offset + 1]
            self.offset += len(chunk)
            return chunk

    response = SlowDripResponse()
    opener = FakeOpener(response)
    monkeypatch.setattr(github_public, "_default_opener", lambda: opener)

    with pytest.raises(GitHubPublicError, match="deadline expired") as raised:
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            timeout_seconds=1.0,
            monotonic=lambda: clock["monotonic"],
        )

    assert len(opener.calls) == 1
    assert response.closed is True
    assert response.applied_timeouts == pytest.approx([1.0, 0.6, 0.2])
    assert "partial" not in str(raised.value)


def test_default_urllib_path_reaches_nested_socket_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(encoded_payload())
    applied_timeouts: list[float] = []

    class Socket:
        def settimeout(self, timeout: float) -> None:
            applied_timeouts.append(timeout)

    class Raw:
        _sock = Socket()

    class Buffered:
        raw = Raw()

    response.fp = Buffered()  # type: ignore[attr-defined]
    opener = FakeOpener(response)
    monkeypatch.setattr(github_public, "_default_opener", lambda: opener)

    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        monotonic=lambda: 0.0,
    )

    assert capture.http_status == 200
    assert applied_timeouts
    assert all(timeout == 15.0 for timeout in applied_timeouts)


def test_content_length_completion_does_not_require_redundant_eof_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    body = encoded_payload()
    applied_timeouts: list[float] = []

    class Socket:
        def settimeout(self, timeout: float) -> None:
            applied_timeouts.append(timeout)

    class Raw:
        _sock = Socket()

    class Buffered:
        raw = Raw()

    class DetachingResponse(FakeResponse):
        def read1(self, size: int) -> bytes:
            chunk = self.read(size)
            if self.offset == len(self.body):
                self.fp = None
            return chunk

    response = DetachingResponse(
        body,
        headers={"Content-Type": "application/json", "Content-Length": str(len(body))},
    )
    response.fp = Buffered()  # type: ignore[attr-defined]
    monkeypatch.setattr(github_public, "_default_opener", lambda: FakeOpener(response))

    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        monotonic=lambda: 0.0,
    )

    assert capture.body == body
    assert applied_timeouts == [15.0]
    assert response.closed is True


def test_default_urllib_path_fails_closed_without_socket_timeout_support(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeResponse(encoded_payload())
    monkeypatch.setattr(github_public, "_default_opener", lambda: FakeOpener(response))

    with pytest.raises(GitHubPublicError, match="does not support deadline enforcement"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            monotonic=lambda: 0.0,
        )

    assert response.closed is True


def test_deadline_and_monotonic_clocks_fail_closed_before_http_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opener = FakeOpener(FakeResponse(encoded_payload()))

    with pytest.raises(GitHubPublicError, match="wall_clock_deadline.*timezone-aware"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=opener,
            wall_clock_deadline=datetime(2026, 9, 4, 12, 0),
        )

    with pytest.raises(GitHubPublicError, match="invalid value"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=opener,
            monotonic=lambda: float("nan"),
        )

    def failed_wall_clock() -> datetime:
        raise RuntimeError("clock implementation detail")

    with pytest.raises(GitHubPublicError, match="retrieval clock failed") as raised:
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=opener,
            now=failed_wall_clock,
            wall_clock_deadline=datetime(2026, 9, 4, 12, 0, tzinfo=UTC),
        )
    assert "implementation detail" not in str(raised.value)

    monotonic_clock = {"value": 1.0}

    def resolve_after_backward_jump() -> tuple[str, ...]:
        monotonic_clock["value"] = 0.5
        return ("140.82.112.5",)

    monkeypatch.setattr(
        github_public,
        "_resolve_api_github_addresses",
        resolve_after_backward_jump,
    )
    with pytest.raises(GitHubPublicError, match="moved backward"):
        fetch_public_repository(
            "InvariantDynamics",
            "readin",
            opener=opener,
            monotonic=lambda: monotonic_clock["value"],
        )

    assert opener.calls == []


def test_default_opener_has_no_proxy_and_refuses_redirects() -> None:
    opener = github_public._default_opener()

    # urllib elides an explicitly empty ProxyHandler from the final handler
    # list; its absence proves that no environment-derived proxy handler was
    # installed.
    assert not any(isinstance(handler, ProxyHandler) for handler in opener.handlers)
    assert any(isinstance(handler, github_public._RejectRedirects) for handler in opener.handlers)


def test_callable_opener_is_supported() -> None:
    calls: list[tuple[Request, float]] = []

    def open_request(request: Request, *, timeout: float) -> FakeResponse:
        calls.append((request, timeout))
        return FakeResponse(encoded_payload())

    capture = fetch_public_repository(
        "InvariantDynamics",
        "readin",
        opener=open_request,
        timeout_seconds=3,
        monotonic=lambda: 0.0,
    )

    assert capture.http_status == 200
    assert len(calls) == 1
    assert calls[0][1] == 3.0
