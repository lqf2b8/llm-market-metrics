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
        "volume + mix + price = spend change exactly. Price effects are measured only from "
        "2026-10-28, when daily price snapshots began."
    )


class Envelope(BaseModel):
    source: str = SOURCE
