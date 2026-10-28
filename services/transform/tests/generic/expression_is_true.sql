{% test expression_is_true(model, expression, column_name=none) %}
{#- Fails with every row for which the expression is not true (null counts as a failure).
    Filter rows with the standard `config: where:` on the test. -#}
select *
from {{ model }}
where not coalesce({{ expression }}, false)
{% endtest %}
