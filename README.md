# Big Weather

DS 4004 Option 5: geospatial analysis of temperature, precipitation and wind across
elevation bands. The local platform includes cached Open-Meteo ingestion, Scala
Spark processing, versioned Parquet storage, validated PySpark analysis jobs with
SQLite cache/history, and a runnable Streamlit dashboard starter.

## Teammates: start here

Read [the team handoff](docs/team-handoff.md) for setup, ownership and remaining work.
Use Python 3.11 and Java 17/21; Scala processing requires sbt 1.11+.

```bash
make install-team
# If no existing data or shared snapshot is available:
make ingest-all
make process
make publish VERSION=historical-2019-2024-v2
make dashboard
```

The dashboard opens at http://localhost:8501. If a published snapshot is already
available, skip ingestion, processing and publication. A published version cannot
be overwritten: choose a new version for changed data. The full 2019–2024 raw
extraction contains 1,893,888 hourly observations across 36 locations.

```bash
# Run and repeat an analysis to demonstrate cache reuse:
.venv/bin/weather-analysis run examples/jobs/seasonal-temperature.json
.venv/bin/weather-analysis run examples/jobs/seasonal-temperature.json
make evidence
```

Evidence tables and provenance appear in `data/platform/evidence/<version>/`.
Teammates can extend `dashboard/app.py` and use `weather_analysis.DatasetStore` /
`AnalysisService` without embedding ingestion or Spark internals in chart code.

## Small ingestion smoke test

```bash
make install
make ingest-sample
make process-sample
make test-python
make test-scala
```

The two-location, seven-day sample writes to **data/sample**, independently of the
full dataset. Partial ingestion replaces a location/year file, so always use a
separate data root for samples and partial-year experiments. `make install-team`
adds dashboard and custom-job dependencies; `make install` installs ingestion/tests.

## Storage and reproducibility

```text
data/raw/{locations,weather}/           # Hive location/year weather partitions
data/processed/                         # Scala outputs and pipeline metrics
data/cache/                             # Persistent historical API response cache
data/platform/releases/<version>/      # Immutable published Parquet + manifest
data/platform/active.json               # Active release pointer
data/platform/jobs.sqlite              # Job history and cache lookup
data/platform/jobs/<job_id>/            # Result, specification, metadata and log
data/platform/evidence/<version>/       # Reproducible descriptive findings tables
```

Generated data is ignored by Git. [The handoff](docs/team-handoff.md) explains how
to share a snapshot. Historical requests fix `models=era5`; raw units are UTC, °C,
mm, m/s and percent. Spark assigns hemisphere-aware seasons and elevation bands,
produces daily/rolling/annual/seasonal results and fits descriptive lapse-rate models.
Publication checks schemas, keys and coverage and records Parquet content checksums.

Open-Meteo data must be attributed to Open-Meteo and its upstream ERA5 providers
(Copernicus/ECMWF). Elevation uses Copernicus DEM GLO-90 (2021). Final report authors
must include the appropriate upstream dataset citations.

## Deliverables and scope

The foundation and interactive starter are ready. Teammates still own final chart
design, interpretation, report writing and presentation assembly. PostgreSQL,
current forecasts and optional Kafka are not implemented in the current local plan.

- [Project plan](docs/project-plan.md)
- [Team handoff and commands](docs/team-handoff.md)
- [Data/API contract and analysis limitations](docs/data-contract.md)
- [Dashboard guide](docs/streamlit-dashboard.md)
- [Exploratory analysis plan](docs/exploratory-analysis.md)
- [Verified evidence baseline](docs/evidence-baseline.md)
- [Final report outline](docs/final-report-outline.md)
- [Presentation outline and demo script](docs/presentation-outline.md)

Use `make lint`, `make test-python` and `make test-scala` for validation. Dashboard
tests run when its optional dependencies are installed; real PySpark integration
tests run when the analysis extra is installed. Benchmark local thread counts with
`.venv/bin/python scripts/benchmark.py --output data/benchmarks/run-01 --repeats 3`.
Typst is only required to rebuild the existing interim report with `make interim`.
