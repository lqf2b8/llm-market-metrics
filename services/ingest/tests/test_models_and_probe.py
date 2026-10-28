from __future__ import annotations

import json
from datetime import UTC, date, datetime

from ingest import models, probe, rankings

NOW = datetime(2026, 10, 28, 6, 0, tzinfo=UTC)


def test_models_normalize_extracts_prices_as_strings(models_body):
    rows = models.normalize(models_body, date(2026, 10, 28), NOW)
    sonnet = next(r for r in rows if r["model_id"] == "anthropic/claude-sonnet-4.5")
    assert sonnet["prompt_price_usd_per_token"] == "0.000003"
    assert sonnet["completion_price_usd_per_token"] == "0.000015"
    assert sonnet["snapshot_date"] == "2026-10-28"
    assert json.loads(sonnet["payload"])["context_length"] == 1000000


def test_models_normalize_tolerates_missing_pricing(models_body):
    rows = models.normalize(models_body, date(2026, 10, 28), NOW)
    unpriced = next(r for r in rows if r["model_id"] == "example/no-pricing")
    assert unpriced["prompt_price_usd_per_token"] is None
    assert unpriced["canonical_slug"] is None


def test_slug_match_report_classifies_each_ranking_slug(rankings_body, models_body):
    slugs = {r["model_permaslug"] for r in rankings.normalize(rankings_body, NOW)}
    report = probe.slug_match_report(slugs, models_body["data"])
    assert report["counts"] == {
        "canonical_slug": 2,  # sonnet, gpt-4o dated slug
        "model_id": 0,
        "after_variant_strip": 1,  # deepseek ...:free
        "unmatched": 1,
    }
    assert report["unmatched"] == ["mystery/unlisted-model"]


def test_rows_per_day_flags_days_without_other_row():
    rows = [
        {"date": "2026-10-26", "model_permaslug": "a/b"},
        {"date": "2026-10-26", "model_permaslug": "other"},
        {"date": "2026-10-27", "model_permaslug": "a/b"},
    ]
    shape = probe.rows_per_day(rows)
    assert shape == {"days": 2, "min_rows": 1, "max_rows": 2, "days_missing_other": ["2026-10-27"]}


def test_probe_run_reports_all_three_checks(fake_client):
    report = probe.run(fake_client, date(2026, 10, 28))
    assert report["rankings"]["shape"]["days"] == 2
    assert report["models"]["with_prompt_and_completion_price"] == 3
    assert report["slug_join"]["counts"]["unmatched"] == 1
    _, params = fake_client.calls[0]
    assert params == {"start_date": "2026-10-21", "end_date": "2026-10-27", "period": "day"}
