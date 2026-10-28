{# Small portability helpers so the same models run on DuckDB (local, CI) and BigQuery. #}

{% macro from_unix_seconds(column) -%}
    {{ return(adapter.dispatch('from_unix_seconds')(column)) }}
{%- endmacro %}

{% macro default__from_unix_seconds(column) -%}
    to_timestamp({{ column }})
{%- endmacro %}

{% macro bigquery__from_unix_seconds(column) -%}
    timestamp_seconds({{ column }})
{%- endmacro %}


{# Text after the first occurrence of a delimiter, or null when the delimiter is absent. #}
{% macro after_delimiter(column, delimiter) -%}
    nullif({{ dbt.split_part(column, "'" ~ delimiter ~ "'", 2) }}, '')
{%- endmacro %}


{# Price in USD per token (string from the API) to USD per million tokens. Negative = variable. #}
{% macro usd_per_mtok(column) -%}
    case
        when cast({{ column }} as {{ dbt.type_float() }}) < 0 then null
        else cast({{ column }} as {{ dbt.type_float() }}) * 1000000
    end
{%- endmacro %}
