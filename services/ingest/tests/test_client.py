from __future__ import annotations

import pytest
import requests

from ingest.client import OpenRouterClient


class FakeResponse:
    def __init__(self, status: int, body: object = None, headers: dict[str, str] | None = None):
        self.status_code = status
        self._body = body
        self.headers = headers or {}

    def json(self) -> object:
        return self._body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self.responses = responses
        self.requests: list[dict] = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.requests.append({"url": url, "headers": headers, "params": params})
        return self.responses.pop(0)


def test_retries_on_rate_limit_then_succeeds():
    session = FakeSession(
        [FakeResponse(429, headers={"Retry-After": "3"}), FakeResponse(200, {"ok": 1})]
    )
    slept: list[float] = []
    client = OpenRouterClient("key", session=session, sleep=slept.append)
    assert client.get("/models") == {"ok": 1}
    assert slept == [3.0]
    assert session.requests[0]["url"] == "https://openrouter.ai/api/v1/models"
    assert session.requests[0]["headers"]["Authorization"] == "Bearer key"


def test_gives_up_after_max_retries():
    session = FakeSession([FakeResponse(503) for _ in range(3)])
    client = OpenRouterClient("key", session=session, max_retries=2, sleep=lambda _: None)
    with pytest.raises(requests.HTTPError):
        client.get("/models")
    assert len(session.requests) == 3


def test_does_not_retry_auth_errors():
    session = FakeSession([FakeResponse(401)])
    client = OpenRouterClient("key", session=session, sleep=lambda _: None)
    with pytest.raises(requests.HTTPError):
        client.get("/models")
    assert len(session.requests) == 1


def test_backoff_without_retry_after_header_is_exponential():
    session = FakeSession([FakeResponse(500), FakeResponse(500), FakeResponse(200, [])])
    slept: list[float] = []
    OpenRouterClient("key", session=session, sleep=slept.append).get("/models")
    assert slept == [1.0, 2.0]


def test_missing_key_is_rejected():
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        OpenRouterClient("")
