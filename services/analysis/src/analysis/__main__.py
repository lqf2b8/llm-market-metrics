"""Freeze this week's forecasts (and backfill any origins not yet stored).

    python -m analysis

Runs after dbt has built the metrics views. Tokens use every complete week; implied spend
uses only weeks where spend is reliable (complete, >= 90% of top-50 tokens priced).
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime

from . import forecast
from .store import Store, from_env

log = logging.getLogger("analysis")

SERIES = {
    "tokens": "is_complete_week",
    "implied_spend_usd": "is_spend_reliable",
}


def freeze(store: Store, now: datetime) -> dict[str, int]:
    """Append forecasts for origins not already stored; never rewrite stored ones."""
    stored = store.stored_origins()
    written = {}
    for metric, flag in SERIES.items():
        weeks, values = store.series(metric, flag)
        rows = forecast.forecasts(metric, weeks, values)
        if not rows:
            run, _ = forecast.contiguous_tail(weeks, values)
            log.warning(
                "%s: no forecasts. Needs %d consecutive weeks of positive values; found %d "
                "consecutive of %d total. Check metrics.weekly_kpis.",
                metric,
                forecast.MIN_TRAIN,
                len(run),
                len(weeks),
            )
        latest_origin = weeks[-1] if weeks else None
        new = [
            {**r, "is_backfill": r["origin_week"] != latest_origin, "produced_at": now}
            for r in rows
            if (metric, r["origin_week"]) not in stored
        ]
        written[metric] = store.append(new)
        log.info(
            "%s: %d new forecast rows (latest origin %s)", metric, written[metric], latest_origin
        )
    return written


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    freeze(from_env(), datetime.now(UTC))
    return 0


if __name__ == "__main__":
    sys.exit(main())
