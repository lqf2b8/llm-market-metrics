"""Command line entry point.

    python -m ingest probe                         # day-1 checks, prints a JSON report
    python -m ingest rankings                      # last 3 complete days (re-pulls late data)
    python -m ingest rankings --backfill           # everything since 2025-01-01
    python -m ingest rankings --start 2026-10-01 --end 2026-10-27
    python -m ingest prices                        # today's model price snapshot
    python -m ingest daily                         # rankings + prices, what the scheduler runs

Configuration comes from environment variables (see .env.example).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, date, datetime, timedelta

from . import models, probe, rankings
from .client import OpenRouterClient
from .sinks import BigQuerySink, LocalSink, Sink

log = logging.getLogger("ingest")


def make_sink() -> Sink:
    kind = os.environ.get("SINK", "local").lower()
    if kind == "local":
        return LocalSink(os.environ.get("LOCAL_DATA_DIR", "data/raw"))
    if kind == "bigquery":
        return BigQuerySink(
            project=_required_env("GCP_PROJECT"),
            dataset=os.environ.get("BQ_RAW_DATASET", "raw"),
            location=os.environ.get("BQ_LOCATION", "US"),
        )
    raise SystemExit(f"Unknown SINK {kind!r}; use 'local' or 'bigquery'")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Environment variable {name} is required")
    return value


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def run_rankings(
    client: OpenRouterClient, sink: Sink, start: date, end: date, now: datetime
) -> int:
    rows = rankings.fetch(client, start, end, ingested_at=now)
    written = sink.write(rankings.TABLE, rows, rankings.PARTITION_FIELD)
    log.info("rankings: %s rows for %s to %s", written, start, end)
    return written


def run_prices(client: OpenRouterClient, sink: Sink, today: date, now: datetime) -> int:
    rows = models.fetch(client, snapshot_date=today, ingested_at=now)
    written = sink.write(models.TABLE, rows, models.PARTITION_FIELD)
    log.info("prices: %s models snapshotted for %s", written, today)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="day-1 checks against the live API")
    rank = sub.add_parser("rankings", help="load daily token rankings")
    rank.add_argument("--start", type=_parse_date)
    rank.add_argument("--end", type=_parse_date)
    rank.add_argument("--backfill", action="store_true", help="start from 2025-01-01")
    sub.add_parser("prices", help="snapshot today's model prices")
    sub.add_parser("daily", help="rankings for the last 3 days + today's prices")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    now = datetime.now(UTC)
    today = now.date()
    yesterday = today - timedelta(days=1)
    client = OpenRouterClient(_required_env("OPENROUTER_API_KEY"))

    if args.command == "probe":
        print(json.dumps(probe.run(client, today), indent=2, default=str))
        return 0

    sink = make_sink()
    if args.command == "rankings":
        end = args.end or yesterday
        start = rankings.DATASET_START if args.backfill else (args.start or end - timedelta(days=2))
        run_rankings(client, sink, start, end, now)
    elif args.command == "prices":
        run_prices(client, sink, today, now)
    elif args.command == "daily":
        run_rankings(client, sink, yesterday - timedelta(days=2), yesterday, now)
        run_prices(client, sink, today, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
