"""Read weekly KPIs and append frozen forecasts, on DuckDB (local) or BigQuery (production).

Forecasts are append-only: once a (metric, origin_week) is stored it is never rewritten,
even if the underlying data is later revised. That is what makes "actual vs. forecast" a
fair comparison.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Protocol

TABLE = "forecast_frozen"
COLUMNS: list[tuple[str, str, str]] = [
    # name, DuckDB type, BigQuery type
    ("metric", "VARCHAR", "STRING"),
    ("origin_week", "DATE", "DATE"),
    ("target_week", "DATE", "DATE"),
    ("horizon_weeks", "INTEGER", "INT64"),
    ("model", "VARCHAR", "STRING"),
    ("point", "DOUBLE", "FLOAT64"),
    ("lower", "DOUBLE", "FLOAT64"),
    ("upper", "DOUBLE", "FLOAT64"),
    ("interval_level", "DOUBLE", "FLOAT64"),
    ("n_calibration", "INTEGER", "INT64"),
    ("is_backfill", "BOOLEAN", "BOOL"),
    ("produced_at", "TIMESTAMP", "TIMESTAMP"),
]
SERIES_SQL = """
    select week_start, {metric}
    from {metrics}.weekly_kpis
    where {flag}
    order by week_start
"""


class Store(Protocol):
    def series(self, metric: str, flag: str) -> tuple[list[date], list[float]]: ...
    def stored_origins(self) -> set[tuple[str, date]]: ...
    def append(self, rows: list[dict[str, Any]]) -> int: ...


class DuckDBStore:
    def __init__(self, path: str, metrics_schema: str = "metrics", schema: str = "analysis"):
        import duckdb

        self.con = duckdb.connect(path)
        self.metrics_schema = metrics_schema
        self.schema = schema
        cols = ", ".join(f"{name} {ddb}" for name, ddb, _ in COLUMNS)
        self.con.execute(f"create schema if not exists {schema}")
        self.con.execute(f"create table if not exists {schema}.{TABLE} ({cols})")

    def series(self, metric: str, flag: str) -> tuple[list[date], list[float]]:
        sql = SERIES_SQL.format(metric=metric, flag=flag, metrics=self.metrics_schema)
        rows = self.con.execute(sql).fetchall()
        return [r[0] for r in rows], [r[1] for r in rows]

    def stored_origins(self) -> set[tuple[str, date]]:
        rows = self.con.execute(f"select distinct metric, origin_week from {self.schema}.{TABLE}")
        return {(m, w) for m, w in rows.fetchall()}

    def append(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        names = [c[0] for c in COLUMNS]
        placeholders = ", ".join("?" for _ in names)
        self.con.executemany(
            f"insert into {self.schema}.{TABLE} ({', '.join(names)}) values ({placeholders})",
            [[r[n] for n in names] for r in rows],
        )
        return len(rows)


class BigQueryStore:
    def __init__(self, project: str, metrics_dataset: str, dataset: str, location: str):
        from google.cloud import bigquery

        self.bq = bigquery
        self.client = bigquery.Client(project=project, location=location)
        self.metrics = f"`{project}.{metrics_dataset}`"
        self.table_id = f"{project}.{dataset}.{TABLE}"
        ds = bigquery.Dataset(f"{project}.{dataset}")
        ds.location = location
        self.client.create_dataset(ds, exists_ok=True)
        schema = [bigquery.SchemaField(n, bq) for n, _, bq in COLUMNS]
        self.client.create_table(bigquery.Table(self.table_id, schema=schema), exists_ok=True)
        self.schema = schema

    def series(self, metric: str, flag: str) -> tuple[list[date], list[float]]:
        sql = SERIES_SQL.format(metric=metric, flag=flag, metrics=self.metrics)
        rows = list(self.client.query(sql).result())
        return [r[0] for r in rows], [r[1] for r in rows]

    def stored_origins(self) -> set[tuple[str, date]]:
        sql = f"select distinct metric, origin_week from `{self.table_id}`"
        return {(r[0], r[1]) for r in self.client.query(sql).result()}

    def append(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        payload = [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in r.items()}
            for r in rows
        ]
        config = self.bq.LoadJobConfig(
            schema=self.schema, write_disposition=self.bq.WriteDisposition.WRITE_APPEND
        )
        self.client.load_table_from_json(payload, self.table_id, job_config=config).result()
        return len(rows)


def from_env() -> Store:
    kind = os.environ.get("WAREHOUSE", "duckdb").lower()
    if kind == "duckdb":
        return DuckDBStore(os.environ.get("DUCKDB_PATH", "../../data/warehouse.duckdb"))
    if kind == "bigquery":
        project = os.environ.get("GCP_PROJECT")
        if not project:
            raise SystemExit("GCP_PROJECT is required when WAREHOUSE=bigquery")
        return BigQueryStore(
            project=project,
            metrics_dataset=os.environ.get("BQ_METRICS_DATASET", "metrics"),
            dataset=os.environ.get("BQ_ANALYSIS_DATASET", "analysis"),
            location=os.environ.get("BQ_LOCATION", "US"),
        )
    raise SystemExit(f"Unknown WAREHOUSE {kind!r}; use 'duckdb' or 'bigquery'")
