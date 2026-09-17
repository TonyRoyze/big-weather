# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "altair>=6,<7",
#     "marimo>=0.24,<1",
#     "pandas>=2.2,<3",
#     "pyarrow>=17,<22",
#     "pyspark==4.0.1",
# ]
# ///
"""Interactive Spark + Altair starter for the Big Weather dataset."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell
def _():
    import atexit
    import json
    import os
    import sys
    from datetime import timedelta
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import pandas as pd
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F

    return SparkSession, F, Path, alt, atexit, json, mo, os, pd, sys, timedelta


@app.cell
def _(mo):
    mo.md(r"""
    # Big Weather: Spark + interactive Altair lab

    Use this notebook to explore the hourly weather data without collecting the full
    dataset into pandas. **Spark reads and filters the Parquet partitions, performs the
    aggregation, and only the compact result is sent to Altair.**

    The controls below are reactive. Try changing the locations, dates, time grain,
    metric, summary statistic, smoothing, and mark type. In the chart you can click a
    legend entry to isolate a location, hover for values, and drag/scroll to zoom.

    This is exploratory analysis. The raw-partition option may be incomplete while the
    downloader is running; use the published release for reportable findings.
    """)


@app.cell
def _(Path, mo, os):
    notebook_path = Path(mo.notebook_location())
    root_candidates = [
        Path.cwd(),
        *Path.cwd().parents,
        notebook_path.parent,
        *notebook_path.parents,
    ]
    project_root = next(
        (candidate for candidate in root_candidates if (candidate / "pyproject.toml").exists()),
        notebook_path.parent.parent,
    )
    raw_root = Path(
        os.getenv(
            "WEATHER_RAW_ROOT",
            str(project_root / "data" / "regional-2020-2025" / "raw"),
        )
    ).resolve()
    platform_root = Path(
        os.getenv("WEATHER_PLATFORM_ROOT", str(project_root / "data" / "platform"))
    ).resolve()

    published_available = (platform_root / "active.json").exists()
    raw_available = (raw_root / "locations" / "locations.parquet").exists() and any(
        (raw_root / "weather").glob("location_id=*/year=*/weather.parquet")
    )
    source_options = {}
    if published_available:
        source_options["Published, validated release"] = "published"
    if raw_available:
        source_options["Downloaded raw partitions (may be incomplete)"] = "raw"

    mo.stop(
        not source_options,
        mo.md(
            "No weather Parquet files were found. Run `make ingest-all`, or set "
            "`WEATHER_RAW_ROOT` / `WEATHER_PLATFORM_ROOT` to a dataset location."
        ),
    )
    source_choice = mo.ui.dropdown(
        options=source_options,
        value=(
            "Published, validated release"
            if published_available
            else "Downloaded raw partitions (may be incomplete)"
        ),
        label="Spark data source",
    )
    mo.vstack(
        [
            mo.md("## 1. Choose what Spark should ingest"),
            source_choice,
            mo.md(
                f"Raw root: `{raw_root}`  \nPublished root: `{platform_root}`"
            ),
        ]
    )
    return platform_root, project_root, raw_root, source_choice


@app.cell
def _(SparkSession, atexit, os, sys):
    if sys.platform == "darwin" and not os.getenv("JAVA_HOME"):
        for java_prefix in ("/opt/homebrew", "/usr/local"):
            java_candidate = (
                f"{java_prefix}/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"
            )
            if os.path.exists(f"{java_candidate}/bin/java"):
                os.environ["JAVA_HOME"] = java_candidate
                break

    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    spark_partitions = int(os.getenv("SPARK_PARTITIONS", "8"))
    spark = (
        SparkSession.builder.appName("Big Weather Altair Explorer")
        .master(os.getenv("SPARK_MASTER", "local[4]"))
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", str(spark_partitions))
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    _spark_shutdown = atexit.register(spark.stop)
    return spark, spark_partitions


@app.cell
def _(F, json, platform_root, raw_root, source_choice, spark):
    if source_choice.value == "published":
        active_release = json.loads((platform_root / "active.json").read_text())
        dataset_version = active_release.get("version") or active_release.get("active_version")
        if not dataset_version:
            raise ValueError("active.json does not contain a dataset version")
        release_root = platform_root / "releases" / dataset_version
        weather_sdf = spark.read.parquet(str(release_root / "enriched_weather"))
        locations_sdf = spark.read.parquet(str(release_root / "locations"))
        source_note = f"Published release `{dataset_version}`"
    else:
        raw_files = [
            str(path)
            for path in sorted(
                (raw_root / "weather").glob("location_id=*/year=*/weather.parquet")
            )
        ]
        locations_sdf = spark.read.parquet(str(raw_root / "locations" / "locations.parquet"))
        raw_weather_sdf = (
            spark.read.option("basePath", str(raw_root / "weather"))
            .parquet(*raw_files)
            .drop("year")
        )
        location_columns = [
            column
            for column in (
                "location_id",
                "name",
                "country",
                "region",
                "latitude",
                "longitude",
                "elevation_m",
            )
            if column in locations_sdf.columns
        ]
        weather_sdf = raw_weather_sdf.join(
            F.broadcast(locations_sdf.select(*location_columns)),
            on="location_id",
            how="left",
        )
        dataset_version = "in-progress-raw-download"
        source_note = "Raw downloaded partitions — coverage can be incomplete"

    weather_sdf = (
        weather_sdf.withColumn("timestamp", F.to_timestamp("timestamp"))
        .withColumn("date", F.to_date("timestamp"))
        .withColumn("year", F.year("timestamp"))
    )
    return dataset_version, locations_sdf, source_note, weather_sdf


@app.cell
def _(F, mo, pd, source_note, spark_partitions, weather_sdf):
    coverage_sdf = (
        weather_sdf.groupBy("location_id", "name")
        .agg(
            F.min("timestamp").alias("first_timestamp"),
            F.max("timestamp").alias("last_timestamp"),
            F.count("*").alias("hourly_rows"),
        )
        .orderBy("name")
    )
    coverage = coverage_sdf.toPandas()
    coverage["first_timestamp"] = pd.to_datetime(coverage["first_timestamp"], utc=True)
    coverage["last_timestamp"] = pd.to_datetime(coverage["last_timestamp"], utc=True)
    start_date = coverage["first_timestamp"].min().date()
    end_date = coverage["last_timestamp"].max().date()
    loaded_rows = int(coverage["hourly_rows"].sum())
    schema_table = pd.DataFrame(weather_sdf.dtypes, columns=["column", "spark_type"])

    mo.vstack(
        [
            mo.md(
                f"## 2. Ingestion check\n\n**{source_note}** · "
                f"**{loaded_rows:,} hourly rows** · **{len(coverage)} locations** · "
                f"{start_date} to {end_date} · {spark_partitions} shuffle partitions"
            ),
            mo.accordion(
                {
                    "Coverage by loaded location": mo.ui.table(coverage),
                    "Spark schema": mo.ui.table(schema_table),
                }
            ),
        ]
    )
    return coverage, end_date, loaded_rows, start_date


@app.cell
def _(coverage, end_date, mo, start_date):
    location_options = {
        f"{row['name']} ({row['location_id']})": row["location_id"]
        for _, row in coverage.iterrows()
    }
    default_locations = list(location_options)[:4]

    locations_control = mo.ui.multiselect(
        options=location_options,
        value=default_locations,
        max_selections=10,
        label="Locations (up to 10)",
    )
    date_control = mo.ui.date_range(
        start=start_date,
        stop=end_date,
        value=(start_date, end_date),
        label="Inclusive date range",
    )
    metric_control = mo.ui.dropdown(
        options={
            "Temperature (°C)": "temperature_2m",
            "Precipitation (mm)": "precipitation",
            "Relative humidity (%)": "relative_humidity_2m",
            "Wind speed at 10 m (m/s)": "wind_speed_10m",
            "Cloud cover (%)": "cloud_cover",
            "Surface pressure (hPa)": "surface_pressure",
        },
        value="Temperature (°C)",
        label="Metric",
    )
    statistic_control = mo.ui.dropdown(
        options={"Mean": "avg", "Minimum": "min", "Maximum": "max", "Sum": "sum"},
        value="Mean",
        label="Summary statistic",
    )
    grain_control = mo.ui.dropdown(
        options={"Day": "day", "Week": "week", "Month": "month"},
        value="Day",
        label="Time grain",
    )
    smoothing_control = mo.ui.slider(
        start=1,
        stop=30,
        step=1,
        value=7,
        show_value=True,
        label="Rolling periods",
    )
    mark_control = mo.ui.radio(
        options={"Line": "line", "Area": "area", "Points": "points"},
        value="Line",
        inline=True,
        label="Chart style",
    )

    mo.vstack(
        [
            mo.md("## 3. Shape the Spark query"),
            mo.hstack([metric_control, statistic_control, grain_control], widths="equal"),
            locations_control,
            date_control,
            mo.hstack([smoothing_control, mark_control], widths="equal"),
        ]
    )
    return (
        date_control,
        grain_control,
        locations_control,
        mark_control,
        metric_control,
        smoothing_control,
        statistic_control,
    )


@app.cell
def _(
    F,
    date_control,
    grain_control,
    locations_control,
    metric_control,
    mo,
    pd,
    statistic_control,
    timedelta,
    weather_sdf,
):
    mo.stop(not locations_control.value, mo.md("Select at least one location."))
    selected_start, selected_end = date_control.value
    exclusive_end = selected_end + timedelta(days=1)

    filtered_sdf = weather_sdf.filter(
        F.col("location_id").isin(locations_control.value)
        & (F.col("timestamp") >= F.lit(selected_start.isoformat()))
        & (F.col("timestamp") < F.lit(exclusive_end.isoformat()))
    )
    if grain_control.value == "day":
        bucket_expression = F.to_date("timestamp")
    else:
        bucket_expression = F.date_trunc(grain_control.value, "timestamp")

    spark_aggregations = {
        "avg": F.avg,
        "min": F.min,
        "max": F.max,
        "sum": F.sum,
    }
    aggregated_sdf = (
        filtered_sdf.withColumn("period", bucket_expression)
        .groupBy("period", "location_id", "name")
        .agg(
            spark_aggregations[statistic_control.value](metric_control.value).alias("value"),
            F.count(metric_control.value).alias("observations"),
        )
        .orderBy("period", "name")
    )
    plot_data = aggregated_sdf.toPandas()
    mo.stop(plot_data.empty, mo.md("No observations match this selection."))
    plot_data["period"] = pd.to_datetime(plot_data["period"], utc=True)
    return aggregated_sdf, plot_data, selected_end, selected_start


@app.cell
def _(plot_data, smoothing_control):
    chart_data = plot_data.copy()
    chart_data["smoothed_value"] = chart_data.groupby("location_id", sort=False)[
        "value"
    ].transform(
        lambda series: series.rolling(
            window=smoothing_control.value,
            min_periods=1,
        ).mean()
    )
    return (chart_data,)


@app.cell
def _(
    alt,
    chart_data,
    grain_control,
    mark_control,
    metric_control,
    mo,
    smoothing_control,
    statistic_control,
):
    metric_labels = {
        "temperature_2m": "Temperature (°C)",
        "precipitation": "Precipitation (mm)",
        "relative_humidity_2m": "Relative humidity (%)",
        "wind_speed_10m": "Wind speed at 10 m (m/s)",
        "cloud_cover": "Cloud cover (%)",
        "surface_pressure": "Surface pressure (hPa)",
    }
    statistic_labels = {"avg": "Mean", "min": "Minimum", "max": "Maximum", "sum": "Sum"}
    y_title = f"{statistic_labels[statistic_control.value]} {metric_labels[metric_control.value]}"

    location_pick = alt.selection_point(fields=["name"], bind="legend")
    base_chart = (
        alt.Chart(chart_data)
        .encode(
            x=alt.X("period:T", title=f"{grain_control.value.title()} (UTC)"),
            y=alt.Y("smoothed_value:Q", title=y_title, scale=alt.Scale(zero=False)),
            color=alt.Color("name:N", title="Location"),
            opacity=alt.condition(location_pick, alt.value(1.0), alt.value(0.12)),
            tooltip=[
                alt.Tooltip("name:N", title="Location"),
                alt.Tooltip("period:T", title="Period"),
                alt.Tooltip("value:Q", title="Raw aggregate", format=".2f"),
                alt.Tooltip("smoothed_value:Q", title="Smoothed", format=".2f"),
                alt.Tooltip("observations:Q", title="Hourly observations", format=","),
            ],
        )
        .add_params(location_pick)
        .properties(height=430)
    )
    if mark_control.value == "area":
        weather_chart = base_chart.mark_area(opacity=0.45)
    elif mark_control.value == "points":
        weather_chart = base_chart.mark_circle(size=45)
    else:
        weather_chart = base_chart.mark_line(point=False, strokeWidth=2)

    weather_chart = weather_chart.interactive(bind_y=False)
    weather_chart_widget = mo.ui.altair_chart(
        weather_chart,
        chart_selection=False,
        legend_selection=False,
    )
    mo.vstack(
        [
            mo.md(
                f"## 4. Explore the result\n\nShowing a **{smoothing_control.value}-period "
                "rolling mean** of Spark's aggregated result. Click the legend to isolate series; "
                "drag or scroll on the chart to zoom, and double-click to reset."
            ),
            weather_chart_widget,
        ]
    )
    return metric_labels, weather_chart, weather_chart_widget, y_title


@app.cell
def _(alt, chart_data, mo, y_title):
    value_brush = alt.selection_interval(encodings=["x"])
    histogram = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X("smoothed_value:Q", bin=alt.Bin(maxbins=35), title=y_title),
            y=alt.Y("count():Q", title="Number of location-periods"),
            color=alt.condition(value_brush, alt.value("#2563eb"), alt.value("#cbd5e1")),
            tooltip=[alt.Tooltip("count():Q", title="Periods")],
        )
        .add_params(value_brush)
        .properties(height=230, title="Distribution — drag across bars to highlight a range")
    )
    histogram_widget = mo.ui.altair_chart(
        histogram,
        chart_selection=False,
        legend_selection=False,
    )
    mo.vstack(
        [mo.md("### Distribution and aggregated data"), histogram_widget, mo.ui.table(chart_data)]
    )
    return histogram, histogram_widget


@app.cell
def _(aggregated_sdf, chart_data, dataset_version, mo, selected_end, selected_start):
    query_plan = aggregated_sdf._jdf.queryExecution().simpleString()
    export_name = f"weather-summary-{selected_start}-{selected_end}.csv"
    mo.vstack(
        [
            mo.md(
                "## 5. Keep the evidence\n\nThe download contains only the selected Spark "
                f"summary and is tagged here with dataset version `{dataset_version}`."
            ),
            mo.download(
                data=chart_data.to_csv(index=False).encode(),
                filename=export_name,
                label="Download selected summary as CSV",
            ),
            mo.accordion({"Spark physical plan": mo.md(f"```text\n{query_plan}\n```")}),
        ]
    )
    return (query_plan,)


if __name__ == "__main__":
    app.run()
