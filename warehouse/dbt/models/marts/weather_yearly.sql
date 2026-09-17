with annual as (
  select location_id, metric, unit, calendar_year,
         count(*) as requested_days, count(daily_value) as complete_days,
         datediff(day, date_from_parts(calendar_year,1,1), date_from_parts(calendar_year+1,1,1)) as calendar_days,
         avg(daily_value) as available_day_mean,
         case when metric = 'precipitation' then sum(daily_value) end as available_precipitation_mm
  from {{ ref('fct_daily_weather') }}
  group by location_id, metric, unit, calendar_year
), complete as (
  select *, complete_days = calendar_days as is_complete_year,
         case when complete_days = calendar_days then available_day_mean end as annual_mean
  from annual
)
select c.*, case when c.calendar_year = p.calendar_year + 1
                      and c.is_complete_year and p.is_complete_year
                 then c.annual_mean - p.annual_mean end as year_over_year_change
from complete c left join complete p
  on c.location_id = p.location_id and c.metric = p.metric and c.calendar_year = p.calendar_year + 1
