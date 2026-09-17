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

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="full")


@app.cell
def _():
    from pathlib import Path as _Path



    _groups = {
        "thermal": (
            "Thermal relationships",
            [
                "temperature_2m",
                "dew_point_2m",
                "apparent_temperature",
                # "wet_bulb_temperature_2m",
                "soil_temperature_0_to_7cm",
                "soil_temperature_7_to_28cm",
                "soil_temperature_28_to_100cm",
                "soil_temperature_100_to_255cm",
            ],
        ),
        "hydrology": (
            "Moisture and precipitation relationships",
            [
                "relative_humidity_2m",
                "precipitation",
                "rain",
                # "snowfall",
                # "snow_depth",
                "et0_fao_evapotranspiration",
                "vapour_pressure_deficit",
                # "total_column_integrated_water_vapour",
            ],
        ),
        "wind": (
            "Wind relationships",
            [
                # "wind_speed_10m",
                "wind_speed_100m",
                # "wind_direction_10m",
                # "wind_direction_100m",
                # "wind_gusts_10m",
            ],
        ),
        "clouds_weather": (
            "Cloud and weather-code relationships",
            [
                # "weather_code",
                "cloud_cover",
                # "cloud_cover_low",
                # "cloud_cover_mid",
                # "cloud_cover_high",
            ],
        ),
        "pressure_boundary": (
            "Pressure and boundary-layer relationships",
            ["pressure_msl", "surface_pressure", "boundary_layer_height"],
        ),
        "soil_moisture": (
            "Soil-moisture relationships",
            [
                "soil_moisture_0_to_7cm",
                "soil_moisture_7_to_28cm",
                "soil_moisture_28_to_100cm",
                "soil_moisture_100_to_255cm",
            ],
        ),
        "radiation": (
            "Radiation and daylight relationships",
            [
                # "is_day",
                # "sunshine_duration",
                # "shortwave_radiation",
                "direct_radiation",
                # "diffuse_radiation",
                # "direct_normal_irradiance",
                # "global_tilted_irradiance",
                # "terrestrial_radiation",
            ],
        ),
        "radiation_instant": (
            "Instantaneous-radiation relationships",
            [
                # "shortwave_radiation_instant",
                # "direct_radiation_instant",
                # "diffuse_radiation_instant",
                # "direct_normal_irradiance_instant",
                # "global_tilted_irradiance_instant",
                # "terrestrial_radiation_instant",
            ],
        ),
    }
    _notebook_key = _Path(__file__).stem
    suite_title, focus_group = _groups[_notebook_key]
    all_variables = [
        "temperature_2m",
        "dew_point_2m",
        "apparent_temperature",
        # "wet_bulb_temperature_2m",
        "soil_temperature_0_to_7cm",
        # "soil_temperature_7_to_28cm",
        # "soil_temperature_28_to_100cm",
        # "soil_temperature_100_to_255cm",
        "relative_humidity_2m",
        "precipitation",
        "rain",
        # "snowfall",
        # "snow_depth",
        "et0_fao_evapotranspiration",
        "vapour_pressure_deficit",
        # "total_column_integrated_water_vapour",
        "wind_speed_100m",
        # "wind_direction_10m",
        # "wind_direction_100m",
        # "wind_gusts_10m",
        "cloud_cover",
        # "weather_code",
        # "cloud_cover_low",
        # "cloud_cover_mid",
        # "cloud_cover_high",
        "pressure_msl",
        "surface_pressure",
        "boundary_layer_height",
        "soil_moisture_0_to_7cm",
        # "soil_moisture_7_to_28cm",
        # "soil_moisture_28_to_100cm",
        # "soil_moisture_100_to_255cm",
        # "is_day",
        "sunshine_duration",
        # "shortwave_radiation",
        "direct_radiation",
        # "diffuse_radiation",
        # "direct_normal_irradiance",
        # "global_tilted_irradiance",
        # "terrestrial_radiation",
        # "shortwave_radiation_instant",
        # "direct_radiation_instant",
        # "diffuse_radiation_instant",
        # "direct_normal_irradiance_instant",
        # "global_tilted_irradiance_instant",
        # "terrestrial_radiation_instant",
    ]
    focus_group = [variable for variable in focus_group if variable in all_variables]
    return all_variables, focus_group, suite_title


@app.cell
def _():
    import atexit
    import math
    import os
    import sys
    from datetime import timedelta
    from pathlib import Path

    import altair as alt
    import marimo as mo
    import pandas as pd
    from pyspark.sql import SparkSession
    from pyspark.sql import functions as F
    from weather_analysis import DatasetStore

    return (
        DatasetStore,
        F,
        Path,
        SparkSession,
        alt,
        atexit,
        math,
        mo,
        os,
        pd,
        sys,
        timedelta,
    )


@app.cell
def _(focus_group, mo, suite_title):
    focus_list = ", ".join(f"`{variable}`" for variable in focus_group)
    mo.md(
        f"""
        # {suite_title}

        Focus variables in this notebook: {focus_list}.

        Pick one focus variable and Spark will compare it with the **other 16 selected
        weather variables**. The first view ranks Pearson
        correlations; the second lets you inspect any pair as a sampled scatterplot.

        Correlation is descriptive, not causal. Weather variables are autocorrelated,
        seasonal, and often derived from each other. `weather_code` is categorical,
        wind direction is circular, and `is_day` is binary, so interpret their Pearson
        coefficients cautiously.
        """
    )
    return


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
        notebook_path.parent.parent.parent,
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
            "`WEATHER_RAW_ROOT` / `WEATHER_PLATFORM_ROOT`."
        ),
    )
    source_control = mo.ui.dropdown(
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
            mo.md("## 1. Data source"),
            source_control,
            mo.md(f"Raw: `{raw_root}`  \nPublished: `{platform_root}`"),
        ]
    )
    return platform_root, raw_root, source_control


@app.cell
def _(SparkSession, atexit, os, sys):
    if sys.platform == "darwin" and not os.getenv("JAVA_HOME"):
        for java_prefix in ("/opt/homebrew", "/usr/local"):
            java_candidate = f"{java_prefix}/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home"
            if os.path.exists(f"{java_candidate}/bin/java"):
                os.environ["JAVA_HOME"] = java_candidate
                break

    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    spark_partitions = int(os.getenv("SPARK_PARTITIONS", "8"))
    spark = (
        SparkSession.builder.appName("Big Weather Relationship Lab")
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
def _(
    DatasetStore,
    F,
    all_variables,
    platform_root,
    raw_root,
    source_control,
    spark,
):
    if source_control.value == "published":
        store = DatasetStore(platform_root)
        dataset_version = store.version
        weather_sdf = spark.read.parquet(str(store.table_path("enriched_weather")))
        locations_sdf = spark.read.parquet(str(store.table_path("locations")))
        source_note = f"Published release `{dataset_version}`"
    else:
        raw_files = [
            str(path)
            for path in sorted((raw_root / "weather").glob("location_id=*/year=*/weather.parquet"))
        ]
        locations_sdf = spark.read.parquet(str(raw_root / "locations" / "locations.parquet"))
        raw_weather_sdf = (
            spark.read.option("basePath", str(raw_root / "weather"))
            .parquet(*raw_files)
            .drop("year")
        )
        location_columns = [
            column
            for column in ("location_id", "name", "country", "region", "elevation_m")
            if column in locations_sdf.columns
        ]
        weather_sdf = raw_weather_sdf.join(
            F.broadcast(locations_sdf.select(*location_columns)),
            on="location_id",
            how="left",
        )
        dataset_version = "in-progress-raw-download"
        source_note = "Raw downloaded partitions — coverage can be incomplete"

    missing_variables = [
        variable for variable in all_variables if variable not in weather_sdf.columns
    ]
    if missing_variables:
        raise ValueError(f"Dataset is missing required variables: {missing_variables}")
    weather_sdf = weather_sdf.withColumn("timestamp", F.to_timestamp("timestamp"))
    return dataset_version, source_note, weather_sdf


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
    mo.vstack(
        [
            mo.md(
                f"**{source_note}** · **{loaded_rows:,} rows** · "
                f"**{len(coverage)} loaded locations** · {start_date} to {end_date} · "
                f"{spark_partitions} Spark shuffle partitions"
            ),
            mo.accordion({"Coverage by location": mo.ui.table(coverage)}),
        ]
    )
    return coverage, end_date, start_date


@app.cell
def _(coverage, end_date, focus_group, mo, start_date):
    location_options = {
        f"{row['name']} ({row['location_id']})": row["location_id"]
        for _, row in coverage.iterrows()
    }
    focus_control = mo.ui.dropdown(
        options=focus_group,
        value=focus_group[0],
        label="Focus variable",
        searchable=True,
    )
    locations_control = mo.ui.multiselect(
        options=location_options,
        value=list(location_options)[:4],
        max_selections=12,
        label="Locations (up to 12)",
    )
    date_control = mo.ui.date_range(
        start=start_date,
        stop=end_date,
        value=(start_date, end_date),
        label="Inclusive date range",
    )
    grain_control = mo.ui.radio(
        options={
            "Hourly readings": "hour",
            "Daily means": "day",
            "Weekly means": "week",
            "Monthly means": "month",
        },
        value="Daily means",
        inline=True,
        label="Analysis grain",
    )
    top_n_control = mo.ui.slider(
        start=8,
        stop=16,
        step=1,
        value=16,
        show_value=True,
        label="Relationships to display",
    )
    mo.vstack(
        [
            mo.md("## 2. Choose the analysis slice"),
            mo.hstack([focus_control, top_n_control], widths="equal"),
            locations_control,
            date_control,
            grain_control,
            mo.md(
                "Daily/weekly/monthly modes average each hourly field within each "
                "location-period before correlation. Hourly mode uses retained observations "
                "directly. No missing values are imputed."
            ),
        ]
    )
    return (
        date_control,
        focus_control,
        grain_control,
        locations_control,
        top_n_control,
    )


@app.cell
def _(
    F,
    all_variables,
    date_control,
    grain_control,
    locations_control,
    mo,
    timedelta,
    weather_sdf,
):
    mo.stop(not locations_control.value, mo.md("Select at least one location."))
    selected_start, selected_end = date_control.value
    exclusive_end = selected_end + timedelta(days=1)
    sliced_sdf = weather_sdf.filter(
        F.col("location_id").isin(locations_control.value)
        & (F.col("timestamp") >= F.lit(selected_start.isoformat()))
        & (F.col("timestamp") < F.lit(exclusive_end.isoformat()))
    )
    if grain_control.value == "hour":
        analysis_sdf = sliced_sdf.select(
            "timestamp", "location_id", "name", "region", "elevation_m", *all_variables
        )
    else:
        period_expression = (
            F.to_date("timestamp")
            if grain_control.value == "day"
            else F.date_trunc(grain_control.value, "timestamp")
        )
        analysis_sdf = (
            sliced_sdf.withColumn("timestamp", period_expression)
            .groupBy("timestamp", "location_id", "name", "region", "elevation_m")
            .agg(*[F.avg(variable).alias(variable) for variable in all_variables])
        )
    return analysis_sdf, selected_end, selected_start, sliced_sdf


@app.cell
def _(F, all_variables, analysis_sdf, focus_control, math, pd):
    focus_variable = focus_control.value
    comparison_variables = [variable for variable in all_variables if variable != focus_variable]
    correlation_expressions = []
    for index, variable in enumerate(comparison_variables):
        valid_pair = F.col(focus_variable).isNotNull() & F.col(variable).isNotNull()
        paired_focus = F.when(valid_pair, F.col(focus_variable))
        paired_comparison = F.when(valid_pair, F.col(variable))
        correlation_expressions.append(
            F.try_divide(
                F.covar_samp(paired_focus, paired_comparison),
                F.stddev_samp(paired_focus) * F.stddev_samp(paired_comparison),
            ).alias(f"correlation_{index}")
        )
    pair_count_expressions = [
        F.sum(
            F.when(
                F.col(focus_variable).isNotNull() & F.col(variable).isNotNull(),
                1,
            ).otherwise(0)
        ).alias(f"pairs_{index}")
        for index, variable in enumerate(comparison_variables)
    ]
    correlation_row = analysis_sdf.agg(*correlation_expressions, *pair_count_expressions).first()
    relationship_rows = []
    for index, variable in enumerate(comparison_variables):
        correlation = correlation_row[f"correlation_{index}"]
        finite_correlation = (
            float(correlation)
            if correlation is not None and math.isfinite(float(correlation))
            else None
        )
        relationship_rows.append(
            {
                "variable": variable,
                "correlation": finite_correlation,
                "absolute_correlation": (
                    abs(finite_correlation) if finite_correlation is not None else None
                ),
                "pair_count": int(correlation_row[f"pairs_{index}"] or 0),
            }
        )
    relationships = pd.DataFrame(relationship_rows).sort_values(
        ["absolute_correlation", "variable"], ascending=[False, True], na_position="last"
    )
    return focus_variable, relationships


@app.cell
def _(alt, focus_variable, mo, relationships, top_n_control):
    ranked_relationships = relationships.head(top_n_control.value).sort_values(
        "correlation", na_position="first"
    )
    correlation_chart = (
        alt.Chart(ranked_relationships)
        .mark_bar()
        .encode(
            x=alt.X(
                "correlation:Q",
                title=f"Pearson correlation with {focus_variable}",
                scale=alt.Scale(domain=[-1, 1]),
            ),
            y=alt.Y("variable:N", sort=None, title=None),
            color=alt.Color(
                "correlation:Q",
                scale=alt.Scale(domain=[-1, 0, 1], range=["#b91c1c", "#e5e7eb", "#1d4ed8"]),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip("variable:N", title="Variable"),
                alt.Tooltip("correlation:Q", title="Pearson r", format=".3f"),
                alt.Tooltip("pair_count:Q", title="Valid pairs", format=","),
            ],
        )
        .properties(height=max(280, 24 * len(ranked_relationships)))
    )
    correlation_widget = mo.ui.altair_chart(
        correlation_chart,
        chart_selection=False,
        legend_selection=False,
    )
    mo.vstack(
        [
            mo.md(
                f"## 3. `{focus_variable}` versus every other variable\n\n"
                "Blue is positive, red is negative. Constant or unavailable pairs have no "
                "finite coefficient and remain in the table below."
            ),
            correlation_widget,
            mo.ui.table(relationships),
        ]
    )
    return


@app.cell
def _(mo, relationships):
    ordered_comparisons = relationships["variable"].tolist()
    comparison_controls = mo.ui.multiselect(
        options=ordered_comparisons,
        value=ordered_comparisons[:6],
        max_selections=12,
        label="Variables to show in the scatterplot grid (up to 12)",
    )
    sample_size_control = mo.ui.slider(
        steps=[1000, 2500, 5000, 10000],
        value=2500,
        show_value=True,
        label="Maximum sampled periods",
    )
    grid_columns_control = mo.ui.slider(
        start=2,
        stop=4,
        step=1,
        value=3,
        show_value=True,
        label="Grid columns",
    )
    mo.vstack(
        [
            mo.md(
                "## 4. Choose scatterplots\n\nSelect the variables first; the grid and "
                "Spark projection update together. Defaults are the six strongest finite "
                "relationships in the current slice."
            ),
            comparison_controls,
            mo.hstack([sample_size_control, grid_columns_control], widths="equal"),
        ]
    )
    return comparison_controls, grid_columns_control, sample_size_control


@app.cell
def _(
    analysis_sdf,
    comparison_controls,
    focus_variable,
    grain_control,
    mo,
    pd,
    sample_size_control,
):
    selected_comparisons = comparison_controls.value
    mo.stop(not selected_comparisons, mo.md("Select at least one comparison variable."))
    sampling_fraction = {
        "hour": 0.05,
        "day": 0.5,
        "week": 1.0,
        "month": 1.0,
    }[grain_control.value]
    grid_source_sdf = analysis_sdf.select(
        "timestamp", "location_id", "name", focus_variable, *selected_comparisons
    ).dropna(subset=[focus_variable])
    sampled_grid_sdf = grid_source_sdf.sample(False, sampling_fraction, seed=42).limit(
        sample_size_control.value
    )
    scatter_wide = sampled_grid_sdf.toPandas()
    mo.stop(scatter_wide.empty, mo.md("No valid observations in this slice."))
    scatter_long = (
        scatter_wide.melt(
            id_vars=["timestamp", "location_id", "name", focus_variable],
            value_vars=selected_comparisons,
            var_name="comparison_variable",
            value_name="comparison_value",
        )
        .dropna(subset=["comparison_value"])
        .reset_index(drop=True)
    )
    scatter_long["timestamp"] = pd.to_datetime(scatter_long["timestamp"], utc=True)
    mo.stop(scatter_long.empty, mo.md("The selected pairs contain no valid observations."))
    return scatter_long, selected_comparisons


@app.cell
def _(alt, focus_variable, grid_columns_control, mo, scatter_long):
    location_pick = alt.selection_point(fields=["name"], bind="legend")
    points = (
        alt.Chart(scatter_long)
        .mark_circle(size=28)
        .encode(
            x=alt.X(
                "comparison_value:Q",
                title=None,
                scale=alt.Scale(zero=False),
            ),
            y=alt.Y(f"{focus_variable}:Q", scale=alt.Scale(zero=False)),
            color=alt.Color("name:N", title="Location"),
            opacity=alt.condition(location_pick, alt.value(0.55), alt.value(0.04)),
            tooltip=[
                alt.Tooltip("name:N", title="Location"),
                alt.Tooltip("timestamp:T", title="Period"),
                alt.Tooltip("comparison_variable:N", title="Compared with"),
                alt.Tooltip("comparison_value:Q", title="X value", format=".3f"),
                alt.Tooltip(f"{focus_variable}:Q", format=".3f"),
            ],
        )
        .add_params(location_pick)
    )
    scatter_chart = (
        alt.layer(points)
        .properties(width=270, height=230)
        .facet(
            facet=alt.Facet("comparison_variable:N", title=None),
            columns=grid_columns_control.value,
        )
        .resolve_scale(x="independent", y="shared")
        .properties(title=f"{focus_variable}: selected relationships")
    )
    scatter_widget = mo.ui.altair_chart(
        scatter_chart,
        chart_selection=False,
        legend_selection=False,
    )
    mo.vstack(
        [
            mo.md(
                "Each panel has its own x-scale and a shared focus-variable y-scale. Click a "
                "legend item to isolate a location and hover for exact values."
            ),
            scatter_widget,
        ]
    )
    return


@app.cell
def _(F, all_variables, sliced_sdf):
    elevation_sdf = (
        sliced_sdf.groupBy("location_id", "name", "region", "elevation_m")
        .agg(*[F.avg(variable).alias(variable) for variable in all_variables])
        .orderBy("elevation_m", "name")
    )
    elevation_wide = elevation_sdf.toPandas().dropna(subset=["elevation_m"])
    elevation_long = (
        elevation_wide.melt(
            id_vars=["location_id", "name", "region", "elevation_m"],
            value_vars=all_variables,
            var_name="variable",
            value_name="mean_hourly_value",
        )
        .dropna(subset=["mean_hourly_value"])
        .reset_index(drop=True)
    )
    return (elevation_long,)


@app.cell
def _(alt, elevation_long, grid_columns_control, mo):
    elevation_points = (
        alt.Chart(elevation_long)
        .mark_circle(size=70, opacity=0.72)
        .encode(
            x=alt.X("elevation_m:Q", title="Elevation (m)", scale=alt.Scale(zero=False)),
            y=alt.Y(
                "mean_hourly_value:Q",
                title="Mean hourly value",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color("region:N", title="Region"),
            tooltip=[
                alt.Tooltip("name:N", title="Location"),
                alt.Tooltip("region:N", title="Region"),
                alt.Tooltip("elevation_m:Q", title="Elevation (m)", format=",.0f"),
                alt.Tooltip("variable:N", title="Variable"),
                alt.Tooltip("mean_hourly_value:Q", title="Mean", format=".3f"),
            ],
        )
    )
    elevation_trends = (
        alt.Chart(elevation_long)
        .transform_regression(
            "elevation_m",
            "mean_hourly_value",
            groupby=["variable"],
        )
        .mark_line(color="#111827", strokeWidth=2.5)
        .encode(
            x=alt.X("elevation_m:Q"),
            y=alt.Y("mean_hourly_value:Q"),
        )
    )
    elevation_chart = (
        alt.layer(elevation_points, elevation_trends)
        .properties(width=270, height=230)
        .facet(
            facet=alt.Facet("variable:N", title=None),
            columns=grid_columns_control.value,
        )
        .resolve_scale(x="shared", y="independent")
        .properties(title="How each selected variable changes with elevation")
    )
    elevation_widget = mo.ui.altair_chart(
        elevation_chart,
        chart_selection=False,
        legend_selection=False,
    )
    mo.vstack(
        [
            mo.md(
                "## 5. Elevation relationships\n\nEach point is one location's mean over "
                "the selected dates. Panels share the elevation axis but use independent y-scales. "
                "The black line is a simple pooled linear fit; regional and latitude differences "
                "can confound the apparent elevation relationship."
            ),
            elevation_widget,
        ]
    )
    return


@app.cell
def _(mo):
    time_grain_control = mo.ui.radio(
        options={"Weekly": "week", "Monthly": "month", "Yearly": "year"},
        value="Monthly",
        inline=True,
        label="Time-series grain",
    )
    mo.vstack(
        [
            mo.md(
                "## 6. Change over time\n\nThe time-series grid uses the focus variable "
                "plus the variables selected for the scatterplot grid."
            ),
            time_grain_control,
        ]
    )
    return (time_grain_control,)


@app.cell
def _(
    F,
    focus_variable,
    pd,
    selected_comparisons,
    sliced_sdf,
    time_grain_control,
):
    temporal_variables = list(dict.fromkeys([focus_variable, *selected_comparisons]))
    elevation_band = (
        F.when(F.col("elevation_m") < 200, "Lowland (<200 m)")
        .when(F.col("elevation_m") < 1000, "Midland (200–999 m)")
        .when(F.col("elevation_m") < 3000, "Highland (1000–2999 m)")
        .otherwise("Alpine (≥3000 m)")
    )
    location_period_sdf = (
        sliced_sdf.withColumn(
            "period",
            F.date_trunc(time_grain_control.value, "timestamp"),
        )
        .withColumn("elevation_band", elevation_band)
        .groupBy("period", "location_id", "elevation_band")
        .agg(*[F.avg(variable).alias(variable) for variable in temporal_variables])
    )
    band_period_sdf = (
        location_period_sdf.groupBy("period", "elevation_band")
        .agg(
            *[F.avg(variable).alias(variable) for variable in temporal_variables],
            F.countDistinct("location_id").alias("locations"),
        )
        .orderBy("period", "elevation_band")
    )
    temporal_wide = band_period_sdf.toPandas()
    temporal_wide["period"] = pd.to_datetime(temporal_wide["period"], utc=True)
    temporal_long = (
        temporal_wide.melt(
            id_vars=["period", "elevation_band", "locations"],
            value_vars=temporal_variables,
            var_name="variable",
            value_name="mean_value",
        )
        .dropna(subset=["mean_value"])
        .reset_index(drop=True)
    )
    return (temporal_long,)


@app.cell
def _(alt, grid_columns_control, mo, temporal_long, time_grain_control):
    band_order = [
        "Lowland (<200 m)",
        "Midland (200–999 m)",
        "Highland (1000–2999 m)",
        "Alpine (≥3000 m)",
    ]
    band_pick = alt.selection_point(fields=["elevation_band"], bind="legend")
    temporal_lines = (
        alt.Chart(temporal_long)
        .mark_line(point=True, strokeWidth=2)
        .encode(
            x=alt.X("period:T", title=f"{time_grain_control.value.title()} (UTC)"),
            y=alt.Y("mean_value:Q", title="Equal-location mean", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "elevation_band:N",
                title="Elevation band",
                sort=band_order,
            ),
            opacity=alt.condition(band_pick, alt.value(1.0), alt.value(0.12)),
            tooltip=[
                alt.Tooltip("variable:N", title="Variable"),
                alt.Tooltip("period:T", title="Period"),
                alt.Tooltip("elevation_band:N", title="Elevation band"),
                alt.Tooltip("mean_value:Q", title="Mean", format=".3f"),
                alt.Tooltip("locations:Q", title="Locations", format=","),
            ],
        )
        .add_params(band_pick)
        .properties(width=310, height=230)
    )
    temporal_chart = (
        temporal_lines.facet(
            facet=alt.Facet("variable:N", title=None),
            columns=grid_columns_control.value,
        )
        .resolve_scale(x="shared", y="independent")
        .properties(title="Selected variables over time by elevation band")
    )
    temporal_widget = mo.ui.altair_chart(
        temporal_chart,
        chart_selection=False,
        legend_selection=False,
    )
    mo.vstack(
        [
            mo.md(
                "Each line is an elevation band. Values are first averaged within each "
                "location-period and then across locations, giving each available location "
                "equal weight. Click the legend to isolate a band."
            ),
            temporal_widget,
        ]
    )
    return


@app.cell
def _(
    dataset_version,
    focus_variable,
    mo,
    relationships,
    scatter_long,
    selected_comparisons,
    selected_end,
    selected_start,
):
    export_prefix = f"{focus_variable}-relationships-{selected_start}-{selected_end}"
    mo.vstack(
        [
            mo.md(
                f"## 7. Export evidence\n\nDataset version: `{dataset_version}` · "
                f"grid variables: `{', '.join(selected_comparisons)}`"
            ),
            mo.hstack(
                [
                    mo.download(
                        data=relationships.to_csv(index=False).encode(),
                        filename=f"{export_prefix}-correlations.csv",
                        label="Download correlations",
                    ),
                    mo.download(
                        data=scatter_long.to_csv(index=False).encode(),
                        filename=f"{export_prefix}-scatter-grid-sample.csv",
                        label="Download scatter-grid sample",
                    ),
                ]
            ),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
