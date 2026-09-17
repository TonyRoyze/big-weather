select location_id, observation_date, metric
from {{ ref('fct_daily_weather') }}
where observed_hours not between 0 and 24 or valid_hours not between 0 and observed_hours
   or is_complete <> (observed_hours = 24 and valid_hours = 24)
   or (is_complete and daily_value is null)
   or (not is_complete and daily_value is not null)
