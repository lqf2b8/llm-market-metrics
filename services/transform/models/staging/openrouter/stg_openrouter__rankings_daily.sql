-- One row per (usage_date, model_permaslug): daily tokens for the top 50 models plus
-- the "other" bucket. Splits the permaslug into provider / base slug / variant and flags
-- the two kinds of traffic that are priced at zero: free variants and stealth previews.

with source as (

    select * from {{ source('openrouter', 'openrouter_rankings_daily') }}

),

deduplicated as (

    -- Ingest is idempotent per date, but keep the latest load defensively.
    select *
    from source
    where true
    qualify row_number() over (
        partition by date, model_permaslug
        order by ingested_at desc
    ) = 1

),

renamed as (

    select
        cast(date as date) as usage_date,
        model_permaslug,
        model_permaslug = 'other' as is_other_bucket,
        case
            when model_permaslug != 'other'
                then {{ dbt.split_part('model_permaslug', "'/'", 1) }}
        end as provider,
        {{ dbt.split_part('model_permaslug', "':'", 1) }} as base_slug,
        {{ after_delimiter('model_permaslug', ':') }} as variant,
        cast(total_tokens as {{ dbt.type_bigint() }}) as total_tokens,
        source_as_of,
        source_version,
        ingested_at
    from deduplicated

)

select
    *,
    coalesce(variant = 'free', false) as is_free_variant,
    -- Unannounced models OpenRouter serves free for a short preview window.
    coalesce(
        provider = 'stealth'
        or (provider = 'openrouter' and (base_slug like '%-alpha' or base_slug like '%-beta')),
        false
    ) as is_stealth_preview
from renamed
