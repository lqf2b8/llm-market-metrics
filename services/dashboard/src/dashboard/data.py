"""Load the dashboard's six dataframes from the `metrics` views, on DuckDB or BigQuery.

The SQL is plain enough to run unchanged on both: `metrics.<view>` resolves to the metrics
schema in DuckDB and to the metrics dataset of the default project in BigQuery.
"""

from __future__ import annotations

import os

import pandas as pd

LATEST = "(select max(week_start) from metrics.weekly_kpis where is_complete_week)"
QUERIES = {
    "as_of": """
        select
            max(data_through_date) as data_through_date,
            max(case when is_complete_week then week_start end) as latest_week
        from metrics.weekly_kpis
    """,
    "kpis": """
        select week_start, is_spend_reliable, tokens, implied_spend_usd,
            effective_paid_usd_per_mtok, tokens_wow_change, implied_spend_wow_change,
            effective_paid_price_wow_change
        from metrics.weekly_kpis
        where is_complete_week
        order by week_start
    """,
    "bridge": f"select * from metrics.spend_bridge_weekly where week_start = {LATEST}",
    "bridge_providers": f"""
        select provider, spend_change_usd, volume_effect_usd, mix_effect_usd, price_effect_usd
        from metrics.spend_bridge_provider_weekly
        where week_start = {LATEST}
        order by abs(spend_change_usd) desc
    """,
    "forecasts": """
        select metric, origin_week, target_week, model, point, lower_bound, upper_bound,
            interval_level, actual, is_covered, is_backfill
        from metrics.forecast_vs_actual
        where horizon_weeks = 1
        order by metric, target_week
    """,
    "providers": """
        select week_start, provider, implied_spend_usd, token_share, paid_token_share,
            spend_share
        from metrics.provider_weekly
        where is_complete_week
        order by week_start, provider
    """,
}


def load_duckdb(path: str) -> dict[str, pd.DataFrame]:
    import duckdb

    con = duckdb.connect(path, read_only=True)
    try:
        return {name: con.execute(sql).df() for name, sql in QUERIES.items()}
    finally:
        con.close()


def load_bigquery(project: str, location: str = "US") -> dict[str, pd.DataFrame]:
    from google.cloud import bigquery

    client = bigquery.Client(project=project, location=location)
    frames = {}
    for name, sql in QUERIES.items():
        rows = [dict(r.items()) for r in client.query(sql).result()]
        frames[name] = pd.DataFrame(rows)
    return frames


def load() -> dict[str, pd.DataFrame]:
    kind = os.environ.get("WAREHOUSE", "duckdb").lower()
    if kind == "duckdb":
        return load_duckdb(os.environ.get("DUCKDB_PATH", "../../data/warehouse.duckdb"))
    if kind == "bigquery":
        project = os.environ.get("GCP_PROJECT")
        if not project:
            raise RuntimeError("GCP_PROJECT is required when WAREHOUSE=bigquery")
        return load_bigquery(project, os.environ.get("BQ_LOCATION", "US"))
    raise RuntimeError(f"Unknown WAREHOUSE {kind!r}; use 'duckdb' or 'bigquery'")


_cache: dict[str, tuple[float, dict[str, pd.DataFrame]]] = {}
CACHE_SECONDS = 600


def load_cached(now: float | None = None) -> dict[str, pd.DataFrame]:
    """load(), reused for 10 minutes: the warehouse changes once a day."""
    import time

    now = time.monotonic() if now is None else now
    hit = _cache.get("frames")
    if hit and now - hit[0] < CACHE_SECONDS:
        return hit[1]
    frames = load()
    _cache["frames"] = (now, frames)
    return frames
