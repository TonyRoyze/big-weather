# Final report working outline

Status: writing scaffold; team interpretation and final figures are still required.
Do not submit unchanged. Assign an owner and reference an evidence version for each section.

## 1. Abstract

After completing the analysis, summarize the question, selected global locations,
2019–2024 ERA5 data, PySpark method and two defensible numerical findings.
Avoid claims of global representativeness or causality.

## 2. Questions and scope

State the team's chosen elevation/temperature, seasonality, precipitation/wind and
temporal-change questions. Explain selection of 36 locations and the four elevation
bands. Record departures from the original proposal (SQLite metadata/Parquet serving;
PostgreSQL, real-time forecast and Kafka not currently implemented).

## 3. Data and methodology

Cite Open-Meteo and the appropriate upstream ERA5 and Copernicus DEM sources.
Describe geocoding/elevation resolution, fixed ERA5 model, UTC and physical units,
caching/retries, partitioning, version manifests and checksums. Use the
[data contract](data-contract.md) for validation rules and exact aggregation definitions.
Explain local Spark task parallelism, hemisphere-aware seasons, daily/rolling/annual
metrics and the pooled seasonal OLS model. Explain why totals need denominators.

## 4. System architecture and implementation

Insert the architecture from [the project plan](project-plan.md). Describe ingestion,
raw Parquet, PySpark transforms, immutable releases, Streamlit, the validated PySpark
worker, SQLite job history and the 24-hour result cache. Include one saved job JSON
and its output schema. Distinguish the synchronous local worker from a distributed queue.

## 5. Quality and engineering evaluation

Use the release manifest and `pipeline_metrics.json` for input/output counts,
rejections, unmatched joins and hourly coverage. Cite test commands and results.
Add repeated local[1]/local[4] benchmark medians, hardware/software versions and
limitations. Compare cache misses and hits using identical job specifications and
dataset versions; state that metadata timing excludes result download/chart rendering.
Document the timestamp precision compatibility issue and incomplete-run publication risk.

## 6. Team findings

Complete this ledger before writing narrative:

| Owner | Question | Dataset version + evidence table / job ID | Effect size and units | Chart | Alternative explanation / limitation |
| --- | --- | --- | --- | --- | --- |
| Assign | Elevation and temperature | elevation_comparison, seasonal_lapse_rates | Fill from export | Scatter / slope chart | Latitude, region, repeated observations |
| Assign | Rainfall / wind geography | location_comparison, location-rainfall job | Fill from export | Ranked locations | Unequal coverage; selected locations |
| Assign | Seasonal patterns | seasonal-temperature job | Fill from export | Seasonal bars / heatmap | Local seasons versus tropical regimes |
| Assign | Change over study period | annual_anomalies | Fill from export | Annual anomaly lines | Six years; not a climate normal |

For each finding: state the question, describe exactly what the chart shows, quantify
the difference, cite provenance, discuss an alternative explanation and state its
scope. Validate extreme values against the source before treating them as events.

## 7. Challenges, limitations and future work

Discuss API/model resolution, geocoding ambiguity, selected-location bias, missing
hours, pooled totals, model assumptions, transient failures, local-only scaling and
synchronous UI jobs. Separate completed solutions from proposed future work.

## 8. Conclusions

Answer the original research questions using only supported findings. Identify the
strongest insight and the most important unresolved uncertainty.

## References and appendix

Include upstream dataset citations, software versions, source revision, commands,
saved specs, complete evidence metadata and benchmark summaries. Keep screenshots
legible with units, dates, population and dataset version in captions.
