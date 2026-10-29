{{ config(materialized='view', schema='metrics', tags=['post_analysis']) }}

-- The latest complete week's spend bridge as ordered steps, for a BI waterfall chart:
-- prior-week spend, then volume, mix and price. The chart's total bar is this week's spend.

with latest as (

    select *
    from {{ ref('spend_bridge_weekly') }}
    where week_start = (
        select max(week_start) from {{ ref('weekly_kpis') }} where is_complete_week
    )

)

select week_start, 1 as step_order, 'Prior week' as step, prior_spend_usd as amount_usd
from latest
union all
select week_start, 2, 'Volume', volume_effect_usd from latest
union all
select week_start, 3, 'Mix', mix_effect_usd from latest
union all
select week_start, 4, 'Price', price_effect_usd from latest
