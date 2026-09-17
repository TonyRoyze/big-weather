"""Known-value PySpark tests for the complete weather transformation contract."""

from datetime import datetime, timezone
import os
import sys

import pytest

pytest.importorskip("pyspark")
from pyspark.sql import SparkSession, functions as F

from weather_analysis import transforms as T

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def spark():
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    session = (
        SparkSession.builder.master("local[2]")
        .appName("weather-transform-tests")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()


def test_elevation_boundaries_and_hemisphere_seasons(spark):
    elevations = spark.createDataFrame(
        [(v,) for v in [0.0, 199.9, 200.0, 999.9, 1000.0, 2999.9, 3000.0]], "metres double"
    )
    assert [
        r.band for r in elevations.select(T.elevation_band(F.col("metres")).alias("band")).collect()
    ] == ["lowland", "lowland", "midland", "midland", "highland", "highland", "alpine"]
    points = spark.createDataFrame(
        [(1, 10.0), (1, -10.0), (7, 10.0), (7, -10.0)], "month int, latitude double"
    )
    assert [
        r.season
        for r in points.select(
            T.season(F.col("month"), F.col("latitude")).alias("season")
        ).collect()
    ] == ["winter", "summer", "summer", "winter"]


def weather_frame(spark, observations):
    # Explicit UTC avoids machine-local timezone conversion in Spark createDataFrame.
    observations = [
        (loc, ts.replace(tzinfo=timezone.utc), *values) for loc, ts, *values in observations
    ]
    # ID, timestamp, temperature, precipitation, wind, humidity.
    frame = spark.createDataFrame(
        observations,
        "location_id string, timestamp timestamp, temperature_2m double, precipitation double, wind_speed_10m double, relative_humidity_2m double",
    )
    return frame.withColumn("source_year", F.year("timestamp")).withColumn(
        "ingested_at", F.col("timestamp")
    )


def test_validation_rejects_missing_columns_nulls_duplicates_and_nonfinite(spark):
    timestamp = datetime(2024, 1, 1)
    good = ("a", timestamp, 20.0, 0.0, 2.0, 60.0)
    frame = weather_frame(
        spark,
        [
            good,
            good,
            ("b", timestamp, 200.0, 0.0, 2.0, 60.0),
            ("c", timestamp, 20.0, float("nan"), 2.0, 60.0),
            ("d", timestamp, 20.0, 0.0, float("inf"), 60.0),
            ("e", timestamp, 20.0, 0.0, 2.0, None),
            (None, timestamp, 20.0, 0.0, 2.0, 60.0),
        ],
    )
    assert T.validate(frame).count() == 1
    with pytest.raises(ValueError, match="Missing weather columns"):
        T.validate(frame.drop("precipitation"))


def test_daily_calendar_window_yearly_changes_and_summaries(spark):
    weather = weather_frame(
        spark,
        [
            ("a", datetime(2024, 1, 1, 0), 20.0, 1.0, 2.0, 60.0),
            ("a", datetime(2024, 1, 1, 1), 22.0, 2.0, 4.0, 80.0),
            ("a", datetime(2024, 1, 31), 10.0, 3.0, 6.0, 70.0),
            ("a", datetime(2024, 2, 1), 14.0, 4.0, 8.0, 70.0),
            ("a", datetime(2025, 1, 1), 18.0, 5.0, 10.0, 70.0),
        ],
    )
    locations = spark.createDataFrame(
        [("a", "Coast", "Test", "North", 10.0, 20.0, 10.0)],
        "location_id string, name string, country string, region string, latitude double, longitude double, elevation_m double",
    )
    enriched = T.enrich(T.validate(weather), locations).cache()
    try:
        daily = T.daily_metrics(enriched).orderBy("date").collect()
        assert [r.daily_avg_temperature_c for r in daily] == [21.0, 10.0, 14.0, 18.0]
        assert [r.observed_hours for r in daily] == [2, 1, 1, 1]
        assert [r.daily_precipitation_mm for r in daily] == [3.0, 3.0, 4.0, 5.0]
        # Jan 1 falls outside Jan 31's 30-day window, even though it is the preceding row.
        assert [r.temperature_30d_rolling_avg_c for r in daily] == [21.0, 10.0, 12.0, 18.0]
        yearly = T.yearly_metrics(enriched).orderBy("year").collect()
        assert yearly[0].annual_avg_temperature_c == 16.5
        assert yearly[0].temperature_yoy_change_c is None
        assert yearly[1].temperature_yoy_change_c == 1.5
        summary = T.summaries(enriched).filter(F.col("year") == 2024).first()
        assert summary.observation_count == 4
        assert summary.total_precipitation_mm == 10.0
        assert summary.avg_temperature_c == 16.5
    finally:
        enriched.unpersist()


def test_lapse_rate_known_line_and_empty_model_schema(spark):
    daily = spark.createDataFrame(
        [
            ("winter", 0.0, 20.0),
            ("winter", 1000.0, 14.0),
            ("winter", 2000.0, 8.0),
            ("summer", 0.0, 25.0),
        ],
        "season string, elevation_m double, daily_avg_temperature_c double",
    )
    result = T.lapse_rates(daily).collect()
    assert len(result) == 1
    assert result[0].season == "winter"
    assert result[0].lapse_rate_c_per_km == pytest.approx(-6.0)
    assert result[0].intercept_c == pytest.approx(20.0)
    assert result[0].r2 == pytest.approx(1.0)
    assert result[0].sample_size == 3
    empty = T.lapse_rates(daily.filter(F.col("season") == "summer"))
    assert empty.count() == 0
    assert empty.columns == [
        "season",
        "slope_c_per_m",
        "lapse_rate_c_per_km",
        "intercept_c",
        "r2",
        "rmse_c",
        "sample_size",
    ]


def test_notebook_windows_and_purged_chronological_split(spark):
    from weather_analysis.notebook import chronological_split, past_average

    # Deliberately shuffled; two locations and a missing hour. A 2-hour window
    # must not use a previous row from 3 hours ago, the current row or another site.
    frame = spark.createDataFrame([
        ('a', datetime(2024, 1, 1, 4, tzinfo=timezone.utc), 40.),
        ('b', datetime(2024, 1, 1, 1, tzinfo=timezone.utc), 100.),
        ('a', datetime(2024, 1, 1, 0, tzinfo=timezone.utc), 10.),
        ('a', datetime(2024, 1, 1, 1, tzinfo=timezone.utc), 20.),
        ('a', datetime(2024, 1, 1, 5, tzinfo=timezone.utc), 50.),
    ], 'location_id string, timestamp timestamp, value double').repartition(3)
    result = past_average(frame, 'value', hours=2).orderBy('location_id', 'timestamp').collect()
    assert [r.value_past_2h for r in result] == [None, 10., None, 40., None]
    train, valid, test = chronological_split(
        frame, '2024-01-01T04:00Z', '2024-01-01T05:00Z', horizon_hours=1)
    assert train.count() == 3
    assert valid.count() == 0  # 04:00 label at 05:00 crosses the test boundary
    assert test.count() == 1
    with pytest.raises(ValueError, match='ordered cutoffs'):
        chronological_split(frame, '2025-01-01', '2024-01-01')
