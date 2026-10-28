-- The bridge must explain the spend change exactly: per model, volume + mix + price equals
-- that model's spend change; per week, the change equals the market's change in implied
-- spend. Floating-point sums allow a millionth of a dollar per million of spend.

with by_model as (

    select
        week_start,
        model_permaslug,
        spend_change_usd - (volume_effect_usd + mix_effect_usd + price_effect_usd) as gap,
        greatest(abs(spend_usd), abs(prior_spend_usd), 1) as scale
    from {{ ref('fct_spend_bridge_model_weekly') }}

),

by_week as (

    select
        bridge.week_start,
        bridge.spend_change_usd
            - (bridge.volume_effect_usd + bridge.mix_effect_usd + bridge.price_effect_usd) as gap,
        bridge.spend_usd - market.implied_spend_usd as gap_to_market,
        greatest(abs(market.implied_spend_usd), 1) as scale
    from {{ ref('spend_bridge_weekly') }} as bridge
    inner join {{ ref('fct_market_weekly') }} as market on market.week_start = bridge.week_start

)

select 'model effects do not add up' as problem, week_start, model_permaslug, gap
from by_model
where abs(gap) > 1e-6 * scale

union all

select 'week effects do not add up' as problem, week_start, cast(null as {{ dbt.type_string() }}), gap
from by_week
where abs(gap) > 1e-6 * scale

union all

select 'bridge spend differs from market spend' as problem, week_start,
    cast(null as {{ dbt.type_string() }}), gap_to_market
from by_week
where abs(gap_to_market) > 1e-6 * scale
