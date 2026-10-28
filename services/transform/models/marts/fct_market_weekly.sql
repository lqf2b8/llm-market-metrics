-- One row per ISO week (Monday start): the market-level weekly headline numbers.

with daily as (

    select * from {{ ref('fct_model_usage_daily') }}

),

gaps as (

    select {{ iso_week_start('usage_date') }} as week_start, count(*) as known_gap_days
    from {{ ref('known_source_gaps') }}
    group by 1

),

weekly as (

    select
        week_start,
        count(distinct usage_date) as days_observed,
        max(usage_date) as data_through_date,
        sum(total_tokens) as total_tokens,
        sum(case when is_other_bucket then total_tokens else 0 end) as other_bucket_tokens,
        sum(case when is_zero_priced then total_tokens else 0 end) as zero_priced_tokens,
        sum(case when not is_other_bucket and not is_zero_priced then total_tokens else 0 end)
            as paid_tokens,
        sum(case when is_priced then total_tokens else 0 end) as priced_tokens,
        sum(case when is_priced and not is_zero_priced then total_tokens else 0 end)
            as priced_paid_tokens,
        sum(case when is_new_model then total_tokens else 0 end) as new_model_tokens,
        coalesce(sum(implied_spend_usd), 0) as implied_spend_usd,
        count(distinct case when first_ranked_date >= week_start then model_permaslug end)
            as models_entering_top50
    from daily
    group by week_start

)

select
    weekly.week_start,
    weekly.days_observed,
    weekly.data_through_date,
    coalesce(gaps.known_gap_days, 0) as known_gap_days,
    weekly.days_observed + coalesce(gaps.known_gap_days, 0) = 7 as is_complete_week,
    weekly.total_tokens,
    weekly.total_tokens - weekly.other_bucket_tokens as top50_tokens,
    weekly.other_bucket_tokens,
    weekly.zero_priced_tokens,
    weekly.paid_tokens,
    weekly.priced_tokens,
    weekly.implied_spend_usd,
    -- Share of identifiable (top-50) tokens whose price is known, zero prices included.
    weekly.priced_tokens * 1.0 / nullif(weekly.total_tokens - weekly.other_bucket_tokens, 0)
        as priced_coverage,
    coalesce(
        weekly.days_observed + coalesce(gaps.known_gap_days, 0) = 7
        and weekly.priced_tokens * 1.0 / nullif(weekly.total_tokens - weekly.other_bucket_tokens, 0)
            >= {{ var('spend_reliable_min_coverage') }},
        false
    ) as is_spend_reliable,
    weekly.implied_spend_usd * 1000000.0 / nullif(weekly.priced_tokens, 0)
        as effective_usd_per_mtok,
    weekly.implied_spend_usd * 1000000.0 / nullif(weekly.priced_paid_tokens, 0)
        as effective_paid_usd_per_mtok,
    weekly.zero_priced_tokens * 1.0 / nullif(weekly.total_tokens - weekly.other_bucket_tokens, 0)
        as zero_priced_share,
    weekly.other_bucket_tokens * 1.0 / nullif(weekly.total_tokens, 0) as outside_top50_share,
    weekly.new_model_tokens * 1.0 / nullif(weekly.total_tokens - weekly.other_bucket_tokens, 0)
        as new_model_share,
    weekly.models_entering_top50
from weekly
left join gaps on gaps.week_start = weekly.week_start
