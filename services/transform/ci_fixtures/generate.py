"""Generate the small synthetic raw layer used in CI: 21 days (three full ISO weeks) of
50 models + the "other" row, and one model-list snapshot. Shapes match what the ingest
service writes; values are made up and only exercise the transformations.

    python ci_fixtures/generate.py
"""

import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent / "raw"
START = date(2026, 9, 28)  # a Monday
DAYS = 21
TS = "2026-10-19T06:00:00+00:00"

MODELS = [f"provider{i % 7}/model-{i}-20260901" for i in range(46)] + [
    "provider1/model-1-20260901:free",
    "stealth/fox-alpha",
    "openrouter/kite-beta",
    "vendorx/retired-model",
]


def main() -> None:
    rank_dir = ROOT / "openrouter_rankings_daily"
    snap_dir = ROOT / "openrouter_models_snapshot"
    rank_dir.mkdir(parents=True, exist_ok=True)
    snap_dir.mkdir(parents=True, exist_ok=True)
    for day in range(DAYS):
        d = (START + timedelta(days=day)).isoformat()
        with (rank_dir / f"date={d}.jsonl").open("w") as f:
            for i, m in enumerate(MODELS + ["other"]):
                # Volume grows over time and shifts toward higher-numbered models (mix).
                tokens = 10**9 * (i + 1) * (100 + day * (1 + i % 5)) // 100
                f.write(json.dumps({
                    "date": d, "model_permaslug": m, "total_tokens": str(tokens),
                    "source_as_of": TS, "source_version": "v1", "ingested_at": TS,
                }, sort_keys=True) + "\n")
    snap = (START + timedelta(days=DAYS - 1)).isoformat()
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
