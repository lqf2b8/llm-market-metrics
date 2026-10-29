{{ config(materialized='view', schema='metrics', tags=['post_analysis']) }}

-- One-week-ahead forecasts against actuals, long format (one row per week and series), for
-- BI line charts: the last 12 target weeks plus the next one.

with latest as (

    select max(week_start) as week_start
    from {{ ref('weekly_kpis') }}
    where is_complete_week

),

recent as (

    select
        case metric when 'tokens' then 'Tokens' else 'Implied spend' end as metric_label,
        forecast.*
    from {{ ref('forecast_vs_actual') }} as forecast
    cross join latest
    where forecast.horizon_weeks = 1
        and forecast.target_week > cast({{ dbt.dateadd('day', -84, 'latest.week_start') }} as date)

)

select metric_label, target_week, 'Actual' as series, actual as value from recent
where actual is not null
union all
select metric_label, target_week, 'Forecast', point from recent
union all
select metric_label, target_week, '90% range, low', lower_bound from recent
where lower_bound is not null
union all
select metric_label, target_week, '90% range, high', upper_bound from recent
where upper_bound is not null
