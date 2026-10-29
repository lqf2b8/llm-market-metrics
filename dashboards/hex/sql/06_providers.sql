-- Hex SQL cell -> dataframe `providers`
select week_start, provider, implied_spend_usd, token_share, paid_token_share, spend_share
from metrics.provider_weekly
where is_complete_week
order by week_start, provider
