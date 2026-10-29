{{ config(materialized='view', schema='metrics', tags=['post_analysis']) }}

-- The last 26 complete weeks for sparklines. Spend and price are null in weeks where spend
-- is not reliable, so a chart cannot draw a trend through them.

select
    week_start,
    tokens,
    case when is_spend_reliable then implied_spend_usd end as implied_spend_usd,
    case when is_spend_reliable then effective_paid_usd_per_mtok end as effective_paid_usd_per_mtok
from {{ ref('weekly_kpis') }}
where is_complete_week
    and week_start > cast({{ dbt.dateadd('day', -182, '(select max(week_start) from ' ~ ref('weekly_kpis') ~ ' where is_complete_week)') }} as date)
