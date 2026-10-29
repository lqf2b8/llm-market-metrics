{{ config(materialized='view', schema='metrics', tags=['post_analysis']) }}

-- One row: the latest complete week's headline numbers, shaped for BI scorecards.

select
    week_start,
    data_through_date,
    is_spend_reliable,
    tokens,
    implied_spend_usd,
    effective_paid_usd_per_mtok,
    tokens_wow_change,
    implied_spend_wow_change,
    effective_paid_price_wow_change
from {{ ref('weekly_kpis') }}
where week_start = (select max(week_start) from {{ ref('weekly_kpis') }} where is_complete_week)
