"""Helpers for reading API payloads defensively: fail loudly on shapes we don't expect."""

from __future__ import annotations

from typing import Any


def extract_rows(body: Any) -> list[dict[str, Any]]:
    """Return the list of records from an API response body.

    Accepts a bare list or an object holding the list under a common key.
    """
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for key in ("data", "rows", "results"):
            value = body.get(key)
            if isinstance(value, list):
                return value
        raise ValueError(f"Unexpected response shape; top-level keys: {sorted(body)}")
    raise ValueError(f"Unexpected response type: {type(body).__name__}")


def require(record: dict[str, Any], field: str) -> Any:
    value = record.get(field)
    if value is None or value == "":
        raise ValueError(f"Record is missing required field {field!r}: {record}")
    return value
