# /// script
# requires-python = ">=3.11"
# dependencies = ["marimo>=0.20,<1", "pandas>=2.2,<3", "pyarrow>=17,<22", "plotly>=6,<7"]
# ///
# Use the project environment: make install-notebook && make notebook
import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell
def _():
    import json
    import os
    from pathlib import Path

    import marimo as mo
    import pandas as pd
    import plotly.express as px
    from weather_analysis import AnalysisService, DatasetStore

    return AnalysisService, DatasetStore, Path, json, mo, os, pd, px


@app.cell
def _(mo):
    mo.md("""
    # Weather exploration: questions → evidence → initial findings

    Start with data quality, then explore one question at a time. The daily/annual
    tables below were calculated by **PySpark** from hourly observations. We use pandas
    and Plotly for fast exploratory comparisons; a later cell lets you run a new
    hourly PySpark calculation. Kafka is not required for this historical analysis.

    Edit cells and add markdown notes as you investigate. Keep dataset version,
    filters, units and denominators with each finding. These are descriptive patterns
    in selected locations, not causal effects or representative global estimates.
    """)
    return


@app.cell
def _(DatasetStore, Path, mo, os, pd):
    notebook_root = Path(mo.notebook_location()).parent
    platform_root = Path(os.getenv("WEATHER_PLATFORM_ROOT", str(notebook_root / "data/platform")))
    mo.stop(not (platform_root / "active.json").exists(), mo.md(
        "No published data found. Obtain the team's dataset bundle or run `make process` "
        "and `make publish` after ingesting raw data. Set WEATHER_PLATFORM_ROOT for another store."))
    store = DatasetStore(platform_root)
    manifest = store.get_overview()
    daily_all = store.read("daily_metrics").assign(date=lambda frame: pd.to_datetime(frame.date))
    locations_all = store.read("locations")
    yearly_all = store.read("yearly_metrics")
    mo.md(f"**Dataset:** `{store.version}` · **Coverage:** {manifest['coverage']['start'][:10]} "
          f"to {manifest['coverage']['end'][:10]} · **Hourly rows:** "
          f"{manifest['tables']['enriched_weather']['rows']:,}\n\n{manifest['attribution']}")
    return daily_all, locations_all, manifest, platform_root, store, yearly_all


@app.cell
def _(daily_all, manifest, mo, pd):
    coverage_table = pd.DataFrame(manifest["quality"].get("coverage_by_location", []))
    null_table = daily_all.isna().sum().rename("missing_values").rename_axis("column").reset_index()
    daily_quality = {
        "duplicate_location_date_keys": int(daily_all.duplicated(["location_id", "date"]).sum()),
        "daily_rows": len(daily_all),
        "locations": daily_all.location_id.nunique(),
        "days_with_fewer_than_24_hours": int((daily_all.observed_hours < 24).sum())
            if "observed_hours" in daily_all else "not recorded in this release",
    }
    mo.vstack([
        mo.md("## 1. Check coverage and quality first\nThese checks describe retained data. "
              "Review pipeline rejections too; a clean output does not prove every raw input was valid."),
        mo.ui.table(pd.DataFrame([daily_quality])),
        mo.accordion({"Hourly coverage per location": mo.ui.table(coverage_table),
                      "Missing values in daily outputs": mo.ui.table(null_table),
                      "Processing counts": mo.json(manifest.get("pipeline", {}))}),
    ])
    return coverage_table, daily_quality, null_table


@app.cell
def _(daily_all, mo):
    region_filter = mo.ui.dropdown(options=["All", *sorted(daily_all.region.unique())], value="All", label="Region")
    year_filter = mo.ui.multiselect(options=[str(year) for year in sorted(daily_all.date.dt.year.unique())],
                                   value=[str(year) for year in sorted(daily_all.date.dt.year.unique())], label="Years")
    band_filter = mo.ui.multiselect(options=sorted(daily_all.elevation_band.unique()),
                                   value=sorted(daily_all.elevation_band.unique()), label="Elevation bands")
    mo.vstack([mo.md("## 2. Define your study slice"), mo.hstack([region_filter, year_filter, band_filter])])
    return band_filter, region_filter, year_filter


@app.cell
def _(band_filter, daily_all, mo, region_filter, year_filter):
    selected_years = [int(value) for value in year_filter.value]
    selected_daily = daily_all[
        daily_all.date.dt.year.isin(selected_years)
        & daily_all.elevation_band.isin(band_filter.value)
        & ((daily_all.region == region_filter.value) | (region_filter.value == "All"))
    ].copy()
    mo.stop(selected_daily.empty, mo.md("No data in this slice. Select at least one year and elevation band."))
    mo.md(f"Selected **{selected_daily.location_id.nunique()} locations** and "
          f"**{len(selected_daily):,} location-days**. Means below use available retained days; "
          "check coverage before comparing locations.")
    return selected_daily, selected_years


@app.cell
def _(locations_all, selected_daily):
    location_means = (selected_daily.groupby(["location_id", "name", "region", "elevation_band", "elevation_m"], observed=True)
        .agg(mean_temperature_c=("daily_avg_temperature_c", "mean"),
             mean_daily_rainfall_mm=("daily_precipitation_mm", "mean"),
             mean_wind_ms=("daily_avg_wind_speed_ms", "mean"), observed_days=("date", "count"))
        .reset_index().merge(locations_all[["location_id", "latitude", "longitude"]],
                            on="location_id", validate="one_to_one")
        .assign(abs_latitude=lambda frame: frame.latitude.abs()))
    band_means = (location_means.groupby("elevation_band", observed=True)
        .agg(mean_temperature_c=("mean_temperature_c", "mean"),
             mean_daily_rainfall_mm=("mean_daily_rainfall_mm", "mean"),
             mean_wind_ms=("mean_wind_ms", "mean"), locations=("location_id", "count"))
        .reset_index())
    return band_means, location_means


@app.cell
def _(band_means, location_means, mo, px):
    elevation_plot = px.scatter(location_means, x="elevation_m", y="mean_temperature_c",
        color="region", symbol="elevation_band", hover_name="name",
        hover_data=["latitude", "observed_days"],
        labels={"elevation_m": "Elevation (m)", "mean_temperature_c": "Mean daily temperature (°C)"})
    mo.vstack([
        mo.md("## 3. Does temperature decrease with elevation?\nEach point is one location's "
              "mean over selected days. Change the region filter to check whether a pooled pattern "
              "also appears within a region. Latitude and sampling differences may explain part of it."),
        elevation_plot, mo.ui.table(band_means),
        mo.md("Band values give **equal weight to each location**, rather than pooling all hourly records."),
    ])
    return (elevation_plot,)


@app.cell
def _(location_means, mo, px):
    correlation_table = location_means[["elevation_m", "abs_latitude", "mean_temperature_c",
                                        "mean_daily_rainfall_mm", "mean_wind_ms"]].corr()
    correlation_plot = px.imshow(correlation_table, zmin=-1, zmax=1, color_continuous_scale="RdBu_r",
                                 text_auto=".2f", title="Pearson correlations across location means")
    mo.vstack([mo.md("### Check alternative explanations\nThese correlations use one row per selected "
                    "location, not thousands of repeated days. Small samples or constant variables "
                    "produce undefined correlations. Correlation alone cannot separate elevation "
                    "from latitude or regional climate."), correlation_plot])
    return correlation_plot, correlation_table


@app.cell
def _(location_means, mo, px, selected_daily):
    rain_plot = px.bar(location_means.sort_values("mean_daily_rainfall_mm", ascending=False),
                      x="name", y="mean_daily_rainfall_mm", color="elevation_band",
                      labels={"name": "Location", "mean_daily_rainfall_mm": "Mean daily precipitation (mm/day)"})
    wettest_days = selected_daily.nlargest(15, "daily_precipitation_mm")[["location_id", "name", "date", "daily_precipitation_mm"]]
    mo.vstack([mo.md("## 4. Where is rainfall higher, and are a few days driving it?\n"
                    "Compare average daily precipitation, then inspect extremes. These are reanalysis "
                    "values; check extreme dates against source data before describing real-world events."),
               rain_plot, mo.ui.table(wettest_days)])
    return rain_plot, wettest_days


@app.cell
def _(mo, px, selected_daily):
    location_seasons = (selected_daily.groupby(["location_id", "elevation_band", "season"], observed=True)
                       .daily_avg_temperature_c.mean().reset_index())
    seasonal_means = (location_seasons.groupby(["elevation_band", "season"], observed=True)
                      .daily_avg_temperature_c.mean().reset_index())
    seasonal_plot = px.bar(seasonal_means, x="season", y="daily_avg_temperature_c",
                          color="elevation_band", barmode="group",
                          category_orders={"season": ["winter", "spring", "summer", "autumn"]},
                          labels={"daily_avg_temperature_c": "Mean daily temperature (°C)"})
    mo.vstack([mo.md("## 5. Does the pattern change by season?\nSeasons are hemisphere-aware. "
                    "These bars average location-level seasonal means equally. The labels are "
                    "calendar conventions, not a claim that tropical locations have temperate seasons."), seasonal_plot])
    return location_seasons, seasonal_means, seasonal_plot


@app.cell
def _(location_means, mo, px, selected_years, yearly_all):
    annual_with_baseline = yearly_all.assign(
        study_mean_c=yearly_all.groupby("location_id").annual_avg_temperature_c.transform("mean"))
    annual_selected = annual_with_baseline[
        annual_with_baseline.location_id.isin(location_means.location_id)
        & annual_with_baseline.year.isin(selected_years)
    ].assign(anomaly_c=lambda frame: frame.annual_avg_temperature_c - frame.study_mean_c)
    anomaly_plot = px.line(annual_selected.sort_values("year"), x="year", y="anomaly_c", color="name",
                          labels={"year": "Year", "anomaly_c": "Temperature anomaly (°C)"})
    mo.vstack([mo.md("## 6. What changed during the study?\nEach annual mean is compared with that "
                    "location's mean across **all years in the published release**, even when you "
                    "filter the displayed years. This is not a 30-year climate normal, and six years "
                    "do not establish a long-term climate trend."), anomaly_plot])
    return annual_selected, annual_with_baseline, anomaly_plot


@app.cell
def _(band_filter, mo, region_filter, selected_years):
    hourly_filters = {"year": selected_years, "elevation_band": band_filter.value}
    if region_filter.value != "All":
        hourly_filters = {**hourly_filters, "region": [region_filter.value]}
    hourly_spec = {"name": "Notebook: seasonal hourly temperature",
                   "source": "enriched_weather", "filters": hourly_filters,
                   "group_by": ["elevation_band", "season"],
                   "aggregations": {"temperature_2m": ["avg", "min", "max", "count"]}}
    run_hourly = mo.ui.run_button(label="Calculate from hourly data with PySpark")
    mo.vstack([mo.md("## 7. Ask a new question using Spark\nEdit this cell's structured specification "
                    "to choose a metric, grouping or aggregation. The button runs a saved PySpark job; "
                    "repeated requests use its cache. These averages weight **hourly observations**, "
                    "so their weighting differs from the equal-location comparisons above."),
               mo.json(hourly_spec), run_hourly])
    return hourly_filters, hourly_spec, run_hourly


@app.cell
def _(AnalysisService, hourly_spec, mo, platform_root, run_hourly, store):
    mo.stop(not run_hourly.value and mo.app_meta().mode != "script",
            mo.md("Press the button above when you want a new hourly calculation."))
    analysis_service = AnalysisService(platform_root, version=store.version)
    hourly_job_id = analysis_service.submit_job(hourly_spec)
    hourly_metadata = analysis_service.get_job_status(hourly_job_id)
    if hourly_metadata["status"] != "completed":
        raise RuntimeError(hourly_metadata.get("error", "Job did not complete"))
    hourly_result = analysis_service.load_job_result(hourly_job_id)
    mo.vstack([mo.md(f"Job `{hourly_job_id}` · {'cache hit' if hourly_metadata['cache_hit'] else 'new Spark result'} "
                    f"· {hourly_metadata['input_rows']:,} matching hourly records"),
               mo.ui.table(hourly_result), mo.json(hourly_metadata)])
    return analysis_service, hourly_job_id, hourly_metadata, hourly_result


@app.cell
def _(band_means, mo):
    finding_notes = mo.ui.text_area(value="Question:\nObserved pattern and effect size:\nAlternative explanation:\nChecks still needed:\nProposed chart:\nOwner:", label="Your initial finding", rows=9)
    mo.vstack([mo.md("## 8. Record candidate findings, then challenge them\n"
                    "The table below is evidence to investigate, not a final causal conclusion. "
                    "Check sample sizes, change the region filter, inspect outliers, and see if "
                    "the pattern persists before turning it into a dashboard headline."),
               mo.ui.table(band_means), finding_notes])
    return (finding_notes,)


@app.cell
def _(band_filter, band_means, finding_notes, json, location_means, manifest, mo, region_filter, selected_years, store):
    findings_record = {"dataset_version": store.version, "fingerprint": manifest["fingerprint"],
                       "filters": {"region": region_filter.value, "years": selected_years,
                                   "elevation_bands": band_filter.value},
                       "method": "Daily means within location, then equal-weight location means within band",
                       "attribution": manifest["attribution"], "notes": finding_notes.value,
                       "band_comparison": band_means.to_dict(orient="records")}
    mo.vstack([mo.md("Download the evidence and notes for the report. You can reuse the calculation "
                    "and Plotly figure cells in the dashboard after validating the finding."),
               mo.download(data=json.dumps(findings_record, indent=2).encode(), filename="initial-finding.json", label="Download finding + provenance"),
               mo.download(data=location_means.to_csv(index=False).encode(), filename="location-means.csv", label="Download location evidence")])
    return (findings_record,)


if __name__ == "__main__":
    app.run()
