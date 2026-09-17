{% set start = var('coverage_start') %}
{% set end = var('coverage_end') %}
{% set days = (modules.datetime.date.fromisoformat(end) - modules.datetime.date.fromisoformat(start)).days + 1 %}
{% if days < 1 or days > 36600 %}
  {{ exceptions.raise_compiler_error('Coverage must contain 1–36600 days.') }}
{% endif %}
select dateadd(day, row_number() over(order by seq4()) - 1,
               to_date('{{ start }}'))::date as observation_date
from table(generator(rowcount => {{ days }}))
