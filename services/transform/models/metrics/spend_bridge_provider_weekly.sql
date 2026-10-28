-- The spend bridge by provider: which providers drove this week's change, and whether
-- through market growth, share gained or lost, or their own price moves.

select
    week_start,
    provider,
    is_complete_pair,
    is_reliable_pair,
    sum(prior_spend_usd) as prior_spend_usd,
    sum(spend_usd) as spend_usd,
    sum(spend_change_usd) as spend_change_usd,
    sum(volume_effect_usd) as volume_effect_usd,
    sum(mix_effect_usd) as mix_effect_usd,
    sum(price_effect_usd) as price_effect_usd
from {{ ref('fct_spend_bridge_model_weekly') }}
group by week_start, provider, is_complete_pair, is_reliable_pair
