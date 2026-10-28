from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ingest import rankings

NOW = datetime(2026, 10, 28, 6, 0, tzinfo=UTC)


def test_date_chunks_cover_range_without_gaps_or_overlap():
    chunks = list(rankings.date_chunks(date(2025, 1, 1), date(2025, 3, 5), days=31))
    assert chunks[0] == (date(2025, 1, 1), date(2025, 1, 31))
    assert chunks[-1][1] == date(2025, 3, 5)
    for (_, prev_end), (next_start, _) in zip(chunks, chunks[1:], strict=False):
        assert (next_start - prev_end).days == 1


def test_date_chunks_single_day():
    assert list(rankings.date_chunks(date(2026, 10, 1), date(2026, 10, 1))) == [
        (date(2026, 10, 1), date(2026, 10, 1))
    ]


def test_date_chunks_reject_reversed_range():
    with pytest.raises(ValueError):
        list(rankings.date_chunks(date(2026, 10, 2), date(2026, 10, 1)))


def test_normalize_keeps_tokens_as_strings_and_carries_meta(rankings_body):
    rows = rankings.normalize(rankings_body, NOW)
    assert len(rows) == 8
    first = rows[0]
    assert first["total_tokens"] == "812345678901"
    assert first["source_as_of"] == "2026-10-28T00:15:00Z"
    assert first["source_version"] == "v1"
    assert first["ingested_at"] == NOW.isoformat()


def test_normalize_rejects_missing_fields():
    body = {"data": [{"date": "2026-10-27", "total_tokens": "1"}]}
    with pytest.raises(ValueError, match="model_permaslug"):
        rankings.normalize(body, NOW)


def test_normalize_rejects_non_numeric_tokens():
    body = {"data": [{"date": "2026-10-27", "model_permaslug": "a/b", "total_tokens": "12x"}]}
    with pytest.raises(ValueError, match="total_tokens"):
        rankings.normalize(body, NOW)


def test_normalize_rejects_unexpected_shape():
    with pytest.raises(ValueError, match="Unexpected response shape"):
        rankings.normalize({"items": []}, NOW)


def test_fetch_clamps_to_dataset_start_and_chunks_requests(fake_client):
    rankings.fetch(fake_client, date(2024, 6, 1), date(2025, 2, 15), NOW, chunk_days=31)
    params = [p for _, p in fake_client.calls]
    assert params[0]["start_date"] == "2025-01-01"
    assert params[-1]["end_date"] == "2025-02-15"
    assert all(p["period"] == "day" for p in params)
    assert len(params) == 2
