# Big Weather — Snowflake/dbt implementation package

These models are prepared for the warehouse implementation. They do not connect the
current dashboard to Snowflake, upload local Parquet, or implement the download queue.

## Responsibilities

- **Snowflake** stores RAW observations and executes SQL.
- **dbt** builds and tests the transformation graph.
- **MART** contains queryable data products, not a separate database service.
- The ingestion service remains responsible for API requests, quotas, file commits,
  checksums and loading RAW. FastAPI remains responsible for requests and UI suggestions.

## Install and configure

Use a separate environment so warehouse dependencies do not change the local app:

```bash
cd warehouse/dbt
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export SNOWFLAKE_ACCOUNT='your-org-your-account'
export SNOWFLAKE_USER='your-user'
export SNOWFLAKE_DATABASE='BIG_WEATHER_DEV'
export SNOWFLAKE_RAW_DATABASE='BIG_WEATHER_DEV'
export SNOWFLAKE_WAREHOUSE='WEATHER_TRANSFORM_WH'
export SNOWFLAKE_ROLE='WEATHER_TRANSFORMER'
export DBT_SCHEMA='WEATHER_DEV'
.venv/bin/dbt debug --profiles-dir .
```

The checked-in profile uses interactive browser authentication and contains no secrets.
For unattended deployment, create a separately managed profile with your organization's
key-pair/OAuth configuration. Do not put credentials in git. Placeholder `offline`
account/user values permit **parse only**; they are not working login credentials.
The role needs source SELECT privileges and permission to create models in the chosen
database. Provision roles/warehouses and ingestion privileges separately.

Default dbt schema naming is deliberately retained: a base `WEATHER_DEV` schema produces
`WEATHER_DEV_STAGING`, `WEATHER_DEV_INTERMEDIATE` and `WEATHER_DEV_MART`. Set a different
base schema/database for each environment. RAW is configured independently.

## Source loading contract

Run `setup/raw_tables.sql` in the selected RAW database, then implement the loader:

1. Load the verified location catalogue (including DEM elevation) into `RAW.LOCATIONS`,
   keeping exactly one row per location. The configuration CSV alone has no verified DEM lookup.
2. Load only committed, checksum-verified weather files into `RAW.WEATHER_HOURLY`.
3. Map Parquet `timestamp` to `observed_at` as **UTC TIMESTAMP_NTZ**. Preserve all 47
   float fields. Convert NaN/infinity and source missing values to SQL NULL before loading.
4. Supply warehouse `loaded_at` (UTC), immutable `source_file`, `source_row_number`
   (unique within that file) and `source_checksum`. Do not substitute observation time
   for load time. Retries must not append an identical file row again.
5. Corrected source files must receive a new file identity/checksum and a later load time.
   Do not mutate the old rows in place. Serialize loads/builds or use a fixed RAW snapshot
   so one dbt build sees consistent input across models.

The staging model deterministically selects the newest loaded revision per location-hour.
All fields remain available in `stg_weather_hourly`; daily marts currently expose the same
12 continuous features as the React map. The metric seed records their units/aggregation.
Categorical fields and directions are retained hourly but intentionally excluded from means.
Add any additional daily feature to both the seed and UNPIVOT list with agreed semantics.

## Build and publish

```bash
.venv/bin/dbt seed --profiles-dir .
.venv/bin/dbt build --profiles-dir . --vars '{coverage_start: "2020-01-01", coverage_end: "2026-08-31"}'
.venv/bin/dbt docs generate --profiles-dir .
```

Dates must match the study plan and are inclusive. The default end is pinned, not today.
Build into an inactive environment/release schema. On successful tests and reconciliation,
explicitly switch the API's serving views/configuration. A dbt build is not an atomic
multi-model release; never point users at half-built models. Current FastAPI still reads
local files and requires a Snowflake adapter before that switch.

For a release that promises complete coverage for **every supported daily metric**:

```bash
.venv/bin/dbt build --profiles-dir . --vars '{require_complete_coverage: true}'
```

This optional gate will fail on missing source variables/days. Normal development builds
allow partial coverage and report it explicitly. Do not enable the gate on a partial
backfill unless failure is intended.

## Model contracts

| Model | Grain / use |
|---|---|
| `stg_weather_hourly` | Unique location + UTC hour; all 47 fields and winning provenance |
| `dim_locations` | One location; coordinates, elevation, country and band |
| `fct_daily_weather` | Location + day + metric, including wholly absent days |
| `coverage_daily` | Exact completeness and missing-hour counts for selection checks |
| `coverage_locations` | Coverage overview; earliest/latest dates do **not** imply continuous coverage |
| `weather_rolling_30d` | Daily 30-calendar-day statistics and complete-window result |
| `weather_yearly` | Location + metric + year; complete-year flag and comparable annual change |
| `weather_seasonal` | Location + metric + DJF/MAM/JJA/SON + season year |
| `elevation_temperature` | Country + day; descriptive temperature/elevation slope and sample size |

Daily values require 24 distinct timestamps and 24 non-null values. Precipitation is
summed, other included metrics averaged. Missing observations are not zero. Period
statistics explicitly label available-day means and precipitation totals; partial totals
are not whole-period totals. Leap years use actual calendar lengths. December belongs
to the following DJF season year; these are calendar seasons, not monsoon labels.
Year-over-year change is emitted only for consecutive, fully complete calendar years.
Rolling windows include missing days through the dense date grid; a complete 30-day result
requires all 30 days. Cross-location comparisons should carry coverage counts and units.

## Backfills and corrections

The hourly model uses MERGE keyed by location/hour, scanning the entire RAW history.
It intentionally does **not** filter on maximum observation time: your backwards-in-time
backfill and late corrections would otherwise be lost. Downstream table marts rebuild
from that deduplicated source, so historical changes update rolling and period summaries.
This favors correctness over minimum scan cost for the first implementation.

At larger scale, replace the full source scan only after adding a durable, monotonically
committed load cursor, and recompute every affected day, season, year and subsequent
29-day rolling window. A lookback on weather dates alone is insufficient. RAW deletions
are not propagated by MERGE; an intentional source removal needs a controlled
`dbt build --full-refresh` into an inactive schema. Schema changes also require review.

## Validation without a warehouse

```bash
.venv/bin/dbt parse --profiles-dir . --no-partial-parse
```

Parsing checks dbt/Jinja configuration and dependency references; it does not execute
Snowflake SQL or prove credentials, grants, data loading, or runtime performance.
The unit test fixture covers leap-day means/totals, a missing hour and a null hour.
Execute unit and data tests using `dbt build` once source tables are provisioned.

Official references: [Snowflake adapter configuration](https://docs.getdbt.com/reference/resource-configs/snowflake-configs),
[dbt data tests](https://docs.getdbt.com/reference/resource-properties/data-tests).

Additional offline checks render the models, parse Snowflake SQL, and execute translated
queries against a small DuckDB fixture (no Snowflake credentials):

```bash
.venv/bin/python -m pip install -r checks/requirements.txt
.venv/bin/python checks/check_models.py
```

These checks cover complete and partial days, absent coverage, leap-year/season lengths,
late historical arrivals, corrected observations and rolling refresh. They do not execute
Snowflake MERGE or validate warehouse-specific execution plans. Run the dbt unit/data tests
and a real backfill/correction reconciliation in Snowflake before deployment.
