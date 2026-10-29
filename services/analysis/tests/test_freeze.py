from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import duckdb
import numpy as np

from analysis.__main__ import freeze
from analysis.store import TABLE, DuckDBStore

START = date(2025, 1, 6)


def make_warehouse(path, n_weeks: int, seed: int = 3) -> None:
    rng = np.random.default_rng(seed)
    tokens = 1e12 * np.exp(np.cumsum(0.05 + 0.08 * rng.standard_normal(n_weeks)))
    con = duckdb.connect(str(path))
    con.execute("create schema metrics")
    con.execute(
        "create table metrics.weekly_kpis (week_start date, is_complete_week boolean, "
        "is_spend_reliable boolean, tokens bigint, implied_spend_usd double)"
    )
    for i, t in enumerate(tokens):
        con.execute(
            "insert into metrics.weekly_kpis values (?, true, ?, ?, ?)",
            [START + timedelta(days=7 * i), i >= 5, int(t), float(t) * 1e-6],
        )
    con.close()


def stored(path):
    con = duckdb.connect(str(path), read_only=True)
    rows = con.execute(
        f"select metric, origin_week, horizon_weeks, point, is_backfill from analysis.{TABLE}"
    ).fetchall()
    con.close()
    return rows


def test_first_run_backfills_and_marks_only_the_latest_origin_live(tmp_path):
    db = tmp_path / "w.duckdb"
    make_warehouse(db, 30)
    written = freeze(DuckDBStore(str(db)), datetime(2026, 1, 1, tzinfo=UTC))
    assert written["tokens"] > 0 and written["implied_spend_usd"] > 0
    rows = stored(db)
    latest = max(r[1] for r in rows if r[0] == "tokens")
    assert all(r[4] is True for r in rows if r[1] != latest)
    assert all(r[4] is False for r in rows if r[1] == latest)
    assert {r[0] for r in rows if r[1] == latest} == {"tokens", "implied_spend_usd"}


def test_stored_forecasts_are_never_rewritten(tmp_path):
    db = tmp_path / "w.duckdb"
    make_warehouse(db, 30)
    freeze(DuckDBStore(str(db)), datetime(2026, 1, 1, tzinfo=UTC))
    before = {(r[0], r[1], r[2]): r[3] for r in stored(db)}

    # Data for past weeks is revised and a new week arrives; old forecasts must not move.
    con = duckdb.connect(str(db))
    con.execute("update metrics.weekly_kpis set tokens = tokens * 2")
    last = con.execute("select max(week_start) from metrics.weekly_kpis").fetchone()[0]
    con.execute(
        "insert into metrics.weekly_kpis values (?, true, true, 9e15, 9e9)",
        [last + timedelta(days=7)],
    )
    con.close()

    written = freeze(DuckDBStore(str(db)), datetime(2026, 1, 8, tzinfo=UTC))
    assert written == {"tokens": 4, "implied_spend_usd": 4}  # one new origin x 4 horizons
    after = {(r[0], r[1], r[2]): r[3] for r in stored(db)}
    assert all(after[k] == v for k, v in before.items())


def test_rerun_without_new_data_writes_nothing(tmp_path):
    db = tmp_path / "w.duckdb"
    make_warehouse(db, 30)
    freeze(DuckDBStore(str(db)), datetime(2026, 1, 1, tzinfo=UTC))
    assert freeze(DuckDBStore(str(db)), datetime(2026, 1, 1, tzinfo=UTC)) == {
        "tokens": 0,
        "implied_spend_usd": 0,
    }
