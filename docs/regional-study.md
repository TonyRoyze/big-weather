# Regional elevation study: 100 locations, newest first

The study imports 47 historical hourly variables for 100 fixed coordinates.
It starts with the newest available seven days for every location, then moves
backwards one week at a time to 2020-01-01. ERA5-Seamless has a five-day delay;
the initial end date is pinned when the plan is saved so resuming stays consistent.
Both dashboards can preview completed downloads while the backfill continues.

## Geographic design

`config/locations_regional_100.csv` contains the reproducible sampling coordinates.
Sri Lanka is in South Asia; the study includes South and Southeast Asia rather than
calling all locations Southeast Asian. Coordinates are approximate named site points,
including mountain summits, not verified weather station locations.

| Country | Locations |
|---|---:|
| Sri Lanka | 30 |
| India | 20 |
| Nepal | 10 |
| Bhutan | 5 |
| Bangladesh | 5 |
| Myanmar | 5 |
| Thailand | 7 |
| Vietnam | 5 |
| Laos | 4 |
| Cambodia | 3 |
| Malaysia | 3 |
| Indonesia | 2 |
| Singapore | 1 |

The live elevation lookup returned 3–4,321 m: 36 sites below 200 m, 20 at
200–999 m, 39 at 1,000–2,999 m and 5 at >=3,000 m. These are deliberately
selected elevation contrasts, not a representative random sample of the region.
Requested coordinates and DEM elevations live in `raw/locations/locations.parquet`.
Each chunk’s `_source*.json` also records the returned weather grid coordinates and elevation.

## Variables and model

The exact pinned list is `python/src/weather_ingest/variables.py`. It includes
thermal/humidity variables; precipitation, rain and snow; pressure and cloud layers;
wind at 10/100 m and gusts; four soil temperature and moisture depths; evapotranspiration;
boundary-layer height; atmospheric water vapour; sunshine/daylight indicator; and
hourly-average and instantaneous solar radiation variables.

We request `era5_seamless`, a fixed ERA5/ERA5-Land combination, with UTC timestamps,
Celsius, m/s and millimetres for precipitation. Snowfall uses cm and snow depth uses m;
read each response's `hourly_units`, rather than assuming every field shares a unit.
Tilt and azimuth are both fixed to zero for the tilted radiation fields.

This covers the standard and additional deterministic hourly historical fields relevant
to this region. It excludes Europe-only CERRA fields, ensemble spread fields that need
another model, daily-only fields such as sunrise, and separate air-quality/marine APIs.
There is no universal “all fields” switch across all Open-Meteo products. New fields
require a new profile and study root. No missing feature is silently dropped; unavailable
values remain typed nulls, with per-feature null counts recorded for each chunk.

The historical API produces reanalysis estimates, not direct station readings. Nearby
coordinates may share underlying grid cells. Open-Meteo also adjusts temperatures for
elevation: a measured temperature/elevation relationship can partly reflect that adjustment.
Compare matched sites within countries/latitude bands and report this limitation.
DJF/MAM/JJA/SON labels in the existing dashboard are calendar seasons, not Sri Lankan
monsoon classifications. Add country-appropriate monsoon definitions for that analysis.

Sources: [historical API documentation](https://open-meteo.com/en/docs/historical-weather-api),
[API quota accounting](https://open-meteo.com/en/pricing). Attribute Open-Meteo,
Copernicus/ECMWF ERA5 and ERA5-Land and Copernicus DEM in the report.

## Download and resume

From the project root after `make install-team` (or the Windows installer terminal):

```bash
make regional-plan          # no network; prints exact fields and expected size
make regional-ingest        # up to 100 new chunks; safe to rerun
make regional-ingest-all    # keep resuming automatically until the backfill is complete
```

The default folder is `data/regional-2020-2025`. Status is in `ingestion-status.json`.
Exit code 2 means paused/incomplete, so `make` may print an error even when a batch
completed correctly. `--watch` prints progress and rechecks quota pauses every minute
(or unavailable recent reanalysis every hour); Ctrl+C is
safe. Rerun the same command to resume. HTTP/network failures stop with an error;
completed checkpoints remain intact. Keep the computer awake for continuous downloading.

`make regional-plan` reports the exact coverage and estimated weighted API cost.
Weekly requests trade more API overhead for earlier coverage of all locations.
The importer conservatively limits itself to 500/minute, 4,500/hour and 9,000 per
rolling 24 hours. The full backfill takes multiple daily quota windows.
Actual availability and other activity on the same IP can slow it further. The shared
ledger is `data/cache/regional-api-usage.json`; keep it between runs and use one machine
for ingestion. Do not parallelize API
requests using Spark. Spark parallelizes local analysis after ingestion.

Each chunk validates every expected UTC hour, preserves all fields, writes atomically,
and saves a SHA-256 checksum. Reruns check existing hashes. Changing locations, model,
fields or pinned dates requires another root. The first migration from the old
location/year schedule preserves verified downloads and backs up its plan as
`study-plan-before-latest-first.json`. Existing yearly files are reused; new chunks
use `weather-<start>-<end>.parquet` and matching `_source-<start>-<end>.json`
inside the same location/year partitions. The default folder name stays unchanged. A failed or partial download cannot be processed
or published through the regional workflow. Local checkpoints and metadata are ignored
by git; the Windows EXE includes configuration/code and an active published dataset when
one exists, never this incomplete raw download.

## Process and share when ingestion is complete

```bash
make regional-process
make regional-publish
make evidence
make windows-setup
make dashboard
```

Processing preserves the 47 fields in `enriched_weather`; existing summary tables still
compute the four original core measures. Other fields are available for custom notebook
Spark aggregations. Publication checks complete location/hour coverage, preserves source
metadata and creates `regional-100-2020-2025-v1`. Restart running notebooks to load it.
The dashboard's custom-query whitelist still exposes its original four measures.

For team deployment, ingest on one machine, publish an immutable release, then distribute
the rebuilt EXE or release folder to teammates. Run Streamlit on one shared host with
persistent data storage if the team needs a shared dashboard. Each person's local Spark
uses that machine's cores; no Kafka or multi-machine Spark cluster is required here.
