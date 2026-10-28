-- One row per (snapshot_date, model_id): a model's list price on the day it was observed.
-- price_key rebuilds the ranking permaslug format (canonical slug + ':variant'), which is
-- the exact join key to stg_openrouter__rankings_daily.

with source as (

    select * from {{ source('openrouter', 'openrouter_models_snapshot') }}

),

deduplicated as (

    select *
    from source
    where true
    qualify row_number() over (
        partition by snapshot_date, model_id
        order by ingested_at desc
    ) = 1

),

renamed as (

    select
        cast(snapshot_date as date) as snapshot_date,
        model_id,
        canonical_slug,
        {{ after_delimiter('model_id', ':') }} as variant,
        coalesce(canonical_slug, {{ dbt.split_part('model_id', "':'", 1) }}) as base_slug,
        name as model_name,
        {{ from_unix_seconds('created_unix') }} as model_created_at,
        context_length,
        -- USD per million tokens; null when the API reports -1 (router, price varies).
        {{ usd_per_mtok('prompt_price_usd_per_token') }} as prompt_usd_per_mtok,
        {{ usd_per_mtok('completion_price_usd_per_token') }} as completion_usd_per_mtok,
        ingested_at
    from deduplicated

)

select
    *,
    base_slug || coalesce(':' || variant, '') as price_key
from renamed
