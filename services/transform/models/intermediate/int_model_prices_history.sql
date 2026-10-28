-- Type-2 price history: one row per price_key per period with an unchanged list price.
--
-- Built from the raw daily snapshots rather than with a dbt snapshot: raw already keeps
-- every day's prices, so this model can be rebuilt from scratch at any time and gives the
-- same answer. A dbt snapshot would be a second, non-reproducible copy of the same facts.
--
-- valid_to is exclusive and null for the current price. is_first_window marks the earliest
-- price seen for a key; usage before valid_from may borrow it, flagged as a backfill.

with snapshots as (

    select
        price_key,
        snapshot_date,
        prompt_usd_per_mtok,
        completion_usd_per_mtok
    from {{ ref('stg_openrouter__models') }}

),

flagged as (

    select
        *,
        case
            when lag(snapshot_date) over by_key is null then 1
            when prompt_usd_per_mtok is distinct from lag(prompt_usd_per_mtok) over by_key then 1
            when completion_usd_per_mtok is distinct from lag(completion_usd_per_mtok) over by_key
                then 1
            else 0
        end as starts_new_window
    from snapshots
    window by_key as (partition by price_key order by snapshot_date)

),

numbered as (

    select
        *,
        sum(starts_new_window) over (
            partition by price_key
            order by snapshot_date
            rows between unbounded preceding and current row
        ) as window_number
    from flagged

),

collapsed as (

    -- Prices are constant within a window, so max() just picks the shared value.
    select
        price_key,
        window_number,
        min(snapshot_date) as valid_from,
        max(snapshot_date) as last_observed_date,
        count(*) as snapshot_days,
        max(prompt_usd_per_mtok) as prompt_usd_per_mtok,
        max(completion_usd_per_mtok) as completion_usd_per_mtok
    from numbered
    group by price_key, window_number

)

select
    price_key,
    valid_from,
    lead(valid_from) over (partition by price_key order by valid_from) as valid_to,
    last_observed_date,
    snapshot_days,
    prompt_usd_per_mtok,
    completion_usd_per_mtok,
    window_number = 1 as is_first_window,
    lead(valid_from) over (partition by price_key order by valid_from) is null as is_current
from collapsed
