-- One row per (usage_date, model_permaslug): each day's tokens with the list price in
-- effect that day and the basis that price came from. Pricing order:
--   1. other_bucket       the aggregate of models outside the top 50: no single price
--   2. free_variant       ':free' variants, priced at zero
--   3. stealth_preview    unannounced preview models served free, priced at zero
--   4. listed             the model list's price on that date (point-in-time join)
--   5. listed_backfilled  dated before our first snapshot: earliest price observed
--   6. retired_list_price models no longer listed, from the sourced seed
--   7. unpriced           none of the above; excluded from spend, counted in coverage

with usage as (

    select * from {{ ref('stg_openrouter__rankings_daily') }}

),

listed_prices as (

    select * from {{ ref('int_model_prices_history') }}

),

retired_prices as (

    select * from {{ ref('retired_model_prices') }}

),

joined as (

    select
        usage.*,
        listed.prompt_usd_per_mtok as listed_prompt_usd_per_mtok,
        listed.completion_usd_per_mtok as listed_completion_usd_per_mtok,
        listed.valid_from as listed_valid_from,
        retired.prompt_usd_per_mtok as retired_prompt_usd_per_mtok,
        retired.completion_usd_per_mtok as retired_completion_usd_per_mtok
    from usage
    left join listed_prices as listed
        on listed.price_key = usage.model_permaslug
        and (
            (
                usage.usage_date >= listed.valid_from
                and (listed.valid_to is null or usage.usage_date < listed.valid_to)
            )
            or (listed.is_first_window and usage.usage_date < listed.valid_from)
        )
    left join retired_prices as retired
        on retired.price_key = usage.model_permaslug

),

based as (

    select
        *,
        case
            when is_other_bucket then 'other_bucket'
            when is_free_variant then 'free_variant'
            when is_stealth_preview then 'stealth_preview'
            when listed_prompt_usd_per_mtok is not null
                and listed_completion_usd_per_mtok is not null
                and usage_date >= listed_valid_from
                then 'listed'
            when listed_prompt_usd_per_mtok is not null
                and listed_completion_usd_per_mtok is not null
                then 'listed_backfilled'
            when retired_prompt_usd_per_mtok is not null then 'retired_list_price'
            else 'unpriced'
        end as pricing_basis
    from joined

),

priced as (

    select
        *,
        case
            when pricing_basis in ('free_variant', 'stealth_preview') then 0
            when pricing_basis in ('listed', 'listed_backfilled') then listed_prompt_usd_per_mtok
            when pricing_basis = 'retired_list_price' then retired_prompt_usd_per_mtok
        end as prompt_usd_per_mtok,
        case
            when pricing_basis in ('free_variant', 'stealth_preview') then 0
            when pricing_basis in ('listed', 'listed_backfilled')
                then listed_completion_usd_per_mtok
            when pricing_basis = 'retired_list_price' then retired_completion_usd_per_mtok
        end as completion_usd_per_mtok
    from based

)

select
    usage_date,
    model_permaslug,
    provider,
    base_slug,
    variant,
    is_other_bucket,
    is_free_variant,
    is_stealth_preview,
    total_tokens,
    pricing_basis,
    pricing_basis not in ('other_bucket', 'unpriced') as is_priced,
    pricing_basis in ('free_variant', 'stealth_preview') as is_zero_priced,
    prompt_usd_per_mtok,
    completion_usd_per_mtok,
    -- The prompt/completion split is not published; one stated blend applies to every model.
    {{ var('prompt_token_share') }} * prompt_usd_per_mtok
    + (1 - {{ var('prompt_token_share') }}) * completion_usd_per_mtok as blended_usd_per_mtok,
    total_tokens / 1000000.0 * (
        {{ var('prompt_token_share') }} * prompt_usd_per_mtok
        + (1 - {{ var('prompt_token_share') }}) * completion_usd_per_mtok
    ) as implied_spend_usd,
    source_as_of
from priced
