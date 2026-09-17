# Big Weather — regional elevation study

The React + deck.gl **Elevation Explorer** is the project dashboard. It includes
terrain, weather colours, date playback, location history and cached on-demand
queries. Run `make install-explorer`, then `make explorer` and open
http://127.0.0.1:8001. For the existing partial download, use `make explorer-raw`
(clearly labelled unpublished preview). See [dashboard setup, controls and data
semantics](docs/elevation-explorer.md).

A Python/PySpark project exploring 100 locations across Sri Lanka and nearby South
and Southeast Asia, with 47 historical hourly variables. Ingestion fills the newest
available week across all locations, then works backwards to 2020. ERA5-Seamless
has a five-day delay; the end date is pinned on the first run.
Data comes from Open-Meteo ERA5-Seamless reanalysis, with location/year Parquet storage.

## Setup and run

Use Python 3.11+ and Java 21 on macOS/Linux. Windows teammates can run
[`dist/BigWeather-Setup.exe`](dist/BigWeather-Setup.exe), which installs the environment
through WSL. The setup can be built before data is ready; it only bundles a dataset
when an active published release exists.

```bash
make install-team
make plan
make ingest-all     # one designated machine; resumable and quota-aware
make process        # requires the full download
make publish
make evidence
make install-explorer
make explorer       # React dashboard + FastAPI service
```

For dashboard development, start the FastAPI service in one terminal:

```bash
.venv/bin/python -m weather_analysis.explorer \
  --raw-root data/regional-2020-2025 --port 8001
```

Then start the React/Vite development server in another terminal:

```bash
make explorer-dev
```

Open http://127.0.0.1:5173. The Vite server proxies API requests to FastAPI on
port 8001. Stop both development processes with `Ctrl+C`.

For the built dashboard served directly by FastAPI, use `make explorer`. Use
`make explorer-raw` when no published release exists; the interface labels this
as an unpublished preview. `make start-local` and `make stop-local` are available
for starting or stopping the project's managed local services.

Until publication, the dashboard shows setup instructions.
Do not start another ingestion worker if one is already running. Regional data and
checkpoints live in `data/regional-2020-2025`; the quota ledger lives in `data/cache`.
Tests use small synthetic fixtures and do not need the full download.

In the dashboard, open **On-demand charts**, select up to 10 locations and weather
metrics, slide to a date range, and click **Load charts**. Requests read only selected
columns and matching location-days from the published Parquet snapshot; repeated
requests are cached for an hour (up to 64 requests). No Spark startup or live
Open-Meteo request is needed. Drag or zoom each chart, or use its range slider within
the loaded dates. Click Load charts again to fetch another range. Large ranges use
labeled calendar buckets with mean daily values, including rainfall, and at most
6,000 plotted rows per chart. The displayed query time excludes chart rendering.

## Code map

| Path | Purpose |
|---|---|
| `config/locations_regional_100.csv` | Fixed sampling coordinates |
| `python/src/weather_ingest/` | Regional import, checkpoints, quota budget, variable profile |
| `python/src/weather_analysis/` | PySpark transforms, publication, jobs, FastAPI service and evidence |
| `explorer/` | React/deck.gl dashboard and Vite frontend |
| `python/tests/` | Ingestion, temporal analysis, publication, dashboard and packaging checks |
| `installer/windows/`, `scripts/` | Team setup and verification |

```bash
make test
make lint
make windows-setup
```

## Team deliverables

- [Regional study and download details](docs/regional-study.md)
- [Data contract](docs/data-contract.md)
- [Team handoff and deployment](docs/team-handoff.md)
- [Windows setup](docs/windows-setup.md)
- [Final report outline](docs/final-report-outline.md)
- [Presentation outline](docs/presentation-outline.md)

Keep findings tied to the dataset version, filters, units and evidence table or job ID.
Account for spatial grid sharing, elevation downscaling and non-random site selection.

The dashboard also includes **Ask weather**, a plain-English analysis page powered
by OpenAI and local Spark. See [setup and supported analyses](docs/ask-weather.md).

The [Snowflake/dbt implementation package](warehouse/dbt/README.md) contains RAW table
contracts, transformations, marts, coverage models, and offline validation for warehouse deployment.
