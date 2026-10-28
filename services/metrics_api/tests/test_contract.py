"""Contract tests against a real dbt-built warehouse.

Skipped unless METRICS_DUCKDB_PATH points at a DuckDB file built by the transform service
(CI builds one from fixtures; locally use data/warehouse.duckdb). They prove every query
the API sends runs against the actual metrics views and that the numbers hang together.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from metrics_api import app as app_module
from metrics_api.warehouse import DuckDBWarehouse

DB_PATH = os.environ.get("METRICS_DUCKDB_PATH")
pytestmark = pytest.mark.skipif(not DB_PATH, reason="METRICS_DUCKDB_PATH not set")


@pytest.fixture(scope="module")
def client():
    app_module.app.dependency_overrides[app_module.get_warehouse] = lambda: DuckDBWarehouse(DB_PATH)
    yield TestClient(app_module.app)
    app_module.app.dependency_overrides.clear()


def test_every_endpoint_answers(client):
    for path in ["/health", "/as-of", "/kpis", "/kpis/history", "/providers"]:
        resp = client.get(path)
        assert resp.status_code == 200, (path, resp.text)


def test_provider_shares_sum_to_one(client):
    rows = client.get("/providers").json()
    assert sum(r["token_share"] for r in rows) == pytest.approx(1.0)


def test_bridge_adds_up_when_available(client):
    history = client.get("/kpis/history").json()
    if len(history) < 2:
        pytest.skip("bridge needs two complete weeks")
    body = client.get("/bridge").json()
    assert body["spend_change_usd"] == pytest.approx(
        body["volume_effect_usd"] + body["mix_effect_usd"] + body["price_effect_usd"], rel=1e-9
    )
