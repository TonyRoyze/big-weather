with grouped as (
    select location_id, observation_date, metric,
           count(*) as observed_hours,
           count(distinct observed_at) as distinct_hours,
           count(hourly_value) as valid_hours,
           case when metric = 'precipitation' then sum(hourly_value)
                else avg(hourly_value) end as candidate_value
    from {{ ref('int_weather_values') }}
    group by location_id, observation_date, metric
)
select location_id, observation_date, metric, observed_hours, valid_hours,
       observed_hours = 24 and distinct_hours = 24 and valid_hours = 24 as is_complete,
       case when observed_hours = 24 and distinct_hours = 24 and valid_hours = 24
            then candidate_value end as daily_value
from grouped
