"""Daily token totals per model from OpenRouter's rankings dataset.

Source: GET /datasets/rankings-daily. One row per (date, model_permaslug): the top 50
models plus one aggregate row with model_permaslug = "other". Data starts 2025-01-01.
Licensed CC BY 4.0: "Source: OpenRouter (openrouter.ai/rankings), as of {as_of}."
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from typing import Any

from .client import OpenRouterClient
from .payload import extract_rows, require

DATASET_START = date(2025, 1, 1)
ENDPOINT = "/datasets/rankings-daily"
TABLE = "openrouter_rankings_daily"
PARTITION_FIELD = "date"


def date_chunks(start: date, end: date, days: int = 31) -> Iterator[tuple[date, date]]:
    """Split an inclusive date range into consecutive inclusive chunks."""
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=days - 1), end)
        yield cursor, chunk_end
        cursor = chunk_end + timedelta(days=1)


def normalize(body: Any, ingested_at: datetime) -> list[dict[str, Any]]:
    meta = body.get("meta", {}) if isinstance(body, dict) else {}
    rows = []
    for record in extract_rows(body):
        tokens = str(require(record, "total_tokens"))
        if not tokens.replace(".", "", 1).isdigit():
            raise ValueError(f"total_tokens is not a non-negative number: {record}")
        rows.append(
            {
                "date": str(require(record, "date")),
                "model_permaslug": str(require(record, "model_permaslug")),
                "total_tokens": tokens,
                "source_as_of": meta.get("as_of"),
                "source_version": meta.get("version"),
                "ingested_at": ingested_at.isoformat(),
            }
        )
    return rows


def fetch(
    client: OpenRouterClient,
    start: date,
    end: date,
    ingested_at: datetime,
    chunk_days: int = 31,
) -> list[dict[str, Any]]:
    start = max(start, DATASET_START)
    rows: list[dict[str, Any]] = []
    for chunk_start, chunk_end in date_chunks(start, end, chunk_days):
        body = client.get(
            ENDPOINT,
            params={
                "start_date": chunk_start.isoformat(),
                "end_date": chunk_end.isoformat(),
                "period": "day",
            },
        )
        rows.extend(normalize(body, ingested_at))
    return rows
