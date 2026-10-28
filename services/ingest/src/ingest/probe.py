"""Day-1 checks: does the live data match what the plan assumes?

Pulls 7 days of rankings and today's model list, then reports:
  1. the response shape and the rows-per-day / "other"-row pattern,
  2. whether the model list carries prompt and completion prices,
  3. how cleanly ranking slugs join to the model list.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from .client import OpenRouterClient
from .models import ENDPOINT as MODELS_ENDPOINT
from .payload import extract_rows
from .rankings import ENDPOINT as RANKINGS_ENDPOINT

OTHER = "other"


def base_slug(slug: str) -> str:
    """Drop a variant suffix such as ':free'."""
    return slug.split(":", 1)[0]


def slug_match_report(ranking_slugs: set[str], models: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = {m.get("canonical_slug") for m in models if m.get("canonical_slug")}
    ids = {m.get("id") for m in models if m.get("id")}
    report: dict[str, list[str]] = {
        "canonical_slug": [],
        "model_id": [],
        "after_variant_strip": [],
        "unmatched": [],
    }
    for slug in sorted(ranking_slugs - {OTHER}):
        stripped = base_slug(slug)
        if slug in canonical:
            report["canonical_slug"].append(slug)
        elif slug in ids:
            report["model_id"].append(slug)
        elif stripped in canonical or stripped in ids:
            report["after_variant_strip"].append(slug)
        else:
            report["unmatched"].append(slug)
    return {"counts": {k: len(v) for k, v in report.items()}, "unmatched": report["unmatched"]}


def rows_per_day(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_day = Counter(r["date"] for r in rows)
    days_with_other = {r["date"] for r in rows if r["model_permaslug"] == OTHER}
    return {
        "days": len(per_day),
        "min_rows": min(per_day.values(), default=0),
        "max_rows": max(per_day.values(), default=0),
        "days_missing_other": sorted(set(per_day) - days_with_other),
    }


def run(client: OpenRouterClient, today: date) -> dict[str, Any]:
    end = today - timedelta(days=1)
    start = end - timedelta(days=6)
    rankings_body = client.get(
        RANKINGS_ENDPOINT,
        params={"start_date": start.isoformat(), "end_date": end.isoformat(), "period": "day"},
    )
    ranking_rows = extract_rows(rankings_body)
    models_body = client.get(MODELS_ENDPOINT)
    models = extract_rows(models_body)
    priced = [
        m
        for m in models
        if (m.get("pricing") or {}).get("prompt") is not None
        and (m.get("pricing") or {}).get("completion") is not None
    ]
    return {
        "rankings": {
            "top_level_keys": sorted(rankings_body) if isinstance(rankings_body, dict) else "list",
            "meta": rankings_body.get("meta") if isinstance(rankings_body, dict) else None,
            "sample_row": ranking_rows[0] if ranking_rows else None,
            "shape": rows_per_day(ranking_rows),
        },
        "models": {
            "count": len(models),
            "with_prompt_and_completion_price": len(priced),
            "sample_fields": sorted(models[0]) if models else [],
        },
        "slug_join": slug_match_report({r["model_permaslug"] for r in ranking_rows}, models),
    }
