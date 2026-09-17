-- Equal weight per location, within country and day. Descriptive association only.
select country, observation_date, count(*) as sample_size,
       regr_slope(daily_value, elevation_m) * 1000 as temperature_slope_c_per_km,
       regr_r2(daily_value, elevation_m) as r_squared,
       min(elevation_m) as min_elevation_m, max(elevation_m) as max_elevation_m
from {{ ref('fct_daily_weather') }}
where metric = 'temperature_2m' and is_complete and elevation_m is not null
group by country, observation_date
having count(*) >= 3 and count(distinct elevation_m) >= 2
