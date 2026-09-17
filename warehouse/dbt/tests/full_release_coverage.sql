-- Opt-in publication gate; a partial backfill is expected during normal builds.
{{ config(enabled=var('require_complete_coverage', false)) }}
select location_id, observation_date, metric
from {{ ref('coverage_daily') }}
where not is_complete
