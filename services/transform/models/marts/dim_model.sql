-- One row per model variant that has ever ranked in the daily top 50.
-- first_ranked_date is when the model entered the top 50, not its launch date: models
-- can launch and stay below the top 50, and data starts 2025-01-01.

with usage as (

    select * from {{ ref('int_usage_priced') }}
    where not is_other_bucket

),

latest_listing as (

    select price_key, model_name, model_created_at
    from {{ ref('stg_openrouter__models') }}
    where true
    qualify row_number() over (partition by price_key order by snapshot_date desc) = 1

),

ranked as (

    select
        model_permaslug,
        min(provider) as provider,
        min(base_slug) as base_slug,
        min(variant) as variant,
        min(usage_date) as first_ranked_date,
        max(usage_date) as last_ranked_date,
        count(*) as days_ranked,
        sum(total_tokens) as lifetime_tokens
    from usage
    group by model_permaslug

),

latest_basis as (

    select model_permaslug, pricing_basis as latest_pricing_basis
    from usage
    where true
    qualify row_number() over (partition by model_permaslug order by usage_date desc) = 1

)

select
    ranked.*,
    coalesce(ranked.variant = 'free', false) as is_free_variant,
    latest_listing.model_name,
    latest_listing.model_created_at,
    latest_listing.price_key is not null as is_currently_listed,
    latest_basis.latest_pricing_basis
from ranked
left join latest_listing on latest_listing.price_key = ranked.model_permaslug
left join latest_basis on latest_basis.model_permaslug = ranked.model_permaslug
