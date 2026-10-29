{{ config(materialized='view', schema='metrics') }}

with latest as (

    select metric, max(origin_week) as origin_week
    from {{ ref('forecast_vs_actual') }}
    group by metric

)

select forecast.*
from {{ ref('forecast_vs_actual') }} as forecast
inner join latest
    on latest.metric = forecast.metric
    and latest.origin_week = forecast.origin_week
