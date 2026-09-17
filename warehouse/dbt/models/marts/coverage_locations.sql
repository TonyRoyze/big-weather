-- These min/max dates are NOT a guarantee of uninterrupted coverage; use coverage_daily for requests.
select location_id, metric, count(*) as expected_days,
       count_if(is_complete) as complete_days,
       sum(valid_hours) as valid_hours,
       min(iff(is_complete, observation_date, null)) as first_complete_date,
       max(iff(is_complete, observation_date, null)) as last_complete_date
from {{ ref('fct_daily_weather') }}
group by location_id, metric
