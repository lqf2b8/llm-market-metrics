-- One row per (ISO week, provider): volume, implied spend and shares, with week-over-week
-- change against the provider's own prior week. Provider "other" is the bucket of models
-- outside the daily top 50, kept so provider rows sum to the market total.

with daily as (

    select * from {{ ref('fct_model_usage_daily') }}

),

market as (

    select week_start, is_complete_week, total_tokens, paid_tokens, implied_spend_usd
    from {{ ref('fct_market_weekly') }}

),

provider_weekly as (

    select
        week_start,
        provider,
        sum(total_tokens) as total_tokens,
        sum(case when not is_other_bucket and not is_zero_priced then total_tokens else 0 end)
            as paid_tokens,
        sum(case when is_priced then total_tokens else 0 end) as priced_tokens,
        coalesce(sum(implied_spend_usd), 0) as implied_spend_usd,
        count(distinct model_permaslug) as models_ranked
    from daily
    group by week_start, provider

),

with_shares as (

    select
        provider_weekly.*,
        market.is_complete_week,
        provider_weekly.total_tokens * 1.0 / nullif(market.total_tokens, 0) as token_share,
        provider_weekly.paid_tokens * 1.0 / nullif(market.paid_tokens, 0) as paid_token_share,
        provider_weekly.implied_spend_usd / nullif(market.implied_spend_usd, 0) as spend_share
    from provider_weekly
    inner join market on market.week_start = provider_weekly.week_start

)

select
    current_week.*,
    prior_week.total_tokens as prior_week_tokens,
    prior_week.implied_spend_usd as prior_week_implied_spend_usd,
    current_week.total_tokens * 1.0 / nullif(prior_week.total_tokens, 0) - 1 as tokens_wow_change,
    current_week.implied_spend_usd / nullif(prior_week.implied_spend_usd, 0) - 1
        as spend_wow_change,
    -- Spend share above token share means the provider earns more per token than average.
    current_week.spend_share - current_week.paid_token_share as spend_minus_paid_token_share
from with_shares as current_week
left join with_shares as prior_week
    on prior_week.provider = current_week.provider
    and prior_week.week_start = cast({{ dbt.dateadd('day', -7, 'current_week.week_start') }} as date)
