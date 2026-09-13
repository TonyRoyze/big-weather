# Big Weather project plan

## Implementation handoff

The core local platform is now implemented: immutable Parquet releases, Scala
quality/runtime metrics, validated PySpark custom jobs, SQLite history and TTL cache,
a runnable Streamlit starter and reproducible evidence exports. Start with
[the team handoff](team-handoff.md). The work packages below retain the broader
plan; Kafka, arbitrary sorting/selection and final team interpretations remain future
work. The current ingestion path is batch ELT, not streaming.

## Project objective

Build a reproducible local weather analytics platform that demonstrates an ELT
pipeline, parallel data processing, cached analysis and an interactive Streamlit
application. The system is intended for an academic demonstration rather than
production deployment or a cloud-scale replacement for Databricks.

## Current baseline

The repository currently contains:

- Open-Meteo ingestion with cached API responses.
- Location, elevation and weather data handling in Python.
- A Scala/Apache Spark processing application.
- Enriched weather data and analytical outputs organized as Parquet datasets.
- Python and Scala tests.

The implemented extensions are the Streamlit starter, cache-aware custom analysis
jobs and evidence exports. Optional Kafka ingestion and final team findings remain
future work.

## Architecture

```text
Open-Meteo API
      ↓
Python extractor and API cache
      ↓
Raw Parquet data  ← optional Kafka weather-events topic for streaming demo
      ↓
Spark transformations (local[4])
      ↓
Processed Parquet datasets and job outputs
      ↓
SQLite job/cache metadata
      ↓
Streamlit dashboard
```

The design is primarily ELT: data is extracted and loaded into raw storage
before the heavier transformations are applied by Spark. Lightweight schema and
request validation may occur during ingestion, so the implementation can be
described as batch ELT with lightweight extraction-time validation. Streaming is
not implemented.

## Work packages

### 1. Data ingestion and storage

- Keep the existing Open-Meteo historical ingestion as the reproducible batch
  path.
- Preserve raw API responses and metadata before transformation.
- Use stable units, UTC timestamps and explicit dataset versions.
- Keep API caching separate from published raw and processed datasets.
- If time permits, add a Python producer that publishes newly retrieved records
  to a Kafka `weather-events` topic. Kafka is an optional demonstration layer,
  not a prerequisite for the core results.

### 2. Spark analysis

- Continue using Spark for validation, enrichment and aggregation.
- Run the local demonstration with `local[4]` and at least four partitions.
- Compare `local[1]` and `local[4]` on the same workload.
- Record runtime, input rows, output rows, partition count and rejected rows.
- Write each analysis result to a clearly named Parquet output.

### 3. Custom analysis jobs

Allow users to configure approved analyses from Streamlit. A job should include
the dataset, filters, date range, grouping columns and aggregations. The system
validates this specification and maps it to a safe PySpark transformation.

For the demonstration, support a whitelist of operations:

- Filtering by location, elevation band, season and date range.
- Grouping by location, elevation band, season or year.
- `count`, `sum`, `avg`, `min` and `max`.
- Sorting and selecting output columns.

Do not execute arbitrary Python submitted through the dashboard. Store job
metadata and status in SQLite or a small JSON-backed registry, then write result
files under `data/platform/jobs/<job_id>/`.

### 4. Cache-aware results

Use a cache-aside flow:

1. Convert the validated job specification into a deterministic query key.
2. Check whether an unexpired result already exists.
3. Return the cached result on a hit.
4. Run Spark on a miss.
5. Store the result and metadata for later requests.

Measure cache-hit latency against cache-miss processing time. Include dataset
version and transformation version in the key so stale results are not reused.

### 5. Streamlit application

Implement the interface described in [the Streamlit dashboard guide](streamlit-dashboard.md).
The dashboard should present the team analyses and also make the pipeline
behavior visible: cache status, job progress, records processed and Spark
parallelism.

### 6. Exploratory analysis

Use the analysis questions and visualization plan in
[the exploratory-analysis guide](exploratory-analysis.md). Each team member or
team should own a clearly defined analytical question and produce a reproducible
result from the processed datasets.

## Demonstration sequence

1. Run the reproducible ingestion command and show the raw dataset layout.
2. Run the Spark job and show the generated Parquet outputs.
3. Show the Spark UI with multiple tasks and explain `local[4]`.
4. Submit a custom analysis job from Streamlit.
5. Show the first request as a cache miss and display its result.
6. Repeat the same request and show the faster cache hit.
7. Present the team-specific finding using the dashboard visualization.

## Evaluation evidence

Collect the following for the report and presentation:

- Number of locations, observations and partitions.
- Raw-to-processed row counts and validation results.
- Runtime with one versus four local execution threads.
- Cache-hit and cache-miss latency.
- Number of submitted, completed and failed analysis jobs.
- At least one data-quality issue or API limitation and how it was handled.

## Deliverables

- Well-documented ingestion, storage, Spark analysis and job code.
- Interactive Streamlit dashboard with team-specific analyses.
- Final report covering methodology, ELT architecture, challenges, findings,
  performance and limitations.
- Presentation covering the architecture, pipeline demonstration, visualizations
  and key findings.

## Scope and limitations

This is a local distributed-processing demonstration. `local[4]` provides real
Spark task parallelism using four local execution threads, but it is not a
multi-machine Spark cluster. Kafka is optional and should only be added if it can
be run reliably within the available lab or personal-machine constraints.
