# Big Weather — regional elevation study

## Separate 3D dashboard

The React + deck.gl **Elevation Explorer** runs alongside the Streamlit dashboard.
It includes terrain, weather colours, date playback, location history and cached
on-demand queries. Run `make install-explorer`, then `make explorer` and open
http://127.0.0.1:8001. For the existing partial download, use `make explorer-raw`
(clearly labelled unpublished preview). Streamlit remains `make dashboard`.
See [setup, controls and data semantics](docs/elevation-explorer.md).

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
make notebook       # interactive exploration
make notebook-altair # Spark ingestion + interactive Altair starter
make notebook-relationships # themed 17-variable Spark relationships
make dashboard
```

Use `make start-local` to start the Streamlit dashboard, optional 3D explorer and
Marimo notebook server together. Use `make stop-local` to stop only the project
services on ports 8501, 8001 and 2718. Logs are kept in `.local-services/`.

Until publication, the dashboard and exploration notebook show setup instructions.
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

For plain Python analysis, copy `notebooks/spark_patterns.py`, import `spark_setup`,
and run it from `notebooks/`. Spark starts automatically and loads a published release.
Spark DataFrame operations run in parallel; temporal helpers use ordered per-location
windows and chronological evaluation splits. Only collect small summaries for plotting.

## Code map

| Path | Purpose |
|---|---|
| `config/locations_regional_100.csv` | Fixed sampling coordinates |
| `python/src/weather_ingest/` | Regional import, checkpoints, quota budget, variable profile |
| `python/src/weather_analysis/` | PySpark transforms, notebook runtime, publication, jobs and evidence |
| `notebooks/` | Interactive exploration and plain Python examples |
| `dashboard/app.py` | Streamlit dashboard starter |
| `python/tests/` | Ingestion, temporal analysis, publication, dashboard and packaging checks |
| `installer/windows/`, `scripts/` | Team setup and verification |

```bash
make test
make lint
make windows-setup
```

## Team deliverables

- [Regional study and download details](docs/regional-study.md)
- [Notebook workflow and temporal analysis](docs/notebook-workflow.md)
- [Data contract](docs/data-contract.md)
- [Team handoff and deployment](docs/team-handoff.md)
- [Windows setup](docs/windows-setup.md)
- [Final report outline](docs/final-report-outline.md)
- [Presentation outline](docs/presentation-outline.md)

Keep findings tied to the dataset version, filters, units and evidence table or job ID.
Account for spatial grid sharing, elevation downscaling and non-random site selection.

The explorer also includes **Ask weather**, a plain-English analysis page powered
by OpenAI and local Spark. See [setup and supported analyses](docs/ask-weather.md).

The [Snowflake/dbt implementation package](warehouse/dbt/README.md) contains RAW table
contracts, transformations, marts, coverage models, and offline validation for warehouse deployment.
