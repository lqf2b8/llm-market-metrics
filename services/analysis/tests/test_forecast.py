from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

from analysis import forecast as fc

START = date(2025, 1, 6)  # a Monday


def weekly(values):
    return [START + timedelta(days=7 * i) for i in range(len(values))], list(values)


def noisy_growth(n: int, growth: float = 0.05, noise: float = 0.08, seed: int = 7):
    rng = np.random.default_rng(seed)
    return list(1e12 * np.exp(np.cumsum(growth + noise * rng.standard_normal(n))))


def test_conformal_halfwidth_uses_the_finite_sample_quantile():
    errors = [float(i) for i in range(1, 20)]  # n = 19 -> k = ceil(20 * 0.9) = 18
    assert fc.conformal_halfwidth(errors) == 18.0


def test_conformal_halfwidth_refuses_too_few_errors():
    assert fc.conformal_halfwidth([0.1] * (fc.MIN_CALIBRATION - 1)) is None
    assert fc.conformal_halfwidth([0.1] * fc.MIN_CALIBRATION) == 0.1


def test_models_recover_exact_geometric_growth():
    log_y = np.log(1e12 * 1.05 ** np.arange(20))
    assert fc._drift(log_y, 2) == pytest.approx(log_y[-1] + 2 * math.log(1.05))
    assert fc._loglinear(log_y, 3) == pytest.approx(log_y[-1] + 3 * math.log(1.05))
    assert fc._naive(log_y, 4) == log_y[-1]


def test_no_lookahead_forecasts_match_those_made_with_truncated_history():
    """Each origin's forecast, computed from the full series, must equal the forecast
    computed when the series ended at that origin."""
    weeks, values = weekly(noisy_growth(60))
    full = {
        (r["origin_week"], r["horizon_weeks"]): r for r in fc.forecasts("tokens", weeks, values)
    }
    for cut in (20, 33, 47, 60):
        truncated = fc.forecasts("tokens", weeks[:cut], values[:cut])
        for r in truncated:
            other = full[(r["origin_week"], r["horizon_weeks"])]
            assert r["model"] == other["model"]
            assert r["point"] == pytest.approx(other["point"])
            assert r["lower"] == other["lower"] or r["lower"] == pytest.approx(other["lower"])


def test_intervals_appear_only_with_enough_calibration_errors():
    weeks, values = weekly(noisy_growth(40))
    rows = fc.forecasts("tokens", weeks, values)
    first_origin = min(r["origin_week"] for r in rows)
    assert all(r["lower"] is None for r in rows if r["origin_week"] == first_origin)
    later = [r for r in rows if r["n_calibration"] >= fc.MIN_CALIBRATION]
    assert later and all(r["lower"] < r["point"] < r["upper"] for r in later)


def test_coverage_is_close_to_nominal_on_a_stationary_growth_process():
    """On a long series whose noise does not change, 90% intervals should cover about 90%
    of realised values. This guards against an off-by-one in the conformal quantile."""
    covered = total = 0
    for seed in range(8):
        weeks, values = weekly(noisy_growth(160, seed=seed))
        actual = dict(zip(weeks, values, strict=True))
        for r in fc.forecasts("tokens", weeks, values):
            if r["lower"] is not None and r["target_week"] in actual:
                total += 1
                covered += r["lower"] <= actual[r["target_week"]] <= r["upper"]
    assert total > 3000
    assert 0.85 <= covered / total <= 0.95


def test_short_or_nonpositive_series_produce_nothing():
    weeks, values = weekly(noisy_growth(fc.MIN_TRAIN - 1))
    assert fc.forecasts("tokens", weeks, values) == []
    weeks, values = weekly([1.0] * 20 + [0.0])
    assert fc.forecasts("tokens", weeks, values) == []


def test_only_the_contiguous_tail_is_used():
    weeks = [START, START + timedelta(days=7), START + timedelta(days=21)]
    assert fc.contiguous_tail(weeks, [1, 2, 3]) == ([weeks[2]], [3])


def test_target_week_is_horizon_weeks_after_origin():
    weeks, values = weekly(noisy_growth(30))
    for r in fc.forecasts("tokens", weeks, values):
        assert (r["target_week"] - r["origin_week"]).days == 7 * r["horizon_weeks"]
