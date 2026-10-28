-- Provider driver view beneath the headline KPIs: each provider's share of tokens and of
-- implied spend, and its week-over-week change. Shares are the governed metrics (tokens,
-- paid_tokens, implied_spend_usd) for the provider divided by the same metric for the market.

select
    week_start,
    provider,
    is_complete_week,
    models_ranked,
    total_tokens as tokens,
    paid_tokens,
    implied_spend_usd,
    token_share,
    paid_token_share,
    spend_share,
    spend_minus_paid_token_share,
    tokens_wow_change,
    spend_wow_change
from {{ ref('fct_provider_weekly') }}
