# Explore first, build dashboard views afterward

The runnable starting point is `notebooks/explore_weather.py`, a marimo notebook
stored as ordinary Python. Use the notebook editor to change code, view tables and
plots, and write markdown explanations. This workflow does not require Kafka.

## Open it

From the project root (or Big Weather Terminal on Windows):

```bash
make install-notebook
make notebook
```

Open the URL printed by marimo. In WSL, paste that URL into your Windows browser
if it does not open automatically. Keep the terminal running. If another dataset
store is needed, use `make notebook PLATFORM_ROOT=/path/to/platform`.

The notebook needs a published snapshot containing the PySpark results.
Until the regional import is processed and published, it shows setup instructions. It does not need raw API downloads. A notebook session captures one dataset
version; rerun the loading cell to switch after publishing a different version.

## Work through these questions

1. **Can I trust this slice?** Review missing hours, incomplete days, duplicates,
   null counts and pipeline rejections. Cleaned outputs alone do not reveal every
   raw-data issue. Keep coverage and denominator counts with each comparison.
2. **How does temperature relate to elevation?** Start with the location scatter and
   band means. Filter to a region and compare again. Check whether latitude or the
   selected locations could explain the pooled association.
3. **Where is rainfall higher?** Compare mean daily precipitation in mm/day. Inspect
   extreme days separately, and verify notable dates against the source before
   calling them observed events. Do not compare pooled rainfall totals across bands
   with different numbers of locations.
4. **Does the relationship vary by season?** Use the seasonal chart, remembering
   that season labels are reversed in the Southern Hemisphere.
5. **What changed over the study period?** Compare annual anomalies relative to each
   location's full published-study mean. Filtering displayed years does not change
   that baseline. Do not describe this short period as proof of a climate trend.

Each chart exposes its code directly. Change grouping columns, add a comparison,
inspect the intermediate DataFrame, then write what you learned in a markdown cell.
Use the region/year/elevation controls for quick comparisons.

## When to use pandas versus PySpark

The notebook uses pandas for the saved daily/annual tables: these are small enough
to inspect and plot interactively. They were produced by the main PySpark pipeline.
Changing a chart or notebook filter does not rebuild the whole pipeline.

For a new calculation over the full hourly data, edit the `hourly_spec` cell and
press **Calculate from hourly data with PySpark**. This uses the same validated job
interface as the dashboard, writes results and metadata, and reuses cached results.
For example, replace its metric/operations with:

```python
"aggregations": {"precipitation": ["sum", "count"], "wind_speed_10m": ["avg", "max"]}
```

Use `group_by: ["location_id", "year"]` for per-location annual totals. A count lets
you check coverage alongside a total. The job specification accepts only the fields
and operations listed in [the data contract](data-contract.md).

The button's hourly averages weight observations equally. The notebook's band
comparison first averages within each location, then gives locations equal weight.
Those methods answer different questions; keep the method with the finding.

If a question needs an operation beyond the approved job specification, add a
function in `python/src/weather_analysis/transforms.py`, check it on a small slice,
then process and publish a new version. This requires raw inputs; the setup EXE's
published snapshot is enough for notebook exploration and custom jobs but does not
contain the raw ingestion partitions.

## Record an initial finding

Use the note field at the bottom of the notebook and download its JSON record,
which includes the dataset fingerprint, filters and band evidence. Download the
location table as well. Notes edited in a widget are not a substitute for saving:
download them or write a markdown cell before closing the notebook.

Use this structure:

```text
Question: Is temperature lower at higher elevations in the selected region?
Observation: Give the measured difference/correlation, units and location counts.
Evidence: Dataset version + notebook/table or Spark job ID + selected filters.
Alternative explanation: Latitude, regional climate, coverage or sampling.
Checks: Does it persist within regions and across years/seasons? What are the outliers?
Status: Candidate finding / checked / ready for dashboard.
```

A good dashboard chart should answer a question you have already investigated.
Reuse its DataFrame calculation and Plotly figure from the notebook, then add the
filters and explanation in Streamlit. A visually striking pattern alone is not a
validated finding.

## Share results

```bash
make notebook-export
```

This generates `data/notebook-exports/explore_weather.html` using default controls.
For the current interactive selection, export HTML from the editor. HTML is a saved
view, not a replacement for the editable `.py` notebook or the published data.
The CLI export may leave the button-gated Spark result unexecuted; saved job results
and provenance remain available through the job service.

Maintainers can validate with `marimo check notebooks/explore_weather.py` and
`.venv/bin/python notebooks/explore_weather.py`. Script execution runs the default
hourly job as well. Notebook controls are always visible in the interactive editor.

The current Windows installer includes this notebook and its dependencies when
rebuilt with `make windows-setup`. A build created before publication installs the environment without a dataset.

## Plain Python with automatic Spark startup

Create a `.py` file directly in `notebooks/` and import the shared setup:

```python
from spark_setup import weather, F, past_average, chronological_split

features = past_average(weather, 'temperature_2m', hours=24)
train, validation, test = chronological_split(
    features, validation_start='2024-01-01', test_start='2025-01-01',
    horizon_hours=24,  # purge labels that extend across a split boundary
)
result = (features.groupBy('location_id')
          .agg(F.avg('temperature_2m').alias('mean_temperature_c')))
result.show()
# Only aggregate results should be collected for Plotly/pandas:
plot_data = result.toPandas()
```

Run the included example:

```bash
cd notebooks
../.venv/bin/python spark_patterns.py
```

In the Windows installer terminal, the virtual environment is already on PATH, so use
`python spark_patterns.py`. In Jupyter/marimo, use
`from weather_analysis.notebook import NotebookSession` and `session = NotebookSession()`;
then `weather = session.weather`. The session prints the actual dataset version and row
count. It requires an active published release; run `make regional-publish` after
processing the completed import. Set `WEATHER_PLATFORM_ROOT` and optionally
`WEATHER_DATASET_VERSION` to select a different published release explicitly.

Spark starts automatically on import and executes jobs at actions such as `.show()`,
`.count()` and `.write.parquet(...)`. Arbitrary Python loops and pandas code do not become
parallel Spark code. Use Spark DataFrame operations for the large hourly dataset; collect
small summaries for visualization. `SPARK_MASTER` defaults to `local[4]` and
`SPARK_PARTITIONS` to 8. This uses local cores, not teammates' computers.

Rows are distributed by location and initially sorted by timestamp. Subsequent Spark
operations may reorder them: temporal calculations must use an explicitly ordered
per-location window. `past_average` uses elapsed hours, excludes the current observation
and does not fill gaps. Compute features before filtering the displayed date range to
retain preceding history. The published daily rolling average includes the current day;
it is descriptive and should not be used directly as a same-day forecast feature.

`chronological_split` uses shared UTC boundaries for all locations, never `randomSplit`.
Construct Python datetimes with an explicit UTC timezone. Set `horizon_hours` to the
furthest future label offset. Fit preprocessing and models on training only. For rolling
forecasts, preceding observations from the validation period may be available; for a
fixed-origin multi-step forecast, do not use any observation after that forecast origin.
The helper cannot detect arbitrary leakage in user-written feature or label code.
