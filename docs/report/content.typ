#import "@preview/merman:0.1.0": mermaid
#let diagram(source, caption) = figure(mermaid(source, width: 100%, height: 50%), caption: caption)

= Introduction and Project Scope

Geospatial Weather and Elevation Analysis is a regional data engineering and
exploration project covering 100 fixed locations in Sri Lanka and nearby South and
Southeast Asia. It combines hourly weather observations, location metadata, and
elevation to support comparisons across places and time. The study profile contains
47 hourly variables from Open-Meteo's ERA5-Seamless reanalysis.

The project brings ingestion, analytical processing, and visualization into one
workflow. Users must be able to select weather features, locations, and dates,
understand whether the requested data is available, obtain missing observations
within source limits, and inspect the resulting charts and analytical summaries.
A separate plain-English interface translates weather questions into validated
queries and explains the computed results.

== Objectives

- A resumable ingestion process with explicit coverage and quota accounting.
- Preserve source and apply consistent temporal and spatial data rules.
- Organize an analytical warehouse using Snowflake and version-controlled dbt models.
- Serve bounded queries through FastAPI to an interactive React geospatial dashboard.
- Integrate coverage checks, feasible query suggestions, and on-demand downloads.
- Support plain-English analysis with inspectable queries and evidence-based summaries.

== Research Scope

The analysis examines how weather variables varie with elevation and how these relationships vary over time.
The coordinates are deliberately selected study sites rather than a representative
random sample. Reanalysis values are model estimates, not direct readings from a
weather station at every requested coordinate. Comparisons must therefore remain
descriptive and account for latitude, geography, sampling, and model resolution.

== Project Design and Implementation Status

The project architecture uses Snowflake and dbt for warehouse storage and
transformation. The working local prototype uses Parquet and Python/PySpark for
processing and validation, with Arrow-based queries for the interactive map.
React/deck.gl, FastAPI, and the plain-English
analysis page have local implementations. Warehouse integration and coverage-aware
on-demand retrieval are project requirements whose implementation remains
outstanding.

= Data and Analytical Methodology

== Sources and Geographic Coverage

The location catalogue records a stable identifier, name, country, region,
coordinates, and elevation for each of the 100 sites. Coordinates include approximate named locations
and mountain sites. Requested coordinates and terrain elevation are retained separately from the grid
coordinates and elevation returned by the weather source.

The weather profile requests ERA5-Seamless, a combination of ERA5 and ERA5-Land,
with UTC timestamps. It covers thermal and humidity measures, precipitation, wind,
pressure, clouds, soil conditions, evapotranspiration, and radiation.

== Temporal Coverage and Ingestion Order

The historical lower bound is 1 January 2020. The active backfill is pinned to
31 August 2026 following the decision to begin with the previous month. It requests
the newest seven-day window across all locations before moving to the preceding
window. This provides broad geographic coverage early in the download rather than
finishing every year for one location first. Windows are clipped at calendar-year
boundaries, and verified legacy annual downloads are reused without overlapping
observations. The saved study plan defines the exact expected coverage.

Recent reanalysis may be unavailable because the source is delayed. Unavailable
data must not be saved as a completed empty checkpoint or confused with an API
quota pause. Coverage is assessed from committed observations rather than assumed
from the overall earliest and latest dates.

== Quality Rules and Derived Measures

Ingestion checks that each response contains every expected hour exactly once and preserves
all requested fields, including typed null values. Each committed chunk has request
metadata and a checksum so interrupted runs can resume and existing files can be
verified.

Daily values require 24 non-null hourly observations for the selected variable.
Daily precipitation is summed, supported continuous measures such as temperature
are averaged. Incomplete days remain null.

= Findings

== Analytical Scope and Comparable Coverage

The analysis examines data quality, geographic and temporal variation, and the
relationship between elevation and weather across the study locations. Source
observations are joined with location metadata and aggregated over explicitly
verified periods. Coverage checks, consistent aggregation rules, and independent
processing validation provide the basis for the findings.

The study locations span *3–4,321 m* in elevation. Within Sri Lanka, the
30 sampled sites span 3–2,500 m, while the six coastal sites occupy a narrow
3–10 m band. Comparing these subsets allows the analysis to assess how the
available elevation range influences geographic associations.

== Data Quality and Processing Verification

No duplicate location–timestamp keys were found, and the metadata join preserved
all 1,230,960 rows without unmatched locations or row multiplication. The 47
numeric weather fields were checked separately from partition metadata.

Fifteen broad plausibility screens found no out-of-range observations. Temperature
and surface-pressure bounds accommodate both coastal and mountain locations.
No observations were removed by these checks. Temperatures range from −8.0°C to 40.7°C and surface pressure
falls to 599.8 hPa. There are 1,606 hourly rows with positive snowfall and 4,567
with positive snow depth.

== Geographic and Temporal Variation

#figure(
  table(
    columns: (2fr, 1.2fr, 2.2fr), inset: 6pt,
    table.header([*Measure*], [*Value*], [*Interpretation*]),
    [Hourly mean temperature], [22.80°C], [Pooled across selected sites],
    [Relative humidity], [83.11%], [Pooled hourly mean],
    [Wind speed], [2.47 m/s], [Pooled hourly mean],
    [Hourly precipitation], [0.356 mm], [Pooled hourly mean],
    [Mean daily precipitation], [8.53 mm], [Equivalent under complete 24-hour coverage],
  ),
  caption: [Pooled weather measures. These
    describe the selected sites and are not national or annual climate averages.],
)
#pagebreak()

Temperature varies substantially across the sampled elevation range

#figure(
  table(
    columns: (0.7fr, 1.5fr, 1.2fr), inset: 6pt,
    table.header([*Rank*], [*Location*], [*Mean temperature*]),
    [Warmest], [Chennai], [31.04°C],
    [2], [Madurai], [30.68°C],
    [3], [Batticaloa], [30.44°C],
    [Coolest], [Nathu La], [6.27°C],
    [2], [Dingboche], [7.66°C],
    [Range], [Warmest to coolest], [24.77°C],
  ),
  caption: [Highest and lowest sampled site mean temperatures],
)

Rainfall also varies substantially between locations. The largest observed period
rainfall totals and highest mean wind speeds are shown below

#figure(
  table(
    columns: (1.5fr, 1.5fr, 1.3fr, 2fr), inset: 6pt,
    table.header([*Measure*], [*Rank*], [*Location*], [*Value*]),
    [Rainfall total], [1], [Lachen], [3,387.2 mm],
    [Rainfall total], [2], [Sylhet], [3,147.4 mm],
    [Rainfall total], [3], [Pokhara], [3,108.1 mm],
    [Mean wind speed], [1], [Jaffna], [7.92 m/s],
    [Mean wind speed], [2], [Mannar], [7.79 m/s],
    [Mean wind speed], [3], [Trincomalee], [6.21 m/s],
  ),
  caption: [Leading rainfall totals and mean wind speeds.],
)

// #figure(
//   image("img/replicated_country_weather.png", width: 100%),
//   caption: [Temperature and mean daily rainfall across the sampled sites in each
//     country],
// )


== Elevation Relationships


#figure(
  table(
    columns: (2fr, 0.6fr, 1.2fr, 1fr, 1.3fr), inset: 6pt,
    table.header([*Sample*], [*Sites*], [*Elevation (m)*], [*Pearson r*], [*Nominal p*]),
    [All regional sites], [100], [3–4,321], [−0.981], [3.81 × 10⁻⁷¹],
    [Sri Lanka], [30], [3–2,500], [−0.965], [8.20 × 10⁻¹⁸],
    [Coastal subset], [6], [3–10], [+0.685], [0.133],
  ),
  caption: [Elevation versus location mean temperature.],
)

This contrast shows the sensitivity of the correlation to geographic selection
and elevation range. The coastal subset provides too little elevation variation
to characterise the relationship observed across the full study area.

#figure(
  image("img/replicated_elevation_temperature.png", width: 100%),
  caption: [Elevation–temperature associations for all regional sites
    and the Sri Lankan subset.],
)

#figure(
  table(
    columns: (2.2fr, 1.1fr, 1.1fr), inset: 6pt,
    table.header([*Measure and predictor*], [*Regional r*], [*Sri Lankan r*]),
    [Temperature versus elevation], [−0.981], [−0.965],
    [Mean daily precipitation versus elevation], [+0.337], [+0.285],
    [Wind speed versus elevation], [−0.506], [−0.531],
    [Relative humidity versus elevation], [+0.418], [+0.232],
    [Surface pressure versus elevation], [−0.998], [−0.9995],
    [Cloud cover versus elevation], [+0.312], [+0.515],
    [Shortwave radiation versus elevation], [−0.229], [−0.129],
  ),
  caption: [Pearson correlations between location-level weather summaries and
    latitude or elevation.],
)

The table shows that elevation has the strongest temperature and surface pressure association in both
samples. Elevation's associations with rainfall and wind are less consistent and do not justify a universal claim that either measure is controlled by elevation, exposure, geography, season, and sample selection remain
relevant.

#figure(
  image("img/elevation_rain_wind_humidity.png", width: 100%),
  caption: [Elevation versus mean daily precipitation, wind speed, and relative
    humidity.],
)

Rainfall differs substantially among sites at similar elevations, indicating that
elevation alone provides an incomplete description of precipitation. The humidity
relationship also depends on the geographic sample, while wind speed decreases with
elevation in both groups despite several low-elevation sites having particularly
high wind speeds.

#figure(
  image("img/elevation_pressure_cloud_radiation.png", width: 100%),
  caption: [Elevation versus surface pressure, cloud cover, and shortwave
    radiation. Surface pressure is measured
    at the site and is distinct from pressure reduced to mean sea level.],
)

Surface pressure has a much tighter relationship with elevation than the other
measures. Cloud cover is more positively associated with elevation within Sri Lanka
than across the region, while shortwave radiation remains weakly related in both
samples.

#pagebreak()

#include "nonparametric-same-month-results.typ"

#pagebreak()
#include "nonparametric-elevation.typ"




= System Architecture and Data Engineering

#grid(
  columns: (1fr, 1fr),
  gutter: 1.2em,
  [
    #diagram(
      "flowchart TD\n        A[Open Meteo source API] --> B[Shared ingestion scheduler and quota ledger]\n        B --> C[Committed source files and provenance]\n        C --> D[Snowflake RAW]\n        D --> E[dbt staging and intermediate models]\n        E --> F[Validated MART tables and views]\n        F --> G[FastAPI query and coverage service]\n        G --> H[React dashboard and Ask weather]\n        H --> I[Missing data request]\n        I --> B",
      [On-demand Ingestion]
    )
  ],
  [
    The source retrieval service and the analytical query service have different roles.
    Ingestion acquires missing observations under the source quota. The serving layer
    reads validated data and returns only the requested analytical result. An interactive
    query against stored data does not itself imply that missing source data has been
    retrieved.
    
    == Technology Selection
    
    === Snowflake
    
    Snowflake is selected for the shared warehouse design because it provides managed
    analytical storage and independently scalable virtual warehouses. Snowflake manages
    the underlying compute infrastructure, so database managers and data engineers do
    not need to provision, patch, or manually maintain virtual machines and cluster
    runtimes. Compute can be suspended when it is not needed and scaled for heavier
    workloads, allowing transformation jobs and interactive serving to use separate
    warehouses while sharing one governed analytical dataset. Its SQL interface also
    fits the location and time filters, aggregations, and window calculations used by
    the dashboard.
  ]
)

This managed, SQL-first operating model is a strong fit for the project because it
supports centralized access, role-based governance, and a clear deployment boundary
between ingestion, transformation, and serving. Compared with a Databricks-first
design, Snowflake requires less platform setup for this warehouse workload: teams do
not need to assemble and maintain clusters, runtime environments, and notebook-based
execution as part of the core serving platform. Databricks is powerful and well
suited to developer-led data engineering, distributed processing, and data science,
but its flexibility can introduce more operational choices and setup than this
project needs. A local Parquet/Spark workflow remains sufficient for development and
may also be sufficient for the present dataset size. Snowflake is therefore selected
for team usability, managed operations, multi-user access, and independent compute
scaling, rather than simply because the project contains millions of rows. The
trade-offs are cloud dependence, operating cost, role administration, and the need
to monitor and control warehouse activity.

=== Data Marts

A data mart is the curated analytical layer of the warehouse, not another database
product. It presents data at a defined grain for a specific use. The project design
uses location-day weather records for map playback and history, seasonal or annual
summaries for comparisons, and coverage records for availability checks. This follows
the separation of reusable staging logic from consumer-facing models described in
#link("https://docs.getdbt.com/best-practices/how-we-structure/4-marts")[dbt's guidance on marts].

This layer prevents each dashboard or generated query from redefining the same
24-hour completeness rule, precipitation calculation, units, and location joins.
Materializing frequently requested aggregates can reduce repeated computation,
views can expose less frequently used results without creating a stored copy of
every possible combination. That choice requires measurement rather than assuming
all marts are automatically faster.

The raw hourly layer remains available for new analyses and audit. Marts must retain
coverage counts and meaningful keys because a summary can hide missing data or
unequal sample sizes. Additional models also create refresh dependencies and storage
costs. The design therefore starts with the grains actually needed by the dashboard
and expands only when a clear analytical requirement warrants it.

=== dbt

dbt provides a framework for defining transformations as modular models, expressing
their dependencies, and documentation alongside the code.

For this project, dbt makes the path from raw hourly observations to validated daily
and comparative measures explicit and reviewable. A change to the complete-day rule
can be maintained in a shared model rather than copied into multiple API handlers.

Snowflake supplies the storage and execution compute, dbt organizes and runs the
transformation logic that produces the marts. It does not replace the Open-Meteo
ingestion client, quota scheduler, or FastAPI service. Tests can catch key and coverage
violations, but their presence alone does not establish scientific validity.
The trade-off is an additional project configuration and deployment layer compared
with a small collection of SQL scripts. This is justified when several contributors
maintain dependent models and reproducible releases, the team must still design
incremental boundaries carefully for backwards-in-time backfills.

== Resumable Ingestion

The ingestion service records the study configuration, completed chunks, source
request windows, timestamps, checksums, and quota usage. Atomic writes separate an
in-flight response from a committed checkpoint. One writer per study prevents two
processes from writing the same chunk. A shared ledger coordinates weighted request
costs across runs and must accompany the dataset when ingestion moves to another
computer.

// The local scheduler enforces conservative rolling minute, hour, and daily budgets.
// It pauses when a budget is exhausted and preserves completed work. Failed attempts
// also consume the local budget. Parallelizing source requests with Spark is not a
// strategy for avoiding API limits, Spark is used for local processing after retrieval.

== Snowflake and dbt Warehouse Design

The warehouse is organized into `RAW`, `STAGING`, `INTERMEDIATE`, and `MART` schemas.
The raw layer retains source observations and ingestion provenance. Staging models
standardize names, types, and timestamps. Intermediate models join the location and
elevation catalogue and derive temporal and geographic dimensions. Mart models
apply the complete-day rule and expose daily metrics and analytical evidence views.

Source files enter through a controlled landing area and Snowflake stage. The
implementation must select and configure the loading mechanism, incremental keys,
and recovery boundaries before enabling unattended ingestion. Incremental processing
must handle both older backfill windows and newly available observations without
creating duplicate location-hours.

dbt tests must cover unique keys, non-null identifiers, accepted values, catalogue
relationships, timestamp bounds, and daily observation counts. Release metadata
identifies the source coverage, transformation version, and active analytical
snapshot. A reconciliation run must compare warehouse outputs with the validated
local reference before the dashboard changes its serving source.

= Dashboard and User Workflows

== Geospatial Exploration

The primary interface uses React, TypeScript, and deck.gl. A sidebar contains the
weather feature, country, date range, and *Load weather* controls. Map settings are
opened from a button at the top-right of the chart. The interface uses a plain white
background, with the map, coverage information, and selected location taking visual
priority.

Elevation controls geographic height and the selected weather feature controls
colour. Interpolated colours are applied to the terrain tiles themselves, following
hills and valleys. The interpolation uses nearby valid samples, missing vertices,
long connections, and regions outside supported triangles remain unfilled. These
colours are a visual estimate between samples, not additional measured observations.
Display exaggeration changes the view without changing recorded elevation or weather.

#figure(
  image("img/dashboard.jpeg", width: 100%),
  caption: [The dashboard interface]
)

Users can pan, rotate, zoom, select a location, and inspect its history. The date
slider and playback reuse the loaded window. The colour scale remains fixed within
that window so changes over time are comparable.

== Query and Response Lifecycle

The current map query is bounded to 100 locations and 93 days. Selecting
*Load weather* requests the chosen feature and window, editing controls alone does
not relabel the loaded scene. A newer request cancels the older browser request,
and stale responses must not overwrite the current selection. Missing observations
remain visibly missing rather than becoming zero.

The local map service filters and aggregates Parquet through Arrow. The warehouse
serving design queries validated Snowflake marts through the same application
boundary. Responses are currently returned as complete JSON windows. Playback is
interactive, but this does not constitute live source ingestion or an implemented
Kafka, WebSocket, or server-sent-event pipeline.

== Coverage-aware, On-demand Ingestion

Coverage-aware retrieval is a core dashboard requirement. Before fulfilling a
selection, the service must check the requested locations, dates, and weather
feature against committed coverage. It must identify missing observations and
estimate the required source requests, weighted quota cost, and likely waiting time.
Source unavailability and quota exhaustion must be explained separately.

If the full selection cannot be served immediately, the dashboard must calculate
practical alternatives: fewer locations with complete coverage, a shorter complete
date window, or the available subset with gaps marked. For example, an interface
could suggest using 12 complete locations or the latest seven complete days. Such
numbers are illustrative, actual suggestions must come from the current coverage
catalogue and remaining quota.

#grid(
  columns: (1fr, 1fr),
  gutter: 1.2em,
  [
    #diagram(
      "flowchart TD\n    A[Select feature locations and dates] --> B[Check committed coverage]\n    B --> C{Complete coverage}\n    C -- yes --> D[Query and visualize]\n    C -- no --> E[Estimate missing work and quota]\n    E --> F[Offer fewer locations or shorter window]\n    E --> G[User selects download missing data]\n    G --> H[Shared ingestion queue]\n    H --> I[Wait for quota or source availability]\n    I --> J[Commit and validate new data]\n    J --> K[Refresh serving data and cache]\n    K --> D",
      [Required coverage-aware dashboard workflow.]
    )
  ],
  [
    The *Download missing data* action must submit only the missing work to the shared
    ingestion scheduler. It must reuse checkpoints and prevent duplicate requests or
    competing writers. Requests blocked by the daily budget remain queued with an
    estimated retry time. Existing data remains available for inspection while they wait.
    After the required observations are committed and the serving data is refreshed,
    the dashboard must update coverage, invalidate stale cached results, and rerun the
    selected analysis.
    
    This workflow belongs to the project scope. The current prototype queries already
    downloaded data, the coverage suggestions and user-triggered retrieval path remain
    to be implemented.
  ]
)





== Ask Weather

The Ask weather page accepts a plain-English question and retrieves the current
catalogue of features, units, locations, and coverage as model context. The model
returns a restricted structured plan. The server validates that plan and compiles
an allowlisted query, it does not execute arbitrary model-written Python or SQL.
The result includes a chart, plain-text summary, result table, coverage counts, and
the exact generated query.

The local demo uses the user's Codex ChatGPT sign-in for planning and summaries,
with a separately configured OpenAI API mode available. Spark executes the validated
local query. The warehouse design requires an equivalent validated Snowflake query
adapter, the existing Spark path must not be described as a deployed warehouse query.
Questions are independent and summaries are based on computed aggregates. This is
catalogue-grounded analysis rather than a document-vector retrieval index.

Supported requests contain one feature, up to 100 locations, and up to 366 days.
They include daily trends, location or country comparisons, elevation scatter plots,
and precipitation totals by location. Generated explanations retain units and coverage limitations and
must not turn descriptive associations into causal claims.

#figure(
  image("img/askweather.png", width: 100%),
  caption: [The Ask Weather dashboard interface]
)

= Execution and Reproducibility

== Local Prototype

Install the Python environment and frontend dependencies before starting the explorer.
Spark-based analysis requires a compatible Java installation. The raw explorer is served at `http://127.0.0.1:8001`. The main commands are,

```bash
make install-team
make install-explorer
make regional-plan
make regional-ingest-all
make explorer-raw
```

The default Ask weather demo uses `codex login` with ChatGPT sign-in. Its usage counts
against the connected subscription. API mode is selected with
`WEATHER_AI_PROVIDER=openai` and a server-side `OPENAI_API_KEY`. Credentials must never
be included in browser environment variables or shared report artifacts.

== Warehouse Integration and Release Verification

Warehouse implementation proceeds through role and schema setup, staged loading,
dbt source and model configuration, incremental backfill, data-quality tests, and
reconciliation with the local reference. Only validated marts should be exposed to
the API. On-demand downloads must become queryable through this same validated path.

Release records must retain source coverage, transformation version, configuration,
and dataset fingerprint. Evidence should also record the exact query, selected
locations, date window, units, and coverage counts. These records make results
reproducible across dashboards and separate verified outputs from unfinished work.

== Implementation Constraints and Design Decisions

In practice, the available Snowflake trial allowance of approximately \$400 in free credits was not sufficient for us to comlete the MVP. We therefore simulated the Snowflake and
dbt process locally using Parquet, PySpark, and versioned release metadata.

The weather API introduced a second constraint, it limited how much data could be
extracted in a single request. Requesting the entire historical range for every
location and variable was therefore impractical and increased the risk of failed
or incomplete downloads. The ingestion strategy was changed to prioritise the
most recent available data across the study locations. Historical data can then
be requested and streamed into the application on demand when a user selects a
date range that is not already available locally. This approach gives users a
useful current view quickly, while avoiding an unnecessarily large initial
extraction.
