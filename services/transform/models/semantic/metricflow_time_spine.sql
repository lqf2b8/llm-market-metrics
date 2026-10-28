-- One row per day, required by MetricFlow to aggregate metrics over time.

{{ dbt.date_spine(
    datepart="day",
    start_date="cast('2024-12-30' as date)",
    end_date="cast('2028-01-01' as date)"
) }}
