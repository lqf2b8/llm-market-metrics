"""Build the facts file for one week from the metrics API.

The facts file is the memo's only input. Every number in it is already formatted for
display, and the number check accepts exactly these strings.
"""

from __future__ import annotations

from typing import Any

import requests

from . import formatting as fmt

TOP_PROVIDERS = 6
HISTORY_WEEKS = 8


class MetricsApi:
    def __init__(self, base_url: str, session: requests.Session | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()

    def get(self, path: str, **params: Any) -> Any:
        resp = self.session.get(f"{self.base_url}{path}", params=params or None, timeout=30)
        resp.raise_for_status()
        return resp.json()


def build_facts(api: MetricsApi, week: str | None = None) -> dict[str, Any]:
    as_of = api.get("/as-of")
    week = week or as_of["latest_complete_week"]
    kpis = api.get("/kpis", week=week)
    history = api.get("/kpis/history")
    providers = api.get("/providers", week=week)
    bridge = api.get("/bridge", week=week)
    return assemble(as_of, kpis, history, providers, bridge)


def assemble(
    as_of: dict[str, Any],
    kpis: dict[str, Any],
    history: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    bridge: dict[str, Any],
) -> dict[str, Any]:
    week = kpis["week_start"]
    recent = [h for h in history if h["week_start"] <= week][-HISTORY_WEEKS:]
    named = [p for p in providers if p["provider"] != "other"]
    by_spend = sorted(named, key=lambda p: p["implied_spend_usd"], reverse=True)[:TOP_PROVIDERS]
    gaps = sorted(
        (p for p in named if p["spend_minus_paid_token_share"] is not None),
        key=lambda p: abs(p["spend_minus_paid_token_share"]),
        reverse=True,
    )[:3]

    return {
        "week_start": week,
        "data_through_date": kpis["data_through_date"],
        "source": as_of["source"],
        "is_spend_reliable": kpis["is_spend_reliable"],
        "headline": {
            "tokens": fmt.tokens(kpis["tokens"]),
            "tokens_wow_change": fmt.signed_pct(kpis["tokens_wow_change"]),
            "paid_tokens": fmt.tokens(kpis["paid_tokens"]),
            "paid_tokens_wow_change": fmt.signed_pct(kpis["paid_tokens_wow_change"]),
            "implied_spend": fmt.money(kpis["implied_spend_usd"]),
            "implied_spend_wow_change": fmt.signed_pct(kpis["implied_spend_wow_change"]),
            "effective_paid_price": fmt.price(kpis["effective_paid_usd_per_mtok"]),
            "effective_paid_price_wow_change": fmt.signed_pct(
                kpis["effective_paid_price_wow_change"]
            ),
            "free_share_of_top50_tokens": fmt.pct(kpis["zero_priced_share"]),
            "new_model_share_of_top50_tokens": fmt.pct(kpis["new_model_share"]),
            "models_entering_top50": kpis["models_entering_top50"],
            "priced_coverage": fmt.pct(kpis["priced_coverage"]),
        },
        "spend_bridge": {
            "prior_week_start": bridge["prior_week_start"],
            "prior_spend": fmt.money(bridge["prior_spend_usd"]),
            "spend": fmt.money(bridge["spend_usd"]),
            "change": fmt.signed_money(bridge["spend_change_usd"]),
            "volume_effect": fmt.signed_money(bridge["volume_effect_usd"]),
            "mix_effect": fmt.signed_money(bridge["mix_effect_usd"]),
            "price_effect": fmt.signed_money(bridge["price_effect_usd"]),
            "price_effect_note": bridge["note"],
            "largest_provider_moves": [
                {
                    "provider": p["provider"],
                    "change": fmt.signed_money(p["spend_change_usd"]),
                    "volume_effect": fmt.signed_money(p["volume_effect_usd"]),
                    "mix_effect": fmt.signed_money(p["mix_effect_usd"]),
                    "price_effect": fmt.signed_money(p["price_effect_usd"]),
                }
                for p in bridge["providers"][:4]
            ],
        },
        "providers_by_spend": [
            {
                "provider": p["provider"],
                "implied_spend": fmt.money(p["implied_spend_usd"]),
                "spend_share": fmt.pct(p["spend_share"]),
                "paid_token_share": fmt.pct(p["paid_token_share"]),
                "tokens_wow_change": fmt.signed_pct(p["tokens_wow_change"]),
            }
            for p in by_spend
        ],
        "pricing_power_gaps": [
            {
                "provider": p["provider"],
                "spend_share": fmt.pct(p["spend_share"]),
                "paid_token_share": fmt.pct(p["paid_token_share"]),
                "gap": fmt.points(p["spend_minus_paid_token_share"]),
            }
            for p in gaps
        ],
        "recent_weeks": [
            {
                "week_start": h["week_start"],
                "tokens": fmt.tokens(h["tokens"]),
                "implied_spend": fmt.money(h["implied_spend_usd"]),
                "is_spend_reliable": h["is_spend_reliable"],
            }
            for h in recent
        ],
        "caveats": [
            "OpenRouter is one marketplace, not the whole market.",
            "Implied spend is tokens x list price with an assumed prompt/completion split: "
            "an index, not revenue. Shares and changes are robust to the split; the level is not.",
            "Token counts use each provider's tokenizer and are not strictly comparable.",
        ],
    }
