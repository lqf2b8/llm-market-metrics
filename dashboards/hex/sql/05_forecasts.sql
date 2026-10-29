-- Hex SQL cell -> dataframe `forecasts`: every frozen 1-week-ahead forecast and its actual
select metric, origin_week, target_week, model, point, lower_bound, upper_bound,
    interval_level, actual, is_covered, is_backfill
from metrics.forecast_vs_actual
where horizon_weeks = 1
order by metric, target_week
