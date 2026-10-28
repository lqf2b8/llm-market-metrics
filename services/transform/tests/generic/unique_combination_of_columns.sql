{% test unique_combination_of_columns(model, combination_of_columns) %}
{#- Fails with one row per key that appears more than once. -#}
select
    {{ combination_of_columns | join(', ') }},
    count(*) as occurrences
from {{ model }}
group by {{ combination_of_columns | join(', ') }}
having count(*) > 1
{% endtest %}
