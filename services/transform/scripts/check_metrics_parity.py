"""Fail if the metrics.weekly_kpis view disagrees with MetricFlow's own query output.

The view is what consumers read; the semantic layer is where metrics are defined. This
check keeps the two from drifting apart. Runs on the DuckDB target (local and CI):

    python scripts/check_metrics_parity.py --duckdb-path ci.duckdb
"""

from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

METRICS = [
    "tokens",
    "paid_tokens",
    "implied_spend_usd",
    "priced_coverage",
    "effective_paid_usd_per_mtok",
    "zero_priced_share",
    "new_model_share",
]
REL_TOL = 1e-9
ABS_TOL = 1e-6


def query_metricflow(out_path: Path) -> dict[str, dict[str, float | None]]:
    subprocess.run(
        [
            "mf",
            "query",
            "--metrics",
            ",".join(METRICS),
            "--group-by",
            "metric_time__week",
            "--csv",
            str(out_path),
        ],
        check=True,
        capture_output=True,
    )
    rows: dict[str, dict[str, float | None]] = {}
    with out_path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            week = row["metric_time__week"][:10]
            rows[week] = {
                m: (float(row[m]) if row[m] not in ("", None) else None)
                for m in METRICS
            }
    return rows


def query_view(duckdb_path: str) -> dict[str, dict[str, float | None]]:
    con = duckdb.connect(duckdb_path, read_only=True)
    cols = ", ".join(METRICS)
    result = con.sql(
        f"select cast(week_start as varchar), {cols} from metrics.weekly_kpis"
    )
    return {
        week: {
            m: (float(v) if v is not None else None)
            for m, v in zip(METRICS, values, strict=True)
        }
        for week, *values in result.fetchall()
    }


def same(a: float | None, b: float | None) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duckdb-path", required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        mf_rows = query_metricflow(Path(tmp) / "mf.csv")
    view_rows = query_view(args.duckdb_path)

    problems = []
    if set(mf_rows) != set(view_rows):
        problems.append(
            f"week sets differ: only in MetricFlow {sorted(set(mf_rows) - set(view_rows))}, "
            f"only in view {sorted(set(view_rows) - set(mf_rows))}"
        )
    for week in sorted(set(mf_rows) & set(view_rows)):
        for metric in METRICS:
            if not same(mf_rows[week][metric], view_rows[week][metric]):
                problems.append(
                    f"{week} {metric}: MetricFlow {mf_rows[week][metric]} "
                    f"vs view {view_rows[week][metric]}"
                )

    if problems:
        print(f"{len(problems)} parity problems:")
        for p in problems[:50]:
            print("  " + p)
        return 1
    print(
        f"metrics.weekly_kpis matches MetricFlow: {len(view_rows)} weeks x {len(METRICS)} metrics"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
