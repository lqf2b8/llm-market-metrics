-- One row per (usage_date, model_permaslug): tokens, implied spend, rank and share.
-- The "other" row (models outside the day's top 50) is kept so totals stay complete.

with usage as (

    select * from {{ ref('int_usage_priced') }}

),

models as (

    select model_permaslug, first_ranked_date from {{ ref('dim_model') }}

),

data_start as (

    -- Models already ranked on the first day of data have an unknown entry date.
    select min(usage_date) as first_data_date from usage

)

select
    usage.usage_date,
    {{ iso_week_start('usage.usage_date') }} as week_start,
    usage.model_permaslug,
    coalesce(usage.provider, 'other') as provider,
    usage.base_slug,
    usage.variant,
    usage.is_other_bucket,
    usage.is_free_variant,
    usage.is_stealth_preview,
    usage.pricing_basis,
    usage.is_priced,
    usage.is_zero_priced,
    usage.total_tokens,
    usage.blended_usd_per_mtok,
    usage.implied_spend_usd,
    usage.total_tokens * 1.0 / sum(usage.total_tokens) over (partition by usage.usage_date)
        as token_share_of_day,
    case
        when not usage.is_other_bucket
            then rank() over (
                partition by usage.usage_date, usage.is_other_bucket
                order by usage.total_tokens desc
            )
    end as daily_rank,
    models.first_ranked_date,
    coalesce(
        models.first_ranked_date > data_start.first_data_date
        and {{ dbt.datediff('models.first_ranked_date', 'usage.usage_date', 'day') }}
            < {{ var('new_model_window_days') }},
        false
    ) as is_new_model
from usage
cross join data_start
left join models on models.model_permaslug = usage.model_permaslug
