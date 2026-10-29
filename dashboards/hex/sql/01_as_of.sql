-- Hex SQL cell -> dataframe `as_of`
select
    max(data_through_date) as data_through_date,
    max(case when is_complete_week then week_start end) as latest_week
from metrics.weekly_kpis
