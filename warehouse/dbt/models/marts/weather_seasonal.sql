with grouped as (
  select location_id, metric, unit, season, season_year,
         count(*) as requested_days, count(daily_value) as complete_days,
         avg(daily_value) as available_day_mean,
         case when metric = 'precipitation' then sum(daily_value) end as available_precipitation_mm
  from {{ ref('fct_daily_weather') }}
  group by location_id, metric, unit, season, season_year
), boundaries as (
  select *, case season
    when 'DJF' then date_from_parts(season_year-1,12,1)
    when 'MAM' then date_from_parts(season_year,3,1)
    when 'JJA' then date_from_parts(season_year,6,1)
    else date_from_parts(season_year,9,1) end as season_start
  from grouped
)
select *, datediff(day, season_start, dateadd(month,3,season_start)) as calendar_days,
       complete_days = datediff(day, season_start, dateadd(month,3,season_start)) as is_complete_season
from boundaries
