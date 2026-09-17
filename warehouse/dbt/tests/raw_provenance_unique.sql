-- A loader retry must not append the same file row twice.
select source_file, source_checksum, source_row_number, count(*) as row_count
from {{ source('weather_raw', 'weather_hourly') }}
group by source_file, source_checksum, source_row_number
having count(*) > 1
