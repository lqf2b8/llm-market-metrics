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
    return assemble(as_of, kpis, history, providers, bridge, fetch_plan(api, week))


def fetch_plan(api: MetricsApi, week: str) -> dict[str, Any] | None:
    """Forecasts for this week (made a week earlier), from this week, and the track record.
    None if the analysis service has not produced forecasts yet."""
    try:
        accuracy = api.get("/forecast")["accuracy"]
    except requests.HTTPError as err:
        if err.response is not None and err.response.status_code in (404, 503):
            return None
        raise
    return {
        "for_this_week": api.get("/forecast/history", target_week=week, horizon_weeks=1),
        "for_next_week": api.get("/forecast/history", origin_week=week, horizon_weeks=1),
        "accuracy": accuracy,
    }


def assemble(
    as_of: dict[str, Any],
    kpis: dict[str, Any],
    history: list[dict[str, Any]],
    providers: list[dict[str, Any]],
    bridge: dict[str, Any],
    plan: dict[str, Any] | None = None,
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
        "against_plan": against_plan(plan),
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


METRIC_LABELS = {
    "tokens": ("tokens", fmt.tokens),
    "implied_spend_usd": ("implied spend", fmt.money),
}
PLAN_NOTE = (
    "The plan is a statistical forecast, frozen the week it was made and never revised. "
    "Ranges are 90% prediction intervals. Implied spend is forecast only from weeks where "
    "spend is reliable."
)


def against_plan(plan: dict[str, Any] | None) -> dict[str, Any]:
    if plan is None:
        return {"available": False, "note": "No forecasts have been produced yet."}

    def label(row: dict[str, Any]) -> tuple[str, Any]:
        return METRIC_LABELS[row["metric"]]

    def forecast_range(row: dict[str, Any]) -> dict[str, Any]:
        name, show = label(row)
        if row["lower_bound"] is None:
            return {"forecast": show(row["point"]), "range_low": None, "range_high": None}
        return {
            "forecast": show(row["point"]),
            "range_low": show(row["lower_bound"]),
            "range_high": show(row["upper_bound"]),
        }

    this_week = []
    for row in plan["for_this_week"]:
        name, show = label(row)
        entry = {"metric": name, "forecast_made_week_of": row["origin_week"], **forecast_range(row)}
        if row["actual"] is not None:
            entry["actual"] = show(row["actual"])
            entry["actual_vs_forecast"] = fmt.signed_pct(row["actual"] / row["point"] - 1)
            if row["lower_bound"] is not None:
                inside = row["lower_bound"] <= row["actual"] <= row["upper_bound"]
                entry["result"] = (
                    "inside the range"
                    if inside
                    else (
                        "above the range"
                        if row["actual"] > row["upper_bound"]
                        else "below the range"
                    )
                )
        this_week.append(entry)

    return {
        "available": True,
        "this_week_vs_forecast": this_week,
        "next_week_forecast": [
            {"metric": label(r)[0], "week_of": r["target_week"], **forecast_range(r)}
            for r in plan["for_next_week"]
        ],
        "track_record_one_week_ahead": [
            {
                "metric": METRIC_LABELS[a["metric"]][0],
                "weeks_with_a_range": a["n_with_interval"],
                "share_of_actuals_inside_range": fmt.pct(a["coverage"]),
                "average_miss": fmt.pct(a["mean_abs_pct_error"]),
            }
            for a in plan["accuracy"]
            if a["horizon_weeks"] == 1 and a["coverage"] is not None
        ],
        "note": PLAN_NOTE,
    }
