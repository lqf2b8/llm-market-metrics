"""Weekly forecasts with honest intervals.

Three deliberately simple models compete, all on the log scale (growth is multiplicative):

    naive      next weeks equal this week
    drift      this week grown at the average weekly growth of the last DRIFT_WINDOW weeks
    loglinear  a straight line through the last TREND_WINDOW weeks of log values

Everything is computed as of each origin week using only data up to that week:

1. Rolling-origin backtest: every model forecasts horizons 1-4 from every origin.
2. Model selection at origin o uses only errors already observable at o (target week <= o),
   over the most recent SELECTION_WINDOW origins. No lookahead.
3. Split conformal intervals: the interval half-width at horizon h is a quantile of the
   chosen model's past absolute log errors at h (again only those observable at o). With
   n calibration errors the quantile index is ceil((n + 1) * (1 - alpha)); below the
   minimum n the interval is omitted rather than guessed.

The output is a list of plain dicts, one per (origin, horizon); nothing here touches a
database, so it is unit-testable on synthetic series.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from datetime import date, timedelta

import numpy as np

HORIZONS = (1, 2, 3, 4)
DRIFT_WINDOW = 8
TREND_WINDOW = 12
MIN_TRAIN = 12  # weeks of history before the first forecast
SELECTION_WINDOW = 26  # most recent origins whose errors inform selection and calibration
ALPHA = 0.10  # 90% intervals
MIN_CALIBRATION = math.ceil(1 / ALPHA) - 1  # 9: fewer errors cannot support a 90% quantile


def _naive(log_y: np.ndarray, h: int) -> float:
    return float(log_y[-1])


def _drift(log_y: np.ndarray, h: int) -> float:
    recent = log_y[-(DRIFT_WINDOW + 1) :]
    growth = float(np.mean(np.diff(recent))) if len(recent) > 1 else 0.0
    return float(log_y[-1]) + h * growth


def _loglinear(log_y: np.ndarray, h: int) -> float:
    recent = log_y[-TREND_WINDOW:]
    t = np.arange(len(recent), dtype=float)
    slope, intercept = np.polyfit(t, recent, 1)
    return float(intercept + slope * (len(recent) - 1 + h))


MODELS: dict[str, Callable[[np.ndarray, int], float]] = {
    "naive": _naive,
    "drift": _drift,
    "loglinear": _loglinear,
}


def conformal_halfwidth(abs_errors: Sequence[float], alpha: float = ALPHA) -> float | None:
    """Split-conformal quantile of absolute errors; None if there are too few."""
    n = len(abs_errors)
    k = math.ceil((n + 1) * (1 - alpha))
    if n < MIN_CALIBRATION or k > n:
        return None
    return float(sorted(abs_errors)[k - 1])


def backtest(log_y: np.ndarray) -> dict[tuple[str, int, int], float]:
    """Predicted log value for every (model, origin index, horizon)."""
    preds = {}
    for origin in range(MIN_TRAIN - 1, len(log_y)):
        history = log_y[: origin + 1]
        for name, model in MODELS.items():
            for h in HORIZONS:
                preds[(name, origin, h)] = model(history, h)
    return preds


def _observable_errors(
    preds: dict[tuple[str, int, int], float],
    log_y: np.ndarray,
    model: str,
    as_of: int,
    horizons: Sequence[int],
) -> list[float]:
    """Absolute log errors of `model` whose target week is known by origin `as_of`,
    from the most recent SELECTION_WINDOW origins."""
    errors = []
    first_origin = max(MIN_TRAIN - 1, as_of - SELECTION_WINDOW)
    for origin in range(first_origin, as_of):
        for h in horizons:
            target = origin + h
            if target <= as_of:
                errors.append(abs(log_y[target] - preds[(model, origin, h)]))
    return errors


def choose_model(preds, log_y: np.ndarray, as_of: int) -> str:
    """Lowest mean absolute log error over all horizons, using only what is known at as_of."""
    scores = {}
    for name in MODELS:
        errs = _observable_errors(preds, log_y, name, as_of, HORIZONS)
        if errs:
            scores[name] = float(np.mean(errs))
    return min(scores, key=scores.get) if scores else "naive"


def contiguous_tail(weeks: Sequence[date], values: Sequence[float]) -> tuple[list, list]:
    """The longest run of consecutive weeks ending at the last week (no gaps)."""
    if not weeks:
        return [], []
    start = len(weeks) - 1
    while start > 0 and (weeks[start] - weeks[start - 1]).days == 7:
        start -= 1
    return list(weeks[start:]), list(values[start:])


def forecasts(
    metric: str, weeks: Sequence[date], values: Sequence[float]
) -> list[dict[str, object]]:
    """Forecast rows for every origin with enough history, as each would have been made then."""
    weeks, values = contiguous_tail(weeks, values)
    if len(values) < MIN_TRAIN or any(v is None or v <= 0 for v in values):
        return []
    log_y = np.log(np.asarray(values, dtype=float))
    preds = backtest(log_y)
    rows = []
    for origin in range(MIN_TRAIN - 1, len(log_y)):
        model = choose_model(preds, log_y, origin)
        for h in HORIZONS:
            center = preds[(model, origin, h)]
            calibration = _observable_errors(preds, log_y, model, origin, [h])
            half = conformal_halfwidth(calibration)
            rows.append(
                {
                    "metric": metric,
                    "origin_week": weeks[origin],
                    "target_week": weeks[origin] + timedelta(days=7 * h),
                    "horizon_weeks": h,
                    "model": model,
                    "point": math.exp(center),
                    "lower": None if half is None else math.exp(center - half),
                    "upper": None if half is None else math.exp(center + half),
                    "interval_level": 1 - ALPHA,
                    "n_calibration": len(calibration),
                }
            )
    return rows
