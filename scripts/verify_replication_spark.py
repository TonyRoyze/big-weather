"""Independently reconcile the frozen panel's daily aggregates with local Spark."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

root = Path(__file__).resolve().parents[1] / "reports/replication"
spark = (
    SparkSession.builder.master("local[2]")
    .appName("Weather replication parity")
    .config("spark.driver.host", "127.0.0.1")
    .config("spark.sql.session.timeZone", "UTC")
    .config("spark.sql.shuffle.partitions", "2")
    .getOrCreate()
)
spark.sparkContext.setLogLevel("WARN")
try:
    # Spark does not accept Arrow nanosecond timestamp Parquet on every version.
    panel = pd.read_parquet(root / "panel.parquet")
    path = root / "spark_panel.parquet"
    panel[
        ["location_id", "timestamp", "temperature_2m", "precipitation", "wind_speed_10m"]
    ].to_parquet(path, coerce_timestamps="us", allow_truncated_timestamps=False, index=False)
    rows = spark.read.parquet(str(path)).withColumn("day", F.to_date("timestamp"))
    actual = (
        rows.groupBy("location_id", "day")
        .agg(
            F.count("*").alias("hours"),
            F.avg("temperature_2m").alias("temperature_2m"),
            F.sum("precipitation").alias("precipitation"),
            F.avg("wind_speed_10m").alias("wind_speed_10m"),
        )
        .toPandas()
    )
    expected = pd.read_parquet(root / "daily_panel.parquet")
    expected["day"] = expected.date.dt.date
    joined = actual.merge(
        expected, on=["location_id", "day"], suffixes=("_spark", "_pandas"), validate="one_to_one"
    )
    assert len(joined) == len(expected) == len(actual)
    errors = {}
    for metric in ["hours", "temperature_2m", "precipitation", "wind_speed_10m"]:
        errors[metric] = float(
            np.max(np.abs(joined[metric + "_spark"] - joined[metric + "_pandas"]))
        )
        np.testing.assert_allclose(
            joined[metric + "_spark"], joined[metric + "_pandas"], rtol=1e-12, atol=1e-10
        )
    result = {
        "status": "passed",
        "hourly_rows": len(panel),
        "daily_rows": len(actual),
        "spark_version": spark.version,
        "max_absolute_difference": errors,
    }
    (root / "spark_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(result)
finally:
    spark.stop()
