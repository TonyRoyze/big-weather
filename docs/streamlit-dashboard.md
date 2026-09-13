# Streamlit dashboard guide

## Implemented starter

Run `make dashboard` after following [the team handoff](team-handoff.md).
`dashboard/app.py` implements Overview, Exploration, Custom analysis, Job history
and Pipeline views. The definitive interfaces and storage semantics are documented
in [the data contract](data-contract.md). The remaining sections describe the target
design; asynchronous polling and arbitrary result sorting/selection are not implemented.

## Purpose

The dashboard is the user-facing layer for the Big Weather ELT pipeline. It
should allow users to explore published results, submit approved custom analyses
and see enough pipeline metadata to understand how the result was produced.

Streamlit should read processed Parquet data and job metadata. It should not
contain the ingestion logic or execute arbitrary user-provided Python.

## Suggested pages

### Overview

Show:

- Dataset version and last refresh time.
- Number of locations and observations.
- Latest processing status.
- Cache-hit rate and typical query latency.
- A map or summary chart of the selected weather metric.

### Exploratory analysis

Provide filters for location, elevation band, season and date/year. Display the
team-specific charts described in [the exploratory-analysis guide](exploratory-analysis.md).

### Custom analysis job

Provide a form with:

- Dataset and date range.
- Locations or elevation bands.
- Group-by field.
- Metric and aggregation.
- Optional result name.

On submission, validate the fields, create a job ID and display the job status.
The first implementation can run the Spark job synchronously for simplicity;
an asynchronous runner with polling is preferable if jobs take long enough to
show progress.

### Job history

Display submitted jobs with:

- Job ID and name.
- Created time.
- Status: queued, running, completed or failed.
- Processing duration.
- Input and output row counts.
- Link to the result table or download.

### Pipeline monitoring

Show recent ingestion time, raw and processed dataset locations, cache status and
the latest Spark runtime. If Kafka is added, include topic/partition information
and the timestamp of the most recent event.

## Job specification

Use a structured specification rather than accepting Python code:

```json
{
  "name": "Seasonal temperature by elevation band",
  "source": "enriched_weather",
  "filters": {
    "season": ["winter", "summer"],
    "date": ["2020-01-01", "2024-12-31"]
  },
  "group_by": ["elevation_band", "season"],
  "aggregations": {
    "temperature_2m": ["avg", "min", "max"]
  }
}
```

The validator should reject unknown columns, unsupported functions, empty
filters and unsafe paths. The job runner should construct the Spark expression
from the validated specification.

## Result and cache contract

Each cache-miss computation produces the following; cache-hit metadata references
the original result via `result_job_id`:

```text
data/platform/jobs/<job_id>/result.parquet/
data/platform/jobs/<job_id>/metadata.json
```

Metadata should include the job specification, dataset version, transformation
version, input/output counts, start/end timestamps, runtime and status.

Use a deterministic hash of the validated specification plus dataset version as
the cache key. A repeated request should read the previous result rather than
rerun Spark.

## Visual design

Use a consistent layout with a sidebar for navigation and filters, KPI cards at
the top of each page, charts in the main area and expandable technical details.
Always display units, date coverage, source attribution and whether the result
was a cache hit or a newly processed job.

Include clear states for loading, no matching data, failed jobs and stale data.
Avoid presenting a chart without its aggregation, population, date range and
units.

## Teammate implementation boundary

The dashboard implementation should consume stable helper functions or a small
job interface rather than importing Spark internals into every page. Recommended
interfaces are:

```python
submit_job(spec) -> job_id
get_job_status(job_id) -> metadata
load_job_result(job_id) -> dataframe
get_overview(dataset_version) -> summary
```

This lets the dashboard team work independently while the ingestion and Spark
teams change the processing implementation.
