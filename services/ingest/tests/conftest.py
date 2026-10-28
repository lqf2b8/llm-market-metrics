from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeClient:
    """Stands in for OpenRouterClient: returns canned bodies and records every call."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, params))
        return self.responses[path]


@pytest.fixture
def rankings_body() -> Any:
    return load_fixture("rankings_daily.json")


@pytest.fixture
def models_body() -> Any:
    return load_fixture("models.json")


@pytest.fixture
def fake_client(rankings_body: Any, models_body: Any) -> FakeClient:
    return FakeClient({"/datasets/rankings-daily": rankings_body, "/models": models_body})
