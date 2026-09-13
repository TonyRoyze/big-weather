"""Weather analysis expressed with PySpark DataFrames (UTC and physical units).

These functions preserve the published table contract in docs/data-contract.md.
They construct Spark expressions; no per-row Python UDFs are needed.
"""

import sys

from pyspark.ml.feature import VectorAssembler
from pyspark.ml.regression import LinearRegression
from pyspark.sql import DataFrame, Window, functions as F

REQUIRED_WEATHER = {
    "location_id",
    "timestamp",
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "relative_humidity_2m",
    "source_year",
    "ingested_at",
}
LAPSE_SCHEMA = (
    "season string, slope_c_per_m double, lapse_rate_c_per_km double, "
    "intercept_c double, r2 double, rmse_c double, sample_size long"
)


def validate(weather: DataFrame) -> DataFrame:
    missing = REQUIRED_WEATHER - set(weather.columns)
    if missing:
        raise ValueError(f"Missing weather columns: {sorted(missing)}")
    return (
        weather.filter(F.col("location_id").isNotNull() & F.col("timestamp").isNotNull())
        .filter(F.col("temperature_2m").between(-100.0, 70.0))
        .filter(F.col("precipitation").between(0.0, sys.float_info.max))
        .filter(F.col("wind_speed_10m").between(0.0, sys.float_info.max))
        .filter(F.col("relative_humidity_2m").between(0.0, 100.0))
        .dropDuplicates(["location_id", "timestamp"])
    )


def elevation_band(elevation):
    return (
        F.when(elevation < 200, "lowland")
        .when(elevation < 1000, "midland")
        .when(elevation < 3000, "highland")
        .otherwise("alpine")
    )


def season(month, latitude):
    northern = (
        F.when(month.isin(12, 1, 2), "winter")
        .when(month.isin(3, 4, 5), "spring")
        .when(month.isin(6, 7, 8), "summer")
        .otherwise("autumn")
    )
    southern = (
        F.when(month.isin(12, 1, 2), "summer")
        .when(month.isin(3, 4, 5), "autumn")
        .when(month.isin(6, 7, 8), "winter")
        .otherwise("spring")
    )
    return F.when(latitude >= 0, northern).otherwise(southern)


def enrich(weather: DataFrame, locations: DataFrame) -> DataFrame:
    metadata = locations.select(
        "location_id", "name", "country", "region", "latitude", "longitude", "elevation_m"
    )
    return (
        weather.join(F.broadcast(metadata), "location_id", "inner")
        .withColumn("elevation_band", elevation_band(F.col("elevation_m")))
        .withColumn("date", F.to_date("timestamp"))
        .withColumn("year", F.year("timestamp"))
        .withColumn("season", season(F.month("timestamp"), F.col("latitude")))
    )


def summaries(enriched: DataFrame) -> DataFrame:
    return enriched.groupBy("elevation_band", "region", "season", "year").agg(
        F.avg("temperature_2m").alias("avg_temperature_c"),
        F.sum("precipitation").alias("total_precipitation_mm"),
        F.avg("wind_speed_10m").alias("avg_wind_speed_ms"),
        F.avg("relative_humidity_2m").alias("avg_relative_humidity_pct"),
        F.count(F.lit(1)).alias("observation_count"),
    )


def daily_metrics(enriched: DataFrame) -> DataFrame:
    daily = enriched.groupBy(
        "location_id", "name", "region", "elevation_m", "elevation_band", "season", "date"
    ).agg(
        F.avg("temperature_2m").alias("daily_avg_temperature_c"),
        F.sum("precipitation").alias("daily_precipitation_mm"),
        F.avg("wind_speed_10m").alias("daily_avg_wind_speed_ms"),
        F.count(F.lit(1)).alias("observed_hours"),
    )
    window = Window.partitionBy("location_id").orderBy(F.unix_date("date")).rangeBetween(-29, 0)
    return daily.withColumn(
        "temperature_30d_rolling_avg_c", F.avg("daily_avg_temperature_c").over(window)
    )


def yearly_metrics(enriched: DataFrame) -> DataFrame:
    yearly = enriched.groupBy("location_id", "name", "region", "elevation_m", "year").agg(
        F.avg("temperature_2m").alias("annual_avg_temperature_c")
    )
    window = Window.partitionBy("location_id").orderBy("year")
    return yearly.withColumn(
        "temperature_yoy_change_c",
        F.col("annual_avg_temperature_c") - F.lag("annual_avg_temperature_c").over(window),
    )


def lapse_rates(daily: DataFrame) -> DataFrame:
    """Descriptive pooled OLS per local season; omit seasons with <2 elevations."""
    frame = daily.select("season", "elevation_m", "daily_avg_temperature_c").na.drop()
    rows = []
    for row in frame.select("season").distinct().orderBy("season").collect():
        selected = frame.filter(F.col("season") == row.season)
        if selected.select("elevation_m").distinct().count() < 2:
            continue
        assembled = VectorAssembler(inputCols=["elevation_m"], outputCol="features").transform(
            selected
        )
        model = LinearRegression(labelCol="daily_avg_temperature_c", maxIter=50, regParam=0.0).fit(
            assembled
        )
        slope = float(model.coefficients[0])
        rows.append(
            (
                row.season,
                slope,
                slope * 1000.0,
                float(model.intercept),
                float(model.summary.r2),
                float(model.summary.rootMeanSquaredError),
                selected.count(),
            )
        )
    # Explicit schema keeps one-location samples readable even when no model can be fitted.
    return daily.sparkSession.createDataFrame(rows, LAPSE_SCHEMA)
