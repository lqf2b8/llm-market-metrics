"""Raw-layer table schemas: (name, BigQuery type, mode)."""

from __future__ import annotations

SCHEMAS: dict[str, list[tuple[str, str, str]]] = {
    "openrouter_rankings_daily": [
        ("date", "DATE", "REQUIRED"),
        ("model_permaslug", "STRING", "REQUIRED"),
        ("total_tokens", "STRING", "REQUIRED"),
        ("source_as_of", "STRING", "NULLABLE"),
        ("source_version", "STRING", "NULLABLE"),
        ("ingested_at", "TIMESTAMP", "REQUIRED"),
    ],
    "openrouter_models_snapshot": [
        ("snapshot_date", "DATE", "REQUIRED"),
        ("model_id", "STRING", "REQUIRED"),
        ("canonical_slug", "STRING", "NULLABLE"),
        ("name", "STRING", "NULLABLE"),
        ("created_unix", "INT64", "NULLABLE"),
        ("context_length", "INT64", "NULLABLE"),
        ("prompt_price_usd_per_token", "STRING", "NULLABLE"),
        ("completion_price_usd_per_token", "STRING", "NULLABLE"),
        ("payload", "STRING", "NULLABLE"),
        ("ingested_at", "TIMESTAMP", "REQUIRED"),
    ],
}
