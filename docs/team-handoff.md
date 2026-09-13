# Team handoff

The shared foundation is implemented. Teammates can now extend a runnable dashboard
and develop findings against named, stable datasets. The final report and slides
remain team deliverables; the repository provides evidence exports and writing outlines.

## Windows one-file setup

Use `dist/BigWeather-Setup.exe` to install the project and dependencies through WSL.
It includes the published dataset and creates desktop launchers. Follow
[the Windows setup guide](windows-setup.md), including its first-machine validation
notes. The commands below are for a manual macOS/Linux or prepared WSL setup.

## Start here

Use Python 3.11 and Java 17 or 21. PySpark includes the Spark runtime; Java is still
required. On macOS/Linux, run from the repository root:

```bash
make install-team
# Existing full raw data on this machine: skip ingestion.
# On a fresh machine without a shared snapshot:
make ingest-all
make process
make publish VERSION=historical-2019-2024-pyspark-v1
make dashboard
```

If a teammate supplies a published snapshot, extract it at the repository root,
then run `make install-team` and `make dashboard`; no API download or processing run
is needed for dashboard work. Python dependencies include PySpark (~434 MB package)
for processing and custom jobs. For charts only, `pip install -e '.[dashboard,dev]'` is sufficient.

Published versions cannot be overwritten. If a version already exists, skip
publication or choose a new version after a changed processing run. The dashboard
uses `data/platform/active.json`. To work with a different local store:

```bash
make dashboard PLATFORM_ROOT=data/another-platform
```

`.env.example` is a configuration template, not automatically loaded by the Python
CLI. Export environment variables explicitly or use the documented Make variables.

The sample workflow is isolated from full data:

```bash
make ingest-sample
make process-sample
.venv/bin/weather-analysis --root data/sample/platform publish --data-root data/sample --version sample-v1
make dashboard PLATFORM_ROOT=data/sample/platform
```

Do not run ingestion/processing at the same time as publication. Ingestion still
replaces location/year partitions: a partial-year request must use a separate data
root. The fixed historical dataset does not need daily refreshes.

## Ownership and completion criteria

| Workstream | Ready now | Team work remaining | Completion evidence |
| --- | --- | --- | --- |
| Ingestion/storage | Cached ERA5 extraction, isolated samples, validated versioned snapshots | Review location resolution and upstream citations | Commands, manifest, 36-location coverage, units |
| Analysis platform | PySpark transformations, quality/runtime counts, safe PySpark jobs, SQLite history and TTL cache | Run repeated performance experiment; review model assumptions | Saved specs, job IDs, benchmark logs |
| Dashboard | Overview/map, date/location/band/season filters, three chart views, custom jobs, history, pipeline evidence, downloads | Assign chart owners; improve layout and narrative; add annual anomalies/lapse-rate views | Screenshots and tested walkthrough of team findings |
| Findings/report | Five evidence tables with metadata; report outline | Own questions, test alternatives, write findings and limitations | Each claim links to version + table/job + chart |
| Presentation | Architecture and slide-by-slide outline | Select strongest results, export legible figures, rehearse | Final deck and reliable local demo |

Suggested division: one person owns `dashboard/app.py`; one owns temperature and
seasonal analysis; one owns precipitation/wind and geographic comparisons; one
owns performance evidence and report/deck integration. Adjust to the team size.
Chart contributors can add separate modules and call them from the existing page
functions. Agree on one dataset version before comparing findings.

## Stable Python interface

```python
from weather_analysis import AnalysisService, DatasetStore

store = DatasetStore("data/platform")  # captures active version once
manifest = store.get_overview()
daily = store.read("daily_metrics", filters=[("location_id", "=", "colombo")])

service = AnalysisService("data/platform", version=store.version)
job_id = service.submit_job({
    "name": "Seasonal temperature",
    "source": "enriched_weather",
    "filters": {"year": [2023, 2024]},
    "group_by": ["elevation_band", "season"],
    "aggregations": {"temperature_2m": ["avg", "count"]},
})
metadata = service.get_job_status(job_id)
if metadata["status"] == "completed":
    result = service.load_job_result(job_id)
history = service.list_jobs()
```

`submit_job` is synchronous and returns an ID even when the worker fails. Invalid
specifications raise `ValueError` before creating a job. Check status before reading.
Concurrent local requests serialize through a file lock; this is a single-machine
demonstration service, not a distributed queue. Spark work has a 600-second default
timeout, independent of time waiting for another job. The worker log records details.
An abruptly killed dashboard process may leave a running/queued history record;
inspect it and resubmit after ensuring the old worker has stopped.

Cache keys include canonical filters, grouping/aggregation, dataset version,
Parquet content fingerprint and `TRANSFORM_VERSION`. Names do not change the
calculation. Cache TTL is 24 hours from computation and hits do not extend it.
Increase `TRANSFORM_VERSION` when changing worker semantics. Result retrieval time
and UI rendering are excluded from the recorded service duration. Cache-hit metadata
points to the original `result_job_id`, so retain that directory.

A [verified baseline](evidence-baseline.md) is checked in for review before downloading
the dataset. Generated data and detailed provenance remain in the shared snapshot.

## Evidence commands

```bash
.venv/bin/weather-analysis run examples/jobs/seasonal-temperature.json
.venv/bin/weather-analysis run examples/jobs/seasonal-temperature.json # cache hit
.venv/bin/weather-analysis run examples/jobs/location-rainfall.json
make evidence
.venv/bin/python scripts/benchmark.py --output data/benchmarks/comparison-01 --repeats 3
```

The benchmark runs the full PySpark job on identical raw inputs with `local[1]` and
`local[4]`, alternates order and preserves logs and metrics. Run it on an otherwise
idle machine. Four threads are local task parallelism, not a four-node cluster.
Compare repeated medians; do not promise a speedup. The UI on port 4040 exists only
while a Spark job is running.

Evidence is under `data/platform/evidence/<version>/`: location comparison,
elevation comparison, annual anomalies, wettest location-days and seasonal lapse
rates, all as Parquet plus `metadata.json` and `findings.md`. Load them with
`pandas.read_parquet`. Export selected dashboard/job results and their provenance
when preparing charts. See [the data contract](data-contract.md).

## Share data without committing it

After publication and evidence export finish, create a local bundle (substitute
the chosen version). Generated datasets and bundles stay outside Git:

```bash
mkdir -p data/bundles
tar -czf data/bundles/historical-pyspark-v1.tar.gz \
  data/platform/active.json \
  data/platform/releases/historical-2019-2024-pyspark-v1 \
  data/platform/evidence/historical-2019-2024-pyspark-v1
```

Make sure `active.json` names the bundled version. Teammates extract at the repo
root with `tar -xzf <bundle>`. Do not overwrite an existing store with a different
release of the same name. Release manifests record SHA-256 checksums of every
Parquet file; preserve them. The bundle does not include raw API cache or raw
hourly inputs; reproduce ingestion separately for ingestion/PySpark development.

## Verification and remaining scope

```bash
make lint
make test-python          # real Spark integration when analysis extra is installed
```

Tests cover schema/key publication rejection, immutable snapshots, specification
validation, known Spark aggregation results, filtering, empty outputs, cache reuse,
timeouts, evidence calculations and Streamlit page/empty-data states. Offline
fixtures do not call Open-Meteo. Dashboard tests use Streamlit's AppTest:
https://docs.streamlit.io/develop/api-reference/app-testing.

The runnable scope follows the current Parquet + SQLite plan. The original proposal's
PostgreSQL serving layer, current-forecast search and optional Kafka layer are not
implemented. Confirm any required proposal changes with the course supervisor.
Arbitrary user code, asynchronous distributed jobs and public hosting are also out
of this handoff's scope. The deployed design would need resource limits and an
operational recovery policy before use as a public multi-user service.
