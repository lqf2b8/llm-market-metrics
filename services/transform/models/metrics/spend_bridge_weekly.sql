-- Why implied spend moved this week: the price-volume-mix bridge at market level.
-- volume + mix + price = spend change, exactly (tested in assert_spend_bridge_adds_up).

select
    week_start,
    prior_week_start,
    is_complete_pair,
    is_reliable_pair,
    sum(prior_spend_usd) as prior_spend_usd,
    sum(spend_usd) as spend_usd,
    sum(spend_change_usd) as spend_change_usd,
    sum(volume_effect_usd) as volume_effect_usd,
    sum(mix_effect_usd) as mix_effect_usd,
    sum(price_effect_usd) as price_effect_usd,
    sum(prior_tokens) as prior_priced_tokens,
    sum(tokens) as priced_tokens,
    sum(case when is_entering then 1 else 0 end) as models_entering,
    sum(case when is_exiting then 1 else 0 end) as models_exiting
from {{ ref('fct_spend_bridge_model_weekly') }}
group by week_start, prior_week_start, is_complete_pair, is_reliable_pair
