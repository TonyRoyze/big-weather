# Exploratory analysis plan

## Runnable starting point

Run `make evidence` against the published dataset. Generated Parquet tables,
`findings.md` and complete metadata appear under `data/platform/evidence/<version>/`.
The [team handoff](team-handoff.md) gives commands, ownership and acceptance criteria;
[the data contract](data-contract.md) defines units and denominator caveats.
Start writing in [the report outline](final-report-outline.md) and plan figures with
[the presentation outline](presentation-outline.md).

## Purpose

The exploratory analysis should turn the processed weather data into clear,
reproducible findings. Each team member or subgroup should own one question,
one dataset slice and one primary visualization.

## Core analysis questions

### 1. Elevation and temperature

How does temperature vary across the four elevation bands? Compare average
temperature, seasonal differences and the fitted lapse-rate relationship.

Suggested visuals:

- Elevation-versus-temperature scatter plot with trend line.
- Box plots by elevation band.
- Seasonal lapse-rate chart.

### 2. Seasonal and hemispheric behavior

How do temperature, precipitation and wind vary by season, and do patterns differ
between hemispheres?

Suggested visuals:

- Monthly or seasonal line chart.
- Small multiples by hemisphere.
- Seasonal summary heatmap.

### 3. Geographic variation

Which locations show the largest differences in temperature, precipitation or
wind, and how much of that variation is associated with elevation?

Suggested visuals:

- Location map colored by selected metric.
- Ranked location bar chart.
- Location-by-season heatmap.

### 4. Change over time

What year-over-year or rolling changes are visible in the study period?

Suggested visuals:

- Annual anomaly line chart.
- Thirty-day rolling temperature chart.
- Year-by-location comparison.

### 5. Extreme conditions

Which locations and periods have unusually high precipitation, wind or
temperature values?

Suggested visuals:

- Extreme-event count by location.
- Threshold exceedance timeline.
- Top-event table with date and location.

## Analysis standards

Every result must state:

- Dataset version and source attribution.
- Date range and number of observations.
- Filters and grouping fields.
- Units and aggregation method.
- Missing-value and outlier treatment.
- Whether the result came from cache or a newly executed Spark job.

Avoid implying causation from correlations. Elevation, latitude, season and
location are related factors, and the analysis should describe associations
unless a suitable causal design is introduced.

## Reproducible workflow

1. Start from a named processed Parquet dataset.
2. Define the analytical question and expected output.
3. Submit the equivalent custom job specification or Spark transformation.
4. Validate row counts, nulls, units and date coverage.
5. Save the result and the job metadata.
6. Build the Streamlit visualization from the saved result.
7. Record the finding, limitations and evidence in the final report.

## Team result template

Each team member should provide:

```text
Question:
Dataset/version:
Filters:
Method:
Main finding:
Evidence:
Limitations:
Dashboard view:
```

## Expected report outputs

The final report should include a small table of analysis jobs and findings,
followed by the strongest visualizations. Include both analytical findings and
engineering findings, such as the effect of partitioning, Spark parallelism and
cache reuse on processing time.
