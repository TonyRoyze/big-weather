select location_id, name, country, region, latitude, longitude, elevation_m,
    case when elevation_m < 200 then 'lowland'
         when elevation_m < 1000 then 'midland'
         when elevation_m < 3000 then 'highland' else 'alpine' end as elevation_band
from {{ source('weather_raw', 'locations') }}
