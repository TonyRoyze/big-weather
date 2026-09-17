-- Dense coverage grid: even wholly absent days/locations/metrics get an explicit row.
select l.location_id, d.observation_date, m.metric, m.unit, m.daily_aggregation,
       o.daily_value,
       coalesce(o.observed_hours, 0) as observed_hours,
       coalesce(o.valid_hours, 0) as valid_hours,
       coalesce(o.is_complete, false) as is_complete,
       l.name, l.country, l.region, l.latitude, l.longitude, l.elevation_m, l.elevation_band,
       year(d.observation_date) as calendar_year,
       case when month(d.observation_date) in (12,1,2) then 'DJF'
            when month(d.observation_date) in (3,4,5) then 'MAM'
            when month(d.observation_date) in (6,7,8) then 'JJA' else 'SON' end as season,
       year(d.observation_date) + iff(month(d.observation_date) = 12, 1, 0) as season_year
from {{ ref('dim_locations') }} l
cross join {{ ref('int_dates') }} d
cross join {{ ref('weather_metrics') }} m
left join {{ ref('int_daily_observations') }} o
  on l.location_id = o.location_id and d.observation_date = o.observation_date and m.metric = o.metric
