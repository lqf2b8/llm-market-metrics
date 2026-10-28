-- The weekly headline KPIs: the contract that the metrics API, the dashboards, the export
-- and the memo read. Column names match the metric names in models/semantic/_semantic.yml,
-- and CI checks these values against MetricFlow's own query output.

with weekly as (

    select * from {{ ref('fct_market_weekly') }}

)

select
    current_week.week_start,
    current_week.data_through_date,
    current_week.is_complete_week,
    current_week.is_spend_reliable,
    current_week.total_tokens as tokens,
    current_week.paid_tokens,
    current_week.implied_spend_usd,
    current_week.priced_coverage,
    current_week.effective_paid_usd_per_mtok,
    current_week.zero_priced_share,
    current_week.new_model_share,
    current_week.outside_top50_share,
    current_week.models_entering_top50,
    current_week.total_tokens * 1.0 / nullif(prior_week.total_tokens, 0) - 1 as tokens_wow_change,
    current_week.paid_tokens * 1.0 / nullif(prior_week.paid_tokens, 0) - 1 as paid_tokens_wow_change,
    current_week.implied_spend_usd / nullif(prior_week.implied_spend_usd, 0) - 1
        as implied_spend_wow_change,
    current_week.effective_paid_usd_per_mtok / nullif(prior_week.effective_paid_usd_per_mtok, 0) - 1
        as effective_paid_price_wow_change
from weekly as current_week
left join weekly as prior_week
    on prior_week.week_start = cast({{ dbt.dateadd('day', -7, 'current_week.week_start') }} as date)
