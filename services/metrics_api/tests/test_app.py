from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from fastapi.testclient import TestClient

from metrics_api import app as app_module
from metrics_api.warehouse import PARAM

WEEK = date(2026, 10, 19)


def kpi_row(week: date = WEEK, **overrides: Any) -> dict[str, Any]:
    row = {
        "week_start": week,
        "data_through_date": date(2026, 10, 25),
        "is_complete_week": True,
        "is_spend_reliable": True,
        "tokens": 188_000_000_000_000,
        "paid_tokens": 150_000_000_000_000,
        "implied_spend_usd": 176_900_000.0,
        "priced_coverage": 0.9997,
        "effective_paid_usd_per_mtok": 1.157,
        "zero_priced_share": 0.133,
        "new_model_share": 0.716,
        "outside_top50_share": 0.06,
        "models_entering_top50": 6,
        "tokens_wow_change": 0.146,
        "paid_tokens_wow_change": 0.05,
        "implied_spend_wow_change": 0.112,
        "effective_paid_price_wow_change": 0.04,
    }
    row.update(overrides)
    return row


class FakeWarehouse:
    """Answers by matching the query text; records every call."""

    def __init__(self, routes: dict[str, list[dict[str, Any]]]) -> None:
        self.routes = routes
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.calls.append((sql, params))
        for needle, rows in self.routes.items():
            if needle in sql:
                if params and "week" in params and rows and "week_start" in rows[0]:
                    return [r for r in rows if r["week_start"] == params["week"]]
                return rows
        raise AssertionError(f"unexpected query: {sql}")


@pytest.fixture
def make_client():
    def _make(routes: dict[str, list[dict[str, Any]]]) -> tuple[TestClient, FakeWarehouse]:
        fake = FakeWarehouse(routes)
        app_module.app.dependency_overrides[app_module.get_warehouse] = lambda: fake
        return TestClient(app_module.app), fake

    yield _make
    app_module.app.dependency_overrides.clear()


def test_kpis_default_to_latest_complete_week(make_client):
    client, fake = make_client(
        {"max(week_start) as week": [{"week": WEEK}], "weekly_kpis where": [kpi_row()]}
    )
    resp = client.get("/kpis")
    assert resp.status_code == 200
    assert resp.json()["week_start"] == "2026-10-19"
    assert fake.calls[-1][1] == {"week": WEEK}


def test_kpis_reject_a_week_that_is_not_a_monday(make_client):
    client, _ = make_client({})
    resp = client.get("/kpis", params={"week": "2026-10-21"})
    assert resp.status_code == 422
    assert "not a Monday" in resp.json()["detail"]


def test_kpis_404_for_a_week_without_data(make_client):
    client, _ = make_client({"weekly_kpis where": [kpi_row()]})
    assert client.get("/kpis", params={"week": "2024-01-01"}).status_code == 404


def test_no_complete_week_returns_503(make_client):
    client, _ = make_client({"max(week_start) as week": [{"week": None}]})
    assert client.get("/kpis").status_code == 503


def test_history_passes_filters_as_parameters(make_client):
    client, fake = make_client({"order by week_start": [kpi_row(), kpi_row(date(2026, 10, 12))]})
    resp = client.get("/kpis/history", params={"start": "2026-10-01", "complete_only": "false"})
    assert resp.status_code == 200 and len(resp.json()) == 2
    _, params = fake.calls[-1]
    assert params["start"] == date(2026, 10, 1)
    assert params["complete_only"] is False


def test_bridge_combines_totals_and_providers(make_client):
    totals = {
        "week_start": WEEK,
        "prior_week_start": date(2026, 10, 12),
        "is_complete_pair": True,
        "is_reliable_pair": True,
        "prior_spend_usd": 159.1e6,
        "spend_usd": 176.9e6,
        "spend_change_usd": 17.8e6,
        "volume_effect_usd": 24.9e6,
        "mix_effect_usd": -7.1e6,
        "price_effect_usd": 0.0,
        "prior_priced_tokens": 1,
        "priced_tokens": 2,
        "models_entering": 6,
        "models_exiting": 9,
    }
    provider = {
        "provider": "anthropic",
        "prior_spend_usd": 70e6,
        "spend_usd": 86.6e6,
        "spend_change_usd": 16.6e6,
        "volume_effect_usd": 11.1e6,
        "mix_effect_usd": 5.5e6,
        "price_effect_usd": 0.0,
    }
    client, _ = make_client(
        {"spend_bridge_weekly": [totals], "spend_bridge_provider_weekly": [provider]}
    )
    body = client.get("/bridge", params={"week": "2026-10-19"}).json()
    assert body["spend_change_usd"] == pytest.approx(
        body["volume_effect_usd"] + body["mix_effect_usd"] + body["price_effect_usd"]
    )
    assert body["providers"][0]["provider"] == "anthropic"
    assert "prior_priced_tokens" not in body


def test_as_of_and_health(make_client):
    client, _ = make_client(
        {
            "latest_complete_week": [
                {
                    "data_through_date": date(2026, 10, 27),
                    "latest_complete_week": WEEK,
                    "latest_reliable_week": WEEK,
                }
            ]
        }
    )
    assert client.get("/health").json() == {"status": "ok"}
    body = client.get("/as-of").json()
    assert body["latest_complete_week"] == "2026-10-19"
    assert "OpenRouter" in body["source"]


def test_parameter_markers_translate_for_each_backend():
    sql = "select * from {metrics}.t where week_start = :week and x >= :start_date"
    assert (
        PARAM.sub(r"$\1", sql)
        == "select * from {metrics}.t where week_start = $week and x >= $start_date"
    )
    assert PARAM.sub(r"@\1", sql).endswith("@week and x >= @start_date")


def test_forecast_returns_latest_points_and_accuracy(make_client):
    point = {
        "metric": "tokens",
        "origin_week": WEEK,
        "target_week": date(2026, 10, 26),
        "horizon_weeks": 1,
        "model": "drift",
        "point": 2.0e14,
        "lower_bound": 1.7e14,
        "upper_bound": 2.3e14,
        "interval_level": 0.9,
        "actual": None,
    }
    acc = {
        "metric": "tokens",
        "horizon_weeks": 1,
        "n_evaluated": 82,
        "n_with_interval": 73,
        "coverage": 0.93,
        "mean_abs_pct_error": 0.096,
        "mean_pct_error": 0.024,
        "n_live_evaluated": 0,
        "live_coverage": None,
        "live_mean_abs_pct_error": None,
        "first_origin_week": date(2025, 3, 24),
        "last_target_week": WEEK,
    }
    client, _ = make_client({"forecast_latest": [point], "forecast_accuracy": [acc]})
    body = client.get("/forecast").json()
    assert body["forecasts"][0]["lower_bound"] == 1.7e14
    assert body["accuracy"][0]["coverage"] == 0.93


def test_forecast_503_before_the_analysis_service_has_run(make_client):
    client, _ = make_client({"forecast_latest": [], "forecast_accuracy": []})
    assert client.get("/forecast").status_code == 503
