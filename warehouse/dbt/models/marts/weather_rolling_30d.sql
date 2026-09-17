with rolling as (
  select location_id, observation_date, metric, unit,
         count(*) over (partition by location_id, metric order by observation_date rows between 29 preceding and current row) as window_days,
         count(daily_value) over (partition by location_id, metric order by observation_date rows between 29 preceding and current row) as complete_days,
         avg(daily_value) over (partition by location_id, metric order by observation_date rows between 29 preceding and current row) as available_day_mean,
         sum(daily_value) over (partition by location_id, metric order by observation_date rows between 29 preceding and current row) as available_day_sum
  from {{ ref('fct_daily_weather') }}
)
select *, case when window_days = 30 and complete_days = 30 then available_day_mean end as complete_30d_mean,
       case when metric = 'precipitation' and window_days = 30 and complete_days = 30
            then available_day_sum end as complete_30d_precipitation_mm
from rolling
