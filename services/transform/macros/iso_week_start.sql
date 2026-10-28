{#
  Monday of the ISO week containing a date. dbt.date_trunc('week', ...) is not portable:
  BigQuery weeks start on Sunday, DuckDB weeks on Monday.
#}
{% macro iso_week_start(column) -%}
    {{ return(adapter.dispatch('iso_week_start')(column)) }}
{%- endmacro %}

{% macro default__iso_week_start(column) -%}
    cast(date_trunc('week', {{ column }}) as date)
{%- endmacro %}

{% macro bigquery__iso_week_start(column) -%}
    date_trunc({{ column }}, isoweek)
{%- endmacro %}
