"""Generate the small synthetic raw layer used in CI: 21 days (three full ISO weeks) of
50 models + the "other" row, and one model-list snapshot. Shapes match what the ingest
service writes; values are made up and only exercise the transformations.

    python ci_fixtures/generate.py                       # the committed fixtures
    python ci_fixtures/generate.py --days 182 --out DIR  # 26 weeks, enough to forecast from

Longer runs end on the same day, so the last three weeks match the committed fixtures'
dates (volumes differ: growth is measured from the first day).
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent / "raw"
END = date(2026, 10, 19)  # a Monday: the day after the last fixture day
DAYS = 21
TS = "2026-10-19T06:00:00+00:00"

MODELS = [f"provider{i % 7}/model-{i}-20260901" for i in range(46)] + [
    "provider1/model-1-20260901:free",
    "stealth/fox-alpha",
    "openrouter/kite-beta",
    "vendorx/retired-model",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=DAYS, help="a multiple of 7")
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    if args.days % 7:
        parser.error("--days must be a multiple of 7 so weeks stay whole")
    write(args.out, args.days)


def write(root: Path, days: int) -> None:
    start = END - timedelta(days=days)
    rank_dir = root / "openrouter_rankings_daily"
    snap_dir = root / "openrouter_models_snapshot"
    rank_dir.mkdir(parents=True, exist_ok=True)
    snap_dir.mkdir(parents=True, exist_ok=True)
    for day in range(days):
        d = (start + timedelta(days=day)).isoformat()
        with (rank_dir / f"date={d}.jsonl").open("w") as f:
            for i, m in enumerate(MODELS + ["other"]):
                # Volume grows over time and shifts toward higher-numbered models (mix).
                tokens = 10**9 * (i + 1) * (100 + day * (1 + i % 5)) // 100
                f.write(json.dumps({
                    "date": d, "model_permaslug": m, "total_tokens": str(tokens),
                    "source_as_of": TS, "source_version": "v1", "ingested_at": TS,
                }, sort_keys=True) + "\n")
    snap = (start + timedelta(days=days - 1)).isoformat()
    with (snap_dir / f"snapshot_date={snap}.jsonl").open("w") as f:
        rows = [
            (f"provider{i % 7}/model-{i}", f"provider{i % 7}/model-{i}-20260901",
             f"{(i + 1) / 1e7:.7f}", f"{(i + 1) * 4 / 1e7:.7f}")
            for i in range(46)
        ] + [
            ("provider1/model-1:free", "provider1/model-1-20260901", "0", "0"),
            ("openrouter/auto", None, "-1", "-1"),
        ]
        for model_id, canonical, prompt, completion in rows:
            f.write(json.dumps({
                "snapshot_date": snap, "model_id": model_id, "canonical_slug": canonical,
                "name": model_id, "created_unix": 1788000000, "context_length": 128000,
                "prompt_price_usd_per_token": prompt, "completion_price_usd_per_token": completion,
                "payload": "{}", "ingested_at": TS,
            }, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
