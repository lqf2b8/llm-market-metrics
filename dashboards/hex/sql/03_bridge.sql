-- Hex SQL cell -> dataframe `bridge`: the latest complete week's spend bridge
select *
from metrics.spend_bridge_weekly
where week_start = (select max(week_start) from metrics.weekly_kpis where is_complete_week)
