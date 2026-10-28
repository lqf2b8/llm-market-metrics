"""Read-only access to the metrics schema, on DuckDB (local) or BigQuery (production).

Queries are written once with `{metrics}` for the schema and `:name` for parameters; each
backend translates them. Results are cached briefly: the data changes once a day.
"""

from __future__ import annotations

import os
import re
import threading
import time
from datetime import date
from typing import Any, Protocol

PARAM = re.compile(r":([a-z_][a-z0-9_]*)")
CACHE_SECONDS = 300
BQ_TYPES: list[tuple[type, str]] = [
    (bool, "BOOL"),
    (int, "INT64"),
    (float, "FLOAT64"),
    (date, "DATE"),
]


class Warehouse(Protocol):
    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]: ...


class _Cached:
    def __init__(self) -> None:
        self._cache: dict[tuple, tuple[float, list[dict[str, Any]]]] = {}
        self._lock = threading.Lock()

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        key = (sql, tuple(sorted((params or {}).items())))
        now = time.monotonic()
        with self._lock:
            hit = self._cache.get(key)
            if hit and now - hit[0] < CACHE_SECONDS:
                return hit[1]
        rows = self._run(sql, params or {})
        with self._lock:
            self._cache[key] = (now, rows)
        return rows

    def _run(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError


class DuckDBWarehouse(_Cached):
    def __init__(self, path: str, schema: str = "metrics") -> None:
        super().__init__()
        self.path = path
        self.schema = schema

    def _run(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        import duckdb

        text = PARAM.sub(r"$\1", sql.format(metrics=self.schema))
        con = duckdb.connect(self.path, read_only=True)
        try:
            result = con.execute(text, params)
            columns = [d[0] for d in result.description]
            return [dict(zip(columns, row, strict=True)) for row in result.fetchall()]
        finally:
            con.close()


class BigQueryWarehouse(_Cached):
    def __init__(self, project: str, dataset: str = "metrics", location: str = "US") -> None:
        super().__init__()
        from google.cloud import bigquery

        self._bq = bigquery
        self.client = bigquery.Client(project=project, location=location)
        self.schema = f"`{project}.{dataset}`"

    def _param(self, name: str, value: Any) -> Any:
        # bool before int: bool is a subclass of int in Python.
        for python_type, bq_type in BQ_TYPES:
            if isinstance(value, python_type):
                return self._bq.ScalarQueryParameter(name, bq_type, value)
        return self._bq.ScalarQueryParameter(name, "STRING", value)

    def _run(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        text = PARAM.sub(r"@\1", sql.format(metrics=self.schema))
        config = self._bq.QueryJobConfig(
            query_parameters=[self._param(k, v) for k, v in params.items()]
        )
        return [dict(row.items()) for row in self.client.query(text, job_config=config).result()]


def from_env() -> Warehouse:
    kind = os.environ.get("WAREHOUSE", "duckdb").lower()
    if kind == "duckdb":
        return DuckDBWarehouse(os.environ.get("DUCKDB_PATH", "../../data/warehouse.duckdb"))
    if kind == "bigquery":
        project = os.environ.get("GCP_PROJECT")
        if not project:
            raise RuntimeError("GCP_PROJECT is required when WAREHOUSE=bigquery")
        return BigQueryWarehouse(
            project=project,
            dataset=os.environ.get("BQ_METRICS_DATASET", "metrics"),
            location=os.environ.get("BQ_LOCATION", "US"),
        )
    raise RuntimeError(f"Unknown WAREHOUSE {kind!r}; use 'duckdb' or 'bigquery'")
