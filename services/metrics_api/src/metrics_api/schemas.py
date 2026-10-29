"""Response models. Field names match the metric names in the dbt semantic layer."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

SOURCE = "Source: OpenRouter (openrouter.ai/rankings), CC BY 4.0"


class AsOf(BaseModel):
    data_through_date: date
    latest_complete_week: date
    latest_reliable_week: date | None
    source: str = SOURCE


class WeeklyKpis(BaseModel):
    week_start: date = Field(description="Monday of the ISO week")
    data_through_date: date
    is_complete_week: bool
    is_spend_reliable: bool = Field(description="Complete week with >= 90% of tokens priced")
    tokens: int
    paid_tokens: int
    implied_spend_usd: float = Field(description="Tokens x blended list price; an index")
    priced_coverage: float | None
    effective_paid_usd_per_mtok: float | None
    zero_priced_share: float | None
    new_model_share: float | None
    outside_top50_share: float | None
    models_entering_top50: int
    tokens_wow_change: float | None
    paid_tokens_wow_change: float | None
    implied_spend_wow_change: float | None
    effective_paid_price_wow_change: float | None


class ProviderWeek(BaseModel):
    week_start: date
    provider: str
    is_complete_week: bool
    models_ranked: int
    tokens: int
    paid_tokens: int
    implied_spend_usd: float
    token_share: float | None
    paid_token_share: float | None
    spend_share: float | None
    spend_minus_paid_token_share: float | None
    tokens_wow_change: float | None
    spend_wow_change: float | None


class BridgeProvider(BaseModel):
    provider: str
    prior_spend_usd: float
    spend_usd: float
    spend_change_usd: float
    volume_effect_usd: float
    mix_effect_usd: float
    price_effect_usd: float


class SpendBridge(BaseModel):
    week_start: date
    prior_week_start: date
    is_complete_pair: bool
    is_reliable_pair: bool
    prior_spend_usd: float
    spend_usd: float
    spend_change_usd: float
    volume_effect_usd: float
    mix_effect_usd: float
    price_effect_usd: float
    models_entering: int
    models_exiting: int
    providers: list[BridgeProvider]
    note: str = (
        "volume + mix + price = spend change exactly. Daily price snapshots began on "
        "2026-10-28; earlier usage is priced at the first snapshot, so price effects for "
        "weeks before then are $0 by construction, not evidence that prices were flat."
    )


class Envelope(BaseModel):
    source: str = SOURCE


class ForecastPoint(BaseModel):
    metric: str
    origin_week: date = Field(description="Last complete week the forecast could see")
    target_week: date
    horizon_weeks: int
    model: str = Field(description="naive, drift or loglinear; chosen on recent backtest error")
    point: float
    lower_bound: float | None = Field(description="None until enough backtest errors exist")
    upper_bound: float | None
    interval_level: float
    actual: float | None = Field(description="Filled in once the target week is in")


class ForecastAccuracy(BaseModel):
    metric: str
    horizon_weeks: int
    n_evaluated: int
    n_with_interval: int
    coverage: float | None = Field(description="Share of actuals inside the interval")
    mean_abs_pct_error: float | None
    mean_pct_error: float | None = Field(description="> 0 means forecasts ran low")
    n_live_evaluated: int
    live_coverage: float | None
    live_mean_abs_pct_error: float | None


class Forecasts(BaseModel):
    forecasts: list[ForecastPoint]
    accuracy: list[ForecastAccuracy]
    note: str = (
        "Forecasts are frozen when made and never revised. Intervals are split-conformal at "
        "90%, calibrated on the last 26 weeks of backtest errors. Accuracy includes backfilled "
        "forecasts (rebuilt from history without lookahead); the live_* fields count only "
        "forecasts made in real time."
    )
