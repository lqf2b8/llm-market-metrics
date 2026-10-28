-- The source returns exactly 51 rows a day (top 50 + "other") with no gaps except the
-- dates listed in known_source_gaps. Returns one row per violation.

with days as (

    select
        usage_date,
        count(*) as row_count,
        sum(case when is_other_bucket then 1 else 0 end) as other_rows
    from {{ ref('stg_openrouter__rankings_daily') }}
    group by usage_date

),

bounds as (

    select min(usage_date) as first_day, max(usage_date) as last_day, count(*) as observed_days
    from days

),

gaps_in_range as (

    select count(*) as gap_days
    from {{ ref('known_source_gaps') }} as gaps
    cross join bounds
    where gaps.usage_date between bounds.first_day and bounds.last_day

),

coverage as (

    select
        {{ dbt.datediff('first_day', 'last_day', 'day') }} + 1 as expected_days,
        observed_days,
        gap_days
    from bounds
    cross join gaps_in_range

)

select
    'missing or unexpected days' as problem,
    cast(null as date) as usage_date,
    expected_days - gap_days - observed_days as amount
from coverage
where expected_days - gap_days != observed_days

union all

select
    'wrong row count' as problem,
    usage_date,
    row_count as amount
from days
where row_count != {{ var('rankings_rows_per_day') }}

union all

select
    'other bucket missing or repeated' as problem,
    usage_date,
    other_rows as amount
from days
where other_rows != 1
