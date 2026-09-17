"""Run with `make dashboard`. Extend the page functions without importing Spark."""

import json
import os
from datetime import timedelta
from pathlib import Path
from time import perf_counter

import pandas as pd
import plotly.express as px
import streamlit as st
from weather_analysis import AnalysisService, DatasetStore
from weather_analysis.charts import (
    METRIC_LABELS,
    load_chart_data,
    load_preview_data,
    preview_catalog,
)
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


@st.cache_data(show_spinner=False, max_entries=64, ttl=3600)
def read_chart(root, version, fingerprint, locations, start, end, metrics):
    return load_chart_data(DatasetStore(root, version), locations, start, end, metrics)


def on_demand_charts(store):
    st.header("On-demand charts")
    st.write("Slide to a date range, choose locations, then load your charts. Drag a chart to pan.")
    fingerprint = store.manifest["fingerprint"]
    locations = read_table(str(store.root), store.version, fingerprint, "locations")
    names = dict(zip(locations.location_id, locations.name))
    coverage = store.manifest["coverage"]
    start = pd.Timestamp(coverage["start"]).date()
    end = pd.Timestamp(coverage["end"]).date()
    with st.form("chart_request"):
        selected = st.multiselect(
            "Chart locations (up to 10)", sorted(names), default=sorted(names)[:1],
            format_func=lambda value: names[value], max_selections=10,
        )
        metrics = st.multiselect(
            "Chart metrics", list(METRIC_LABELS), default=list(METRIC_LABELS)[:2],
            format_func=METRIC_LABELS.get,
        )
        if start < end:
            dates = st.slider(
                "Requested dates (UTC)", min_value=start, max_value=end,
                value=(max(start, end - timedelta(days=89)), end), step=timedelta(days=1),
            )
        else:
            dates = (start, end)
            st.caption(f"Available date: {start}")
        submitted = st.form_submit_button("Load charts")
    state_key = f"chart-request-{store.version}-{fingerprint}"
    if submitted:
        if not selected or not metrics:
            st.warning("Choose at least one location and metric.")
            return
        st.session_state[state_key] = (tuple(sorted(selected)), dates, tuple(sorted(metrics)))
    if state_key not in st.session_state:
        st.info("Choose your range and click Load charts to request data.")
        return
    selected, dates, metrics = st.session_state[state_key]
    started = perf_counter()
    with st.spinner("Loading selected weather data…"):
        frame, rows, bucket_days = read_chart(
            str(store.root), store.version, fingerprint, selected, *dates, metrics,
        )
    st.caption(
        f"Loaded request: {dates[0]} to {dates[1]} · {rows:,} location-days · "
        f"{len(frame):,} plotted rows · {perf_counter() - started:.3f}s query/cache retrieval. "
        "Change controls and click Load charts to update."
    )
    if frame.empty:
        st.info("No observations match this request.")
        return
    if bucket_days > 1:
        st.caption(
            f"Charts show {bucket_days}-day means of available daily values; rainfall is a "
            "mean daily total. Request a shorter range for daily detail."
        )
    frame["Location"] = frame.location_id.map(names)
    for metric in metrics:
        fig = px.line(frame, x="date", y=metric, color="Location",
                      labels={"date": "Date (UTC)", metric: METRIC_LABELS[metric]})
        fig.update_layout(dragmode="pan", hovermode="x unified")
        fig.update_xaxes(rangeslider_visible=True)
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": True}, key=metric)
    st.caption("Chart sliders zoom within the loaded request. Data source: published study snapshot.")


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


def evidence(store):
    st.header("Evidence views")
    st.write(
        "Explore the published annual-change and elevation lapse-rate outputs. "
        "These are descriptive associations, not causal estimates."
    )
    fingerprint = store.manifest["fingerprint"]
    yearly = read_table(str(store.root), store.version, fingerprint, "yearly_metrics")
    lapse = read_table(str(store.root), store.version, fingerprint, "lapse_rates")
    tab1, tab2 = st.tabs(["Annual temperature", "Seasonal lapse rates"])
    with tab1:
        locations = sorted(yearly.location_id.unique())
        selected = st.multiselect("Locations", locations, default=locations)
        subset = yearly[yearly.location_id.isin(selected)].copy()
        if subset.empty:
            st.info("No annual metrics match the selected locations.")
        else:
            subset["year"] = subset["year"].astype(str)
            st.plotly_chart(
                px.line(
                    subset.sort_values("year"),
                    x="year",
                    y="annual_avg_temperature_c",
                    color="location_id",
                    markers=True,
                    labels={
                        "year": "Year",
                        "annual_avg_temperature_c": "Annual mean temperature (°C)",
                        "location_id": "Location",
                    },
                ),
                use_container_width=True,
            )
            st.plotly_chart(
                px.bar(
                    subset.dropna(subset=["temperature_yoy_change_c"]),
                    x="year",
                    y="temperature_yoy_change_c",
                    color="location_id",
                    barmode="group",
                    labels={
                        "year": "Year",
                        "temperature_yoy_change_c": "Year-over-year change (°C)",
                        "location_id": "Location",
                    },
                ),
                use_container_width=True,
            )
            st.caption(
                "Year-over-year change compares each location with its previous observed year; "
                "it is not a climate-normal anomaly."
            )
            st.dataframe(subset, hide_index=True)
    with tab2:
        if lapse.empty:
            st.info("No lapse-rate model could be fitted for this dataset.")
        else:
            st.plotly_chart(
                px.bar(
                    lapse.sort_values("season"),
                    x="season",
                    y="lapse_rate_c_per_km",
                    labels={
                        "season": "Local season",
                        "lapse_rate_c_per_km": "Temperature slope (°C/km)",
                    },
                    hover_data=["r2", "rmse_c", "sample_size"],
                ),
                use_container_width=True,
            )
            st.caption(
                "A negative value indicates lower modeled temperature at higher elevation. "
                "Repeated daily observations and geography limit causal interpretation."
            )
            st.dataframe(lapse, hide_index=True)


def pipeline(store, service):
    st.header("Pipeline evidence")
    st.write(
        "Historical ingestion → raw Parquet → PySpark → published Parquet → dashboard / PySpark jobs → SQLite history"
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


def download_preview(root):
    st.header("Regional study download")
    status_path = root / "ingestion-status.json"
    if status_path.exists():
        status = json.loads(status_path.read_text())
        done, total = status.get("completed_chunks", 0), status.get("expected_chunks", 600)
        a, b, c = st.columns(3)
        a.metric("Completed downloads", f"{done} / {total}")
        b.metric("Downloaded hourly rows", f"{status.get('completed_rows', 0):,}")
        c.metric("Download status", status.get("status", "unknown").capitalize())
        st.progress(min(1.0, done / total) if total else 0.0)
        if window := status.get("active_window"):
            st.caption(
                f"Current window: {window['start']} to {window['end']} · "
                f"{window['completed_locations']} / {window['total_locations']} locations"
            )
        if status.get("reason"):
            st.caption(status["reason"])
    st.button("Refresh download progress")
    chunks = preview_catalog(root)
    if not chunks:
        st.info("No completed downloads are available to preview yet.")
        st.code("make ingest-all\nmake process\nmake publish")
        return
    st.warning(
        "Unpublished preview — incomplete study and raw data. These charts are for early "
        "inspection, not final findings. Published analyses become available after processing."
    )
    locations = pd.read_parquet(root / "raw/locations")
    names = dict(zip(locations.location_id, locations.name))
    available = sorted({c["location_id"] for c in chunks})
    selected = st.multiselect("Preview locations", available, default=available[:1],
                              format_func=lambda value: names.get(value, value), max_selections=10)
    if not selected:
        st.info("Choose a location to preview.")
        return
    chosen = [c for c in chunks if c["location_id"] in selected]
    first = min(pd.Timestamp(c["start"]).date() for c in chosen)
    last = max(pd.Timestamp(c["end"]).date() for c in chosen)
    with st.form("preview_request"):
        dates = st.date_input("Preview dates (UTC; up to 93 days)",
                              (max(first, last - timedelta(days=29)), last),
                              min_value=first, max_value=last)
        metric = st.selectbox("Preview metric", list(METRIC_LABELS)[:3],
                              format_func=METRIC_LABELS.get)
        submitted = st.form_submit_button("Load preview")
    if submitted:
        if len(dates) != 2:
            st.warning("Select a start and end date.")
            return
        try:
            with st.spinner("Reading completed downloads…"):
                frame = load_preview_data(chosen, selected, *dates, metric)
        except ValueError as exc:
            st.warning(str(exc))
            return
        if frame.empty:
            st.info("No downloaded observations match this request. Try another date or location.")
            return
        frame["Location"] = frame.location_id.map(names)
        st.plotly_chart(px.line(frame, x="date", y=metric, color="Location", markers=True,
                               labels={"date": "Date (UTC)", metric: METRIC_LABELS[metric]}),
                        use_container_width=True)
        st.caption("Daily values require 24 non-null hourly readings. Missing downloads are not zeros.")
        st.dataframe(frame, hide_index=True)
    with st.expander("Finish the study"):
        st.write("Once ingestion is complete, process and publish the regional study, then refresh this page.")
        st.code("make process\nmake publish")


def main():
    st.title("Big Weather")
    project_root = Path(__file__).resolve().parents[1]
    root = Path(os.getenv("WEATHER_PLATFORM_ROOT", str(project_root / "data/platform")))
    regional_root = Path(os.getenv("WEATHER_REGIONAL_ROOT",
                                   str(project_root / "data/regional-2020-2025")))
    try:
        store = DatasetStore(root)
        service = AnalysisService(root, store.version)
    except (FileNotFoundError, ValueError) as exc:
        st.info(str(exc))
        try:
            download_preview(regional_root)
        except (OSError, ValueError, KeyError) as preview_error:
            st.error(f"Unable to read download progress: {preview_error}")
            st.code("make ingest-all\nmake process\nmake publish")
        return
    st.caption(
        f"Dataset {store.version} · {store.manifest['coverage']['start'][:10]} to "
        f"{store.manifest['coverage']['end'][:10]}"
    )
    page = st.sidebar.radio(
        "Navigate",
        ["Overview", "On-demand charts", "Exploration", "Evidence", "Custom analysis", "Job history", "Pipeline"],
    )
    if page == "Overview":
        overview(store)
    elif page == "On-demand charts":
        on_demand_charts(store)
    elif page == "Exploration":
        exploration(store)
    elif page == "Custom analysis":
        custom_analysis(service)
    elif page == "Job history":
        history(service)
    elif page == "Evidence":
        evidence(store)
    else:
        pipeline(store, service)
    st.divider()
    st.caption(store.manifest["attribution"])


main()
