"""Where raw rows land. Both sinks are idempotent per partition: rerunning a date
replaces that date's rows instead of duplicating them."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Protocol

from .schemas import SCHEMAS


class Sink(Protocol):
    def write(self, table: str, rows: list[dict[str, Any]], partition_field: str) -> int: ...


class LocalSink:
    """JSON Lines files, one per partition value: <root>/<table>/<field>=<value>.jsonl."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, table: str, rows: list[dict[str, Any]], partition_field: str) -> int:
        by_partition: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_partition[str(row[partition_field])].append(row)
        table_dir = self.root / table
        table_dir.mkdir(parents=True, exist_ok=True)
        for value, part_rows in by_partition.items():
            path = table_dir / f"{partition_field}={value}.jsonl"
            tmp = path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                for row in part_rows:
                    fh.write(json.dumps(row, sort_keys=True) + "\n")
            tmp.replace(path)
        return len(rows)


def replace_partitions_sql(target: str, stage: str, partition_field: str) -> str:
    """One atomic script: drop the target's rows for every partition in the stage, then insert."""
    return (
        "BEGIN TRANSACTION;\n"
        f"DELETE FROM `{target}` WHERE {partition_field} IN "
        f"(SELECT DISTINCT {partition_field} FROM `{stage}`);\n"
        f"INSERT INTO `{target}` SELECT * FROM `{stage}`;\n"
        "COMMIT TRANSACTION;"
    )


def check_never_expires(table: Any) -> None:
    """The raw layer cannot be re-fetched (price snapshots), so refuse to write to a table
    that BigQuery will expire. Sandbox-mode datasets set a 60-day expiry by default."""
    partitioning = getattr(table, "time_partitioning", None)
    if getattr(table, "expires", None) or (partitioning and partitioning.expiration_ms):
        raise SystemExit(
            f"{table.table_id} is set to expire, so old rows would be silently dropped. "
            "Recreate the datasets with infra/gcp/reset.sh and infra/gcp/setup.sh."
        )


class BigQuerySink:
    """Loads rows into a stage table, then swaps the affected partitions in one transaction."""

    def __init__(
        self, project: str, dataset: str, location: str = "US", client: Any = None
    ) -> None:
        from google.cloud import bigquery  # imported lazily so local runs don't need it

        self._bq = bigquery
        self.client = client or bigquery.Client(project=project, location=location)
        self.project = project
        self.dataset = dataset
        self.location = location

    def _schema(self, table: str) -> list[Any]:
        return [self._bq.SchemaField(name, typ, mode=mode) for name, typ, mode in SCHEMAS[table]]

    def _ensure_table(self, table: str, partition_field: str) -> str:
        dataset_ref = self._bq.Dataset(f"{self.project}.{self.dataset}")
        dataset_ref.location = self.location
        self.client.create_dataset(dataset_ref, exists_ok=True)
        table_id = f"{self.project}.{self.dataset}.{table}"
        tbl = self._bq.Table(table_id, schema=self._schema(table))
        tbl.time_partitioning = self._bq.TimePartitioning(field=partition_field)
        tbl = self.client.create_table(tbl, exists_ok=True)
        check_never_expires(tbl)
        return table_id

    def write(self, table: str, rows: list[dict[str, Any]], partition_field: str) -> int:
        if not rows:
            return 0
        target = self._ensure_table(table, partition_field)
        stage = f"{self.project}.{self.dataset}._stage_{table}"
        job_config = self._bq.LoadJobConfig(
            schema=self._schema(table),
            write_disposition=self._bq.WriteDisposition.WRITE_TRUNCATE,
        )
        self.client.load_table_from_json(rows, stage, job_config=job_config).result()
        self.client.query(replace_partitions_sql(target, stage, partition_field)).result()
        self.client.delete_table(stage, not_found_ok=True)
        return len(rows)
