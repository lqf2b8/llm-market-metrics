{{ config(materialized='view', schema='metrics') }}

with frozen as (

    select * from {{ source('analysis', 'forecast_frozen') }}

),

actuals as (

    select week_start, 'tokens' as metric, cast(tokens as {{ dbt.type_float() }}) as actual
    from {{ ref('weekly_kpis') }}
    where is_complete_week

    union all

    select week_start, 'implied_spend_usd' as metric, implied_spend_usd as actual
    from {{ ref('weekly_kpis') }}
    where is_spend_reliable

)

select
    frozen.metric,
    frozen.origin_week,
    frozen.target_week,
    frozen.horizon_weeks,
    frozen.model,
    frozen.point,
    frozen.lower as lower_bound,
    frozen.upper as upper_bound,
    frozen.interval_level,
    frozen.n_calibration,
    frozen.is_backfill,
    frozen.produced_at,
    actuals.actual,
    actuals.actual / nullif(frozen.point, 0) - 1 as pct_error,
    case
        when actuals.actual is null or frozen.lower is null then null
        else actuals.actual between frozen.lower and frozen.upper
    end as is_covered
from frozen
left join actuals
    on actuals.metric = frozen.metric
    and actuals.week_start = frozen.target_week
