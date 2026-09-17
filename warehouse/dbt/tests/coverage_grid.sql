select count(*) as actual_rows
from {{ ref('fct_daily_weather') }}
having count(*) <> (
  (select count(*) from {{ ref('dim_locations') }}) *
  (select count(*) from {{ ref('int_dates') }}) *
  (select count(*) from {{ ref('weather_metrics') }})
)
