-- Price-volume-mix bridge of the week-over-week change in implied spend, one row per
-- (week, model). For each model i, with Q = market priced tokens, q = model tokens,
-- w = q / Q its share and p its average price (week 0 = prior week, 1 = this week):
--
--   volume_effect = (Q1 - Q0) * w0 * p0      market growth at last week's prices and mix
--   mix_effect    = Q1 * (w1 - w0) * p0      share gained or lost, at last week's price
--   price_effect  = q1 * (p1 - p0)           the model's own price change
--
-- The three add up exactly to the model's spend change s1 - s0, and summed over models
-- the volume effects equal (Q1 - Q0) * S0 / Q0. Models that enter carry p0 = p1 (all of
-- their spend is mix); models that exit carry q1 = 0. Only priced tokens are in the bridge,
-- so it explains the change in total implied spend exactly (unpriced tokens carry no spend).

with model_week as (

    select
        week_start,
        model_permaslug,
        min(provider) as provider,
        sum(total_tokens) as tokens,
        sum(implied_spend_usd) as spend_usd
    from {{ ref('fct_model_usage_daily') }}
    where is_priced
    group by week_start, model_permaslug

),

weeks as (

    select week_start, is_complete_week, is_spend_reliable
    from {{ ref('fct_market_weekly') }}

),

week_pairs as (

    select
        this_week.week_start,
        prior_week.week_start as prior_week_start,
        this_week.is_complete_week and prior_week.is_complete_week as is_complete_pair,
        this_week.is_spend_reliable and prior_week.is_spend_reliable as is_reliable_pair
    from weeks as this_week
    inner join weeks as prior_week
        on prior_week.week_start = cast({{ dbt.dateadd('day', -7, 'this_week.week_start') }} as date)

),

model_keys as (

    select distinct
        week_pairs.week_start,
        week_pairs.prior_week_start,
        model_week.model_permaslug,
        model_week.provider
    from week_pairs
    inner join model_week
        on model_week.week_start in (week_pairs.week_start, week_pairs.prior_week_start)

),

paired as (

    select
        model_keys.week_start,
        model_keys.prior_week_start,
        model_keys.model_permaslug,
        model_keys.provider,
        coalesce(this_week.tokens, 0) as tokens_1,
        coalesce(this_week.spend_usd, 0) as spend_1,
        coalesce(prior_week.tokens, 0) as tokens_0,
        coalesce(prior_week.spend_usd, 0) as spend_0
    from model_keys
    left join model_week as this_week
        on this_week.week_start = model_keys.week_start
        and this_week.model_permaslug = model_keys.model_permaslug
    left join model_week as prior_week
        on prior_week.week_start = model_keys.prior_week_start
        and prior_week.model_permaslug = model_keys.model_permaslug

),

priced as (

    select
        *,
        sum(tokens_1) over (partition by week_start) as market_tokens_1,
        sum(tokens_0) over (partition by week_start) as market_tokens_0,
        case
            when tokens_0 > 0 then spend_0 / tokens_0
            when tokens_1 > 0 then spend_1 / tokens_1
            else 0
        end as price_0
    from paired

),

effects as (

    select
        *,
        case when tokens_1 > 0 then spend_1 / tokens_1 else price_0 end as price_1,
        tokens_0 * 1.0 / nullif(market_tokens_0, 0) as share_0,
        tokens_1 * 1.0 / nullif(market_tokens_1, 0) as share_1
    from priced

)

select
    effects.week_start,
    effects.prior_week_start,
    effects.model_permaslug,
    effects.provider,
    week_pairs.is_complete_pair,
    week_pairs.is_reliable_pair,
    effects.tokens_0 as prior_tokens,
    effects.tokens_1 as tokens,
    effects.spend_0 as prior_spend_usd,
    effects.spend_1 as spend_usd,
    effects.spend_1 - effects.spend_0 as spend_change_usd,
    (effects.market_tokens_1 - effects.market_tokens_0) * coalesce(effects.share_0, 0)
        * effects.price_0 as volume_effect_usd,
    effects.market_tokens_1 * (coalesce(effects.share_1, 0) - coalesce(effects.share_0, 0))
        * effects.price_0 as mix_effect_usd,
    effects.tokens_1 * (effects.price_1 - effects.price_0) as price_effect_usd,
    effects.tokens_0 = 0 as is_entering,
    effects.tokens_1 = 0 as is_exiting
from effects
inner join week_pairs on week_pairs.week_start = effects.week_start
