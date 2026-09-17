-- Long form for only continuous features with agreed daily semantics.
select location_id, observed_at, cast(observed_at as date) as observation_date,
       lower(metric) as metric, hourly_value
from {{ ref('stg_weather_hourly') }}
unpivot include nulls (hourly_value for metric in (
  temperature_2m, precipitation, relative_humidity_2m, wind_speed_10m,
  apparent_temperature, dew_point_2m, cloud_cover, surface_pressure,
  soil_temperature_0_to_7cm, soil_moisture_0_to_7cm,
  shortwave_radiation, snow_depth
))
