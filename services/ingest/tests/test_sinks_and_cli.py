from __future__ import annotations

import json

import ingest.__main__ as cli
from ingest.sinks import LocalSink, replace_partitions_sql


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_local_sink_rerun_replaces_partition_instead_of_duplicating(tmp_path):
    sink = LocalSink(tmp_path)
    first = [{"date": "2026-10-27", "v": 1}, {"date": "2026-10-27", "v": 2}]
    sink.write("t", first, "date")
    sink.write("t", [{"date": "2026-10-27", "v": 3}], "date")
    assert _read_jsonl(tmp_path / "t" / "date=2026-10-27.jsonl") == [{"date": "2026-10-27", "v": 3}]


def test_local_sink_leaves_other_partitions_alone(tmp_path):
    sink = LocalSink(tmp_path)
    sink.write("t", [{"date": "2026-10-26", "v": 1}], "date")
    sink.write("t", [{"date": "2026-10-27", "v": 2}], "date")
    assert sorted(p.name for p in (tmp_path / "t").iterdir()) == [
        "date=2026-10-26.jsonl",
        "date=2026-10-27.jsonl",
    ]


def test_bigquery_swap_is_one_transaction():
    sql = replace_partitions_sql("p.raw.t", "p.raw._stage_t", "date")
    assert sql.startswith("BEGIN TRANSACTION;")
    assert "DELETE FROM `p.raw.t` WHERE date IN (SELECT DISTINCT date FROM `p.raw._stage_t`)" in sql
    assert sql.rstrip().endswith("COMMIT TRANSACTION;")


def test_daily_command_writes_rankings_and_prices(tmp_path, monkeypatch, fake_client):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("SINK", "local")
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(cli, "OpenRouterClient", lambda _key: fake_client)
    assert cli.main(["daily"]) == 0
    assert any((tmp_path / "openrouter_rankings_daily").iterdir())
    snapshots = list((tmp_path / "openrouter_models_snapshot").iterdir())
    assert len(snapshots) == 1
    assert len(_read_jsonl(snapshots[0])) == 4
