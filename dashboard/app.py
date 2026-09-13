"""Run with `make dashboard`. Extend the page functions without importing Spark."""

import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from weather_analysis import AnalysisService, DatasetStore
from weather_analysis.spec import BANDS, GROUPS, METRICS, OPERATIONS, SEASONS

st.set_page_config(page_title="Big Weather", page_icon="🌦", layout="wide")


@st.cache_data(show_spinner=False)
def read_table(root, version, fingerprint, name):
    # Version and fingerprint invalidate cached tables when a new snapshot is published.
    return DatasetStore(root, version).read(name)


def overview(store):
    manifest = store.get_overview()
    st.header("Weather across elevations")
    st.write("Explore the selected locations, local seasons and weather patterns in the study.")
    a, b, c = st.columns(3)
    a.metric("Locations", manifest["tables"]["locations"]["rows"])
    b.metric("Hourly observations", f"{manifest['tables']['enriched_weather']['rows']:,}")
    c.metric("Daily summaries", f"{manifest['tables']['daily_metrics']['rows']:,}")
    locations = read_table(str(store.root), store.version, manifest["fingerprint"], "locations")
    st.map(locations.rename(columns={"latitude": "lat", "longitude": "lon"}))
    st.dataframe(locations[["name", "country", "region", "elevation_m"]], hide_index=True)
    st.info(
        "These selected locations describe the study sample; they are not a representative global sample."
    )


def exploration(store):
    st.header("Explore the study")
    daily = read_table(
        str(store.root), store.version, store.manifest["fingerprint"], "daily_metrics"
    )
    choices = sorted(daily.location_id.unique())
    bands = st.multiselect("Elevation bands", sorted(BANDS), default=sorted(BANDS))
    seasons = st.multiselect("Local seasons", sorted(SEASONS), default=sorted(SEASONS))
    locations = st.multiselect("Locations", choices, default=choices)
    bounds = pd.to_datetime(daily.date)
    dates = st.date_input(
        "Date range",
        value=(bounds.min().date(), bounds.max().date()),
        min_value=bounds.min().date(),
        max_value=bounds.max().date(),
    )
    if len(dates) != 2:
        st.info("Select a start and end date.")
        return
    subset = daily[
        daily.elevation_band.isin(bands)
        & daily.season.isin(seasons)
        & daily.location_id.isin(locations)
        & bounds.between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))
    ].copy()
    if subset.empty:
        st.info(
            "No observations match these filters. Choose another location, season or date range."
        )
        return
    metric = st.selectbox(
        "Weather metric",
        ["daily_avg_temperature_c", "daily_precipitation_mm", "daily_avg_wind_speed_ms"],
    )
    labels = {
        "daily_avg_temperature_c": "Daily mean temperature (°C)",
        "daily_precipitation_mm": "Daily precipitation (mm)",
        "daily_avg_wind_speed_ms": "Daily mean wind speed (m/s)",
        "date": "Date (UTC)",
        "elevation_m": "Elevation (m)",
    }
    st.caption(
        f"{len(subset):,} location-days · {subset.location_id.nunique()} locations · "
        f"{dates[0]} to {dates[1]} · daily aggregates of validated hours"
    )
    tab1, tab2, tab3 = st.tabs(["Time series", "Elevation relationship", "Seasonal comparison"])
    with tab1:
        chart = subset.sort_values("date")
        if len(chart) > 12000:
            chart["date"] = pd.to_datetime(chart.date).dt.to_period("M").dt.to_timestamp()
            chart = (
                chart.groupby(["location_id", "date"], observed=True)[metric].mean().reset_index()
            )
            st.caption(
                "Large selection: plotted as monthly means of selected daily values, including precipitation."
            )
        st.plotly_chart(
            px.line(chart, x="date", y=metric, color="location_id", labels=labels),
            use_container_width=True,
        )
    with tab2:
        means = (
            subset.groupby(["location_id", "name", "elevation_m", "elevation_band"], observed=True)[
                metric
            ]
            .mean()
            .reset_index()
        )
        st.plotly_chart(
            px.scatter(
                means,
                x="elevation_m",
                y=metric,
                color="elevation_band",
                hover_name="name",
                labels=labels,
            ),
            use_container_width=True,
        )
        st.caption(
            "Each point is a location mean over selected days. Association does not establish an elevation effect."
        )
    with tab3:
        location_seasons = (
            subset.groupby(["location_id", "elevation_band", "season"], observed=True)[metric]
            .mean()
            .reset_index()
        )
        seasonal = (
            location_seasons.groupby(["elevation_band", "season"], observed=True)[metric]
            .mean()
            .reset_index()
        )
        st.plotly_chart(
            px.bar(
                seasonal,
                x="season",
                y=metric,
                color="elevation_band",
                barmode="group",
                labels=labels,
            ),
            use_container_width=True,
        )
        st.caption(
            "Equal-weight location means within each band and local season; precipitation is a mean daily total."
        )
    st.download_button(
        "Download selected daily data",
        subset.to_csv(index=False),
        "selected-daily-weather.csv",
        "text/csv",
    )


def custom_analysis(service):
    st.header("Custom analysis")
    st.write(
        "Choose a structured analysis of validated hourly observations. Results are saved for reuse and citation."
    )
    with st.form("analysis"):
        name = st.text_input("Analysis name", "Seasonal temperature by elevation")
        group = st.multiselect("Group by", sorted(GROUPS), default=["elevation_band", "season"])
        metric = st.selectbox("Hourly metric", sorted(METRICS), index=2)
        operations = st.multiselect("Aggregations", sorted(OPERATIONS), default=["avg", "count"])
        seasons = st.multiselect("Filter local seasons (blank selects all)", sorted(SEASONS))
        bands = st.multiselect("Filter elevation bands (blank selects all)", sorted(BANDS))
        locations = st.multiselect(
            "Filter locations (blank selects all)",
            sorted(service.store.read("locations").location_id),
        )
        coverage = service.store.manifest["coverage"]
        start, end = pd.Timestamp(coverage["start"]).date(), pd.Timestamp(coverage["end"]).date()
        dates = st.date_input("Analysis dates", (start, end), min_value=start, max_value=end)
        submitted = st.form_submit_button("Run analysis")
    if submitted:
        filters = {
            k: v
            for k, v in {
                "season": seasons,
                "elevation_band": bands,
                "location_id": locations,
            }.items()
            if v
        }
        if len(dates) != 2:
            st.error("Select a complete date range.")
            return
        filters["date"] = [d.isoformat() for d in dates]
        spec = {
            "name": name,
            "source": "enriched_weather",
            "filters": filters,
            "group_by": group,
            "aggregations": {metric: operations},
        }
        try:
            with st.spinner(
                "Running analysis; a first request starts Spark and may take a minute…"
            ):
                st.session_state["last_job"] = service.submit_job(spec)
        except ValueError as exc:
            st.error(str(exc))
    if "last_job" in st.session_state:
        show_result(service, st.session_state["last_job"])
    st.caption(
        "Temperature °C · precipitation mm per hour · wind m/s · humidity %. "
        "Count counts non-null hourly values. Summing precipitation across locations is a pooled total, not a typical site's rainfall."
    )


def show_result(service, job_id):
    meta = service.get_job_status(job_id)
    st.caption(f"Result dataset: {meta['dataset_version']} · Job: {job_id}")
    if meta["status"] == "failed":
        st.error(meta["error"])
    elif meta["status"] == "completed":
        st.success(
            f"{'Cache hit' if meta['cache_hit'] else 'New Spark result'} · "
            f"{meta['duration_seconds']:.3f}s · {meta['input_rows']:,} matching hourly rows"
        )
        result = service.load_job_result(job_id)
        if result.empty:
            st.info("The job completed with no matching data.")
        st.dataframe(result, hide_index=True)
        st.download_button(
            "Download result",
            result.to_csv(index=False),
            f"{job_id}.csv",
            "text/csv",
            key=f"result-{job_id}",
        )
        import json

        st.download_button(
            "Download provenance",
            json.dumps(meta, indent=2),
            f"{job_id}.json",
            "application/json",
            key=f"meta-{job_id}",
        )
    else:
        st.info(f"Job status: {meta['status']}")
    with st.expander("Reproducibility details"):
        st.json(meta)


def history(service):
    st.header("Job history")
    jobs = service.list_jobs()
    if not jobs:
        st.info("No analyses have been submitted yet.")
        return
    st.dataframe(
        pd.DataFrame(
            [
                {
                    k: j.get(k)
                    for k in [
                        "job_id",
                        "dataset_version",
                        "status",
                        "cache_hit",
                        "duration_seconds",
                        "input_rows",
                        "output_rows",
                    ]
                }
                for j in jobs
            ]
        ),
        hide_index=True,
    )
    selected = st.selectbox("Inspect a job", [j["job_id"] for j in jobs])
    show_result(service, selected)


def pipeline(store, service):
    st.header("Pipeline evidence")
    st.write(
        "Historical ingestion → raw Parquet → Scala Spark → published Parquet → dashboard / PySpark jobs → SQLite history"
    )
    metrics = store.manifest.get("pipeline")
    if metrics:
        st.json(metrics)
    else:
        st.info(
            "This snapshot predates processing metrics. Run make process and publish a new version to record them."
        )
    jobs = service.list_jobs()
    complete = [j for j in jobs if j["status"] == "completed"]
    st.metric("Completed requests", len(complete))
    if complete:
        st.metric("Cache hit rate", f"{sum(j['cache_hit'] for j in complete) / len(complete):.0%}")
    with st.expander("Dataset manifest and quality checks"):
        st.json(store.manifest)


def main():
    st.title("Big Weather")
    root = Path(os.getenv("WEATHER_PLATFORM_ROOT", "data/platform"))
    try:
        store = DatasetStore(root)
        service = AnalysisService(root, store.version)
    except (FileNotFoundError, ValueError) as exc:
        st.info(str(exc))
        st.code("make install-team\nmake process\nmake publish\nmake dashboard")
        return
    st.caption(
        f"Dataset {store.version} · {store.manifest['coverage']['start'][:10]} to "
        f"{store.manifest['coverage']['end'][:10]}"
    )
    page = st.sidebar.radio(
        "Navigate", ["Overview", "Exploration", "Custom analysis", "Job history", "Pipeline"]
    )
    if page == "Overview":
        overview(store)
    elif page == "Exploration":
        exploration(store)
    elif page == "Custom analysis":
        custom_analysis(service)
    elif page == "Job history":
        history(service)
    else:
        pipeline(store, service)
    st.divider()
    st.caption(store.manifest["attribution"])


main()
