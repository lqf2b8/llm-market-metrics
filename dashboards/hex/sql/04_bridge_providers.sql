-- Hex SQL cell -> dataframe `bridge_providers`: who drove the latest week's change
select provider, spend_change_usd, volume_effect_usd, mix_effect_usd, price_effect_usd
from metrics.spend_bridge_provider_weekly
where week_start = (select max(week_start) from metrics.weekly_kpis where is_complete_week)
order by abs(spend_change_usd) desc
