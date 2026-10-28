-- Weekly marts must add back to the daily facts to the token, and provider rows must add
-- up to the market row. Returns one row per week that does not reconcile.

with daily as (

    select week_start, sum(total_tokens) as tokens, sum(coalesce(implied_spend_usd, 0)) as spend
    from {{ ref('fct_model_usage_daily') }}
    group by week_start

),

providers as (

    select week_start, sum(total_tokens) as tokens, sum(implied_spend_usd) as spend
    from {{ ref('fct_provider_weekly') }}
    group by week_start

),

market as (

    select week_start, total_tokens as tokens, implied_spend_usd as spend
    from {{ ref('fct_market_weekly') }}

)

select
    market.week_start,
    market.tokens as market_tokens,
    daily.tokens as daily_tokens,
    providers.tokens as provider_tokens,
    market.spend as market_spend,
    daily.spend as daily_spend,
    providers.spend as provider_spend
from market
full outer join daily on daily.week_start = market.week_start
full outer join providers on providers.week_start = coalesce(market.week_start, daily.week_start)
where market.tokens is null
    or daily.tokens is null
    or providers.tokens is null
    or market.tokens != daily.tokens
    or market.tokens != providers.tokens
    -- Spend is a float sum; allow a tenth of a cent of rounding.
    or abs(market.spend - daily.spend) > 0.001
    or abs(market.spend - providers.spend) > 0.001
