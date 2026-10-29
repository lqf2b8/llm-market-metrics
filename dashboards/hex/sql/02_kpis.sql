-- Hex SQL cell -> dataframe `kpis`
select
    week_start,
    is_spend_reliable,
    tokens,
    implied_spend_usd,
    effective_paid_usd_per_mtok,
    tokens_wow_change,
    implied_spend_wow_change,
    effective_paid_price_wow_change
from metrics.weekly_kpis
where is_complete_week
order by week_start
