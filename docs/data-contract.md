# Data and analysis contract

## Storage

```text
data/raw/locations/locations.parquet
data/raw/weather/location_id=<id>/year=<yyyy>/weather.parquet
data/processed/{enriched_weather,daily_metrics,summaries,yearly_metrics,lapse_rates}/
data/processed/pipeline_metrics.json
data/platform/active.json
data/platform/releases/<version>/{locations,enriched_weather,daily_metrics,summaries,yearly_metrics,lapse_rates}/
data/platform/releases/<version>/manifest.json
data/platform/jobs.sqlite
data/platform/jobs/<job_id>/{request.json,metadata.json,worker.log,worker_metrics.json,result.parquet/}
data/platform/evidence/<version>/{*.parquet,metadata.json,findings.md}
```

Cached requests live separately in `data/cache`. Publication copies completed
Parquet outputs into a staging directory, checks required columns and unique keys,
hashes files, renames the release and atomically switches the active pointer. A
failed validation leaves the previous release active. Published files are immutable
by convention and protected against replacement by the publisher; do not edit them
manually. Readers keep a single version for each page or job.

## Table meanings

| Table | Grain / key | Fields used by the team |
| --- | --- | --- |
| locations | One row per `location_id` | `name`, `country`, `region`, `latitude`, `longitude`, `elevation_m` |
| enriched_weather | `location_id`, `timestamp` | Hourly temperature, precipitation, wind and humidity; location metadata; `date`, `year`, `season`, `elevation_band` |
| daily_metrics | `location_id`, `date` | Daily mean temperature/wind, daily precipitation total, rolling 30-calendar-day temperature mean, `observed_hours` (new processing runs) |
| summaries | `elevation_band`, `region`, `season`, `year` | Pooled hourly means; pooled precipitation sum; `observation_count` |
| yearly_metrics | `location_id`, `year` | Annual hourly temperature mean and difference from preceding available annual row |
| lapse_rates | `season` | Signed OLS slope in °C/m and °C/km, intercept, R², RMSE, daily sample size |

UTC is used throughout. Some Spark Parquet timestamp encodings load into pandas
without timezone metadata; interpret them as UTC. Ingestion writes microsecond
Parquet timestamps for Spark compatibility. Units: °C, precipitation mm per hourly
interval (mm after summing), wind m/s, relative humidity %, elevation m.

Elevation bands: lowland <200 m, midland 200–<1000 m, highland 1000–<3000 m,
alpine ≥3000 m. Seasons are `winter`, `spring`, `summer`, `autumn`; December–February
is northern winter and southern summer. They are not calendar-quarter codes or a
claim that tropical climates have temperate seasonality.

## Quality and denominators

Scala filters missing identifiers/timestamps and missing or invalid required weather
values, rejects non-finite precipitation/wind and drops duplicate hourly keys. It
joins locations, records counts before/after validation and joining, and reports
actual input/shuffle partitions. Rejection counts combine invalid rows and duplicates;
they are not a per-reason audit. Publication records per-location hourly coverage
against the global observed study window; inspect gaps before making comparisons.
A complete 2019–2024 release has 52,608 hours per location and 1,893,888 total hours.

Daily means use retained hours. `observed_hours < 24` signals incomplete daily
coverage; neither daily totals nor window calculations impute missing observations.
Rolling means average available daily means over the preceding 29 calendar days
plus the current day. The first windows contain fewer than 30 days. Year-over-year
output currently uses the preceding *available* annual row; check that years are
consecutive before describing it as a one-year change.

Never compare the `summaries.total_precipitation_mm` field as a typical site's
rainfall across bands: it sums across different numbers of locations and hours.
The evidence module first computes location means, then equal-weight band means.
Its rainfall comparison is **mean daily precipitation in mm/day**. Record the number
of locations and retained days alongside every comparison.

The lapse-rate model pools repeated daily observations; R² and slope are descriptive.
There are no independent-sample confidence intervals, latitude controls or causal
identification. The six-year study period is too short to establish a long-term
climate trend. Annual anomalies use each location's observed study-period annual
mean as baseline, not a standard 30-year climate normal.

## Custom job JSON

Only `enriched_weather` is currently exposed. Group/filter fields:
`location_id`, `elevation_band`, `season`, `year`, `region`. Filters additionally
support `date: ["YYYY-MM-DD", "YYYY-MM-DD"]` as an inclusive interval. Year lists
are enumerations: `[2020, 2024]` means only those two years. Omit filters to select
all; explicit empty lists are rejected. Unknown location IDs produce an empty result.

Metrics: `temperature_2m`, `precipitation`, `wind_speed_10m`,
`relative_humidity_2m`. Operations: `count`, `sum`, `avg`, `min`, `max`.
The validator accepts only these names and never executes submitted SQL/Python.
Result columns are `<metric>_<operation>`, with group columns sorted canonically;
results load sorted by grouping keys. User-selected result columns and arbitrary
sorting are future additions. Count is the number of non-null values in that metric.

Example: [seasonal-temperature.json](../examples/jobs/seasonal-temperature.json).
PySpark is pinned to the Scala job's Spark 4.0.1 runtime. Official installation
reference: https://spark.apache.org/docs/4.0.1/api/python/getting_started/install.html.
