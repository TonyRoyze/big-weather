select location_id, observed_at
from {{ ref('stg_weather_hourly') }}
where observed_at <> date_trunc('hour', observed_at)
   or (temperature_2m is not null and not temperature_2m between -100 and 70)
   or (relative_humidity_2m is not null and not relative_humidity_2m between 0 and 100)
   or precipitation < 0 or wind_speed_10m < 0
