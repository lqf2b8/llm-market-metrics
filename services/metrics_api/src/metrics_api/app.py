"""Read-only HTTP API over the governed metrics.

Every endpoint reads the dbt `metrics` views and nothing else, so the API cannot compute a
number that disagrees with the dashboards or the memo. Weeks are ISO weeks named by their
Monday; when no week is given, the latest complete week is used.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import warehouse as wh
from .schemas import (
    SOURCE,
    AsOf,
    BridgeProvider,
    ForecastAccuracy,
    ForecastPoint,
    Forecasts,
    ProviderWeek,
    SpendBridge,
    WeeklyKpis,
)

app = FastAPI(
    title="LLM API Market Metrics",
    version="0.1.0",
    description=(
        "Weekly metrics for the LLM API market, computed from OpenRouter's public usage "
        "data. Implied spend is tokens x list price: an index, not anyone's revenue. " + SOURCE
    ),
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])


@lru_cache
def get_warehouse() -> wh.Warehouse:
    return wh.from_env()


Warehouse = Annotated[wh.Warehouse, Depends(get_warehouse)]
WeekParam = Annotated[
    date | None, Query(description="Monday of the ISO week; default: latest complete week")
]


def _latest_complete_week(db: wh.Warehouse) -> date:
    rows = db.query(
        "select max(week_start) as week from {metrics}.weekly_kpis where is_complete_week"
    )
    if not rows or rows[0]["week"] is None:
        raise HTTPException(503, "No complete week of data yet")
    return rows[0]["week"]


def _resolve_week(db: wh.Warehouse, week: date | None) -> date:
    if week is None:
        return _latest_complete_week(db)
    if week.weekday() != 0:
        raise HTTPException(422, f"{week} is not a Monday; weeks are named by their Monday")
    return week


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/as-of", response_model=AsOf)
def as_of(db: Warehouse) -> AsOf:
    row = db.query(
        """
        select
            max(data_through_date) as data_through_date,
            max(case when is_complete_week then week_start end) as latest_complete_week,
            max(case when is_spend_reliable then week_start end) as latest_reliable_week
        from {metrics}.weekly_kpis
        """
    )[0]
    if row["data_through_date"] is None:
        raise HTTPException(503, "No data loaded yet")
    return AsOf(**row)


@app.get("/kpis", response_model=WeeklyKpis)
def kpis(db: Warehouse, week: WeekParam = None) -> WeeklyKpis:
    week = _resolve_week(db, week)
    rows = db.query("select * from {metrics}.weekly_kpis where week_start = :week", {"week": week})
    if not rows:
        raise HTTPException(404, f"No data for the week of {week}")
    return WeeklyKpis(**rows[0])


@app.get("/kpis/history", response_model=list[WeeklyKpis])
def kpis_history(
    db: Warehouse,
    start: Annotated[date, Query(description="First Monday to include")] = date(2025, 1, 1),
    end: Annotated[date | None, Query(description="Last Monday to include")] = None,
    complete_only: bool = True,
) -> list[WeeklyKpis]:
    rows = db.query(
        """
        select * from {metrics}.weekly_kpis
        where week_start >= :start
            and week_start <= :end
            and (is_complete_week or not :complete_only)
        order by week_start
        """,
        {"start": start, "end": end or date(9999, 12, 31), "complete_only": complete_only},
    )
    return [WeeklyKpis(**r) for r in rows]


@app.get("/providers", response_model=list[ProviderWeek])
def providers(db: Warehouse, week: WeekParam = None) -> list[ProviderWeek]:
    week = _resolve_week(db, week)
    rows = db.query(
        """
        select * from {metrics}.provider_weekly
        where week_start = :week
        order by implied_spend_usd desc, tokens desc
        """,
        {"week": week},
    )
    if not rows:
        raise HTTPException(404, f"No data for the week of {week}")
    return [ProviderWeek(**r) for r in rows]


@app.get("/bridge", response_model=SpendBridge)
def bridge(db: Warehouse, week: WeekParam = None) -> SpendBridge:
    week = _resolve_week(db, week)
    totals = db.query(
        "select * from {metrics}.spend_bridge_weekly where week_start = :week", {"week": week}
    )
    if not totals:
        raise HTTPException(404, f"No bridge for the week of {week} (needs the prior week too)")
    by_provider = db.query(
        """
        select provider, prior_spend_usd, spend_usd, spend_change_usd,
            volume_effect_usd, mix_effect_usd, price_effect_usd
        from {metrics}.spend_bridge_provider_weekly
        where week_start = :week
        order by abs(spend_change_usd) desc
        """,
        {"week": week},
    )
    fields = set(SpendBridge.model_fields) - {"providers", "note"}
    return SpendBridge(
        **{k: v for k, v in totals[0].items() if k in fields},
        providers=[BridgeProvider(**r) for r in by_provider],
    )


@app.get("/forecast", response_model=Forecasts)
def forecast(db: Warehouse) -> Forecasts:
    """The latest frozen forecast for each metric, 1-4 weeks ahead, and the track record."""
    points = db.query(
        """
        select metric, origin_week, target_week, horizon_weeks, model, point,
            lower_bound, upper_bound, interval_level, actual
        from {metrics}.forecast_latest
        order by metric, horizon_weeks
        """
    )
    if not points:
        raise HTTPException(503, "No forecasts yet; run the analysis service")
    accuracy = db.query("select * from {metrics}.forecast_accuracy order by metric, horizon_weeks")
    fields = set(ForecastAccuracy.model_fields)
    return Forecasts(
        forecasts=[ForecastPoint(**r) for r in points],
        accuracy=[
            ForecastAccuracy(**{k: v for k, v in r.items() if k in fields}) for r in accuracy
        ],
    )


@app.get("/forecast/history", response_model=list[ForecastPoint])
def forecast_history(
    db: Warehouse,
    metric: Annotated[str | None, Query(description="tokens or implied_spend_usd")] = None,
    origin_week: Annotated[
        date | None, Query(description="Week the forecast was made from")
    ] = None,
    target_week: Annotated[date | None, Query(description="Week the forecast was for")] = None,
    horizon_weeks: Annotated[int | None, Query(ge=1, le=4)] = None,
) -> list[ForecastPoint]:
    """Frozen forecasts with their actuals, filtered by any combination of the parameters."""
    # Only provided filters go into the SQL: BigQuery cannot type a null parameter compared
    # with a DATE column. Column names come from this fixed dict, never from the request.
    filters = {
        "metric": metric,
        "origin_week": origin_week,
        "target_week": target_week,
        "horizon_weeks": horizon_weeks,
    }
    given = {k: v for k, v in filters.items() if v is not None}
    where = " and ".join(f"{k} = :{k}" for k in given) or "true"
    rows = db.query(
        f"""
        select metric, origin_week, target_week, horizon_weeks, model, point,
            lower_bound, upper_bound, interval_level, actual
        from {{metrics}}.forecast_vs_actual
        where {where}
        order by metric, origin_week, horizon_weeks
        """,
        given,
    )
    return [ForecastPoint(**r) for r in rows]
