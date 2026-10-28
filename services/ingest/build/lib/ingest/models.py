"""Daily snapshot of OpenRouter's model list, used to build price history.

No public price history exists, so each daily snapshot becomes one observation; dbt
turns the snapshots into a type-2 price dimension. Prices are kept as the API's strings
(USD per token) in the raw layer and cast in staging.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from .client import OpenRouterClient
from .payload import extract_rows, require

ENDPOINT = "/models"
TABLE = "openrouter_models_snapshot"
PARTITION_FIELD = "snapshot_date"


def normalize(body: Any, snapshot_date: date, ingested_at: datetime) -> list[dict[str, Any]]:
    rows = []
    for record in extract_rows(body):
        pricing = record.get("pricing") or {}
        rows.append(
            {
                "snapshot_date": snapshot_date.isoformat(),
                "model_id": str(require(record, "id")),
                "canonical_slug": record.get("canonical_slug"),
                "name": record.get("name"),
                "created_unix": record.get("created"),
                "context_length": record.get("context_length"),
                "prompt_price_usd_per_token": _as_str(pricing.get("prompt")),
                "completion_price_usd_per_token": _as_str(pricing.get("completion")),
                "payload": json.dumps(record, sort_keys=True),
                "ingested_at": ingested_at.isoformat(),
            }
        )
    return rows


def fetch(
    client: OpenRouterClient, snapshot_date: date, ingested_at: datetime
) -> list[dict[str, Any]]:
    return normalize(client.get(ENDPOINT), snapshot_date, ingested_at)


def _as_str(value: Any) -> str | None:
    return None if value is None else str(value)
