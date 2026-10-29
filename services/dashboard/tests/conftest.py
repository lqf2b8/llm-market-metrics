from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

LATEST = date(2026, 10, 19)
PROVIDERS = ["anthropic", "openai", "deepseek", "google", "z-ai", "other"]


def synthetic_frames(n_weeks: int = 30) -> dict[str, pd.DataFrame]:
    weeks = [LATEST - timedelta(days=7 * i) for i in range(n_weeks)][::-1]
    rng = np.random.default_rng(1)
    tokens = 1e13 * np.exp(np.cumsum(0.05 + 0.05 * rng.standard_normal(n_weeks)))
    spend = tokens * 1e-6
    kpis = pd.DataFrame(
        {
            "week_start": weeks,
            "is_spend_reliable": [i > 3 for i in range(n_weeks)],
            "tokens": tokens.astype("int64"),
            "implied_spend_usd": spend,
            "effective_paid_usd_per_mtok": np.linspace(2, 1.2, n_weeks),
            "tokens_wow_change": [None] + list(tokens[1:] / tokens[:-1] - 1),
            "implied_spend_wow_change": [None] + list(spend[1:] / spend[:-1] - 1),
            "effective_paid_price_wow_change": [None] + [-0.01] * (n_weeks - 1),
        }
    )
    forecasts = []
    for metric, series in (("tokens", tokens), ("implied_spend_usd", spend)):
        for i in range(12, n_weeks + 1):
            point = series[i - 1] * 1.05
            target = weeks[i - 1] + timedelta(days=7)
            forecasts.append(
                {
                    "metric": metric,
                    "origin_week": weeks[i - 1],
                    "target_week": target,
                    "model": "drift",
                    "point": point,
                    "lower_bound": None if i < 20 else point * 0.85,
                    "upper_bound": None if i < 20 else point * 1.15,
                    "interval_level": 0.9,
                    "actual": series[i] if i < n_weeks else None,
                    "is_covered": None,
                    "is_backfill": i < n_weeks,
                }
            )
    shares = np.array([0.4, 0.2, 0.15, 0.1, 0.1, 0.05])
    providers = pd.DataFrame(
        [
            {
                "week_start": w,
                "provider": p,
                "implied_spend_usd": s * 1e8,
                "token_share": s,
                "paid_token_share": s,
                "spend_share": s,
            }
            for w in weeks
            for p, s in zip(PROVIDERS, shares, strict=True)
        ]
    )
    return {
        "as_of": pd.DataFrame(
            {"data_through_date": [LATEST + timedelta(days=8)], "latest_week": [LATEST]}
        ),
        "kpis": kpis,
        "bridge": pd.DataFrame(
            [
                {
                    "prior_spend_usd": 159.1e6,
                    "spend_usd": 176.9e6,
                    "volume_effect_usd": 24.9e6,
                    "mix_effect_usd": -7.1e6,
                    "price_effect_usd": 1e-9,
                }
            ]
        ),
        "bridge_providers": pd.DataFrame(
            [
                {
                    "provider": "anthropic",
                    "spend_change_usd": 16.6e6,
                    "volume_effect_usd": 14e6,
                    "mix_effect_usd": 2.6e6,
                    "price_effect_usd": 0.0,
                }
            ]
        ),
        "forecasts": pd.DataFrame(forecasts),
        "providers": providers,
    }


@pytest.fixture
def frames():
    return synthetic_frames()
