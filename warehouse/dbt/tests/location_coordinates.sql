select location_id from {{ ref('dim_locations') }}
where latitude not between -90 and 90 or longitude not between -180 and 180
