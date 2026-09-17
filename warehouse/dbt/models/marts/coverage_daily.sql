select location_id, observation_date, metric, observed_hours, valid_hours,
       24 - valid_hours as missing_hours, is_complete,
       case when observed_hours = 0 then 'missing'
            when is_complete then 'complete' else 'partial' end as coverage_status
from {{ ref('fct_daily_weather') }}
