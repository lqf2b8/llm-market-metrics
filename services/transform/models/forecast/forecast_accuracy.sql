{{ config(materialized='view', schema='metrics') }}

-- pct_error is actual / point - 1, so mean_pct_error > 0 means forecasts ran low.

with evaluated as (

    select * from {{ ref('forecast_vs_actual') }}
    where actual is not null

)

select
    metric,
    horizon_weeks,
    count(*) as n_evaluated,
    count(is_covered) as n_with_interval,
    avg(case when is_covered then 1.0 when is_covered is not null then 0.0 end) as coverage,
    avg(abs(pct_error)) as mean_abs_pct_error,
    avg(pct_error) as mean_pct_error,
    count(case when not is_backfill then 1 end) as n_live_evaluated,
    avg(case when not is_backfill and is_covered then 1.0
             when not is_backfill and is_covered is not null then 0.0 end) as live_coverage,
    avg(case when not is_backfill then abs(pct_error) end) as live_mean_abs_pct_error,
    min(origin_week) as first_origin_week,
    max(target_week) as last_target_week
from evaluated
group by metric, horizon_weeks
