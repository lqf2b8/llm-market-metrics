"""Minimal OpenRouter HTTP client with retry on rate limits and server errors."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import requests

BASE_URL = "https://openrouter.ai/api/v1"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        session: requests.Session | None = None,
        base_url: str = BASE_URL,
        max_retries: int = 5,
        timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        self._api_key = api_key
        self._session = session or requests.Session()
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._timeout = timeout
        self._sleep = sleep

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}/{path.lstrip('/')}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        for attempt in range(self._max_retries + 1):
            resp = self._session.get(url, headers=headers, params=params, timeout=self._timeout)
            if resp.status_code in RETRY_STATUSES and attempt < self._max_retries:
                self._sleep(_retry_after(resp, attempt))
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError("unreachable")  # pragma: no cover


def _retry_after(resp: requests.Response, attempt: int) -> float:
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return max(float(header), 0.0)
        except ValueError:
            pass
    return float(min(2**attempt, 60))
