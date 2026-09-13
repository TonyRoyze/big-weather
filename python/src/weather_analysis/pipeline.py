"""Batch processing: raw Parquet → validated/enriched data → dashboard tables.

Run `weather-analysis process` or `make process`. Java is required by PySpark;
there is no application compilation/build step. Publish only after this finishes.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import time
import sys

from pyspark.sql import SparkSession

from . import transforms
from .storage import atomic_json


def process(input_root: Path, output_root: Path) -> dict:
    input_root, output_root = Path(input_root).resolve(), Path(output_root).resolve()
    if (
        input_root == output_root
        or input_root in output_root.parents
        or output_root in input_root.parents
    ):
        raise ValueError("Input and output must be separate, non-overlapping directories")
    started = time.perf_counter()
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    spark = (
        SparkSession.builder.appName("Big Weather Processing")
        .master(os.getenv("SPARK_MASTER", "local[4]"))
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.driver.memory", "4g")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    output_root.mkdir(parents=True, exist_ok=True)
    # A failed rerun must not leave an old success/timing record behind.
    (output_root / "pipeline_metrics.json").unlink(missing_ok=True)
    try:
        weather = spark.read.parquet(str(input_root / "weather")).repartition(4).cache()
        locations = spark.read.parquet(str(input_root / "locations"))
        validated = transforms.validate(weather).cache()
        enriched = transforms.enrich(validated, locations).cache()
        daily = transforms.daily_metrics(enriched).cache()
        enriched.write.mode("overwrite").partitionBy("elevation_band").parquet(
            str(output_root / "enriched_weather")
        )
        transforms.summaries(enriched).write.mode("overwrite").parquet(
            str(output_root / "summaries")
        )
        daily.write.mode("overwrite").parquet(str(output_root / "daily_metrics"))
        transforms.yearly_metrics(enriched).write.mode("overwrite").parquet(
            str(output_root / "yearly_metrics")
        )
        transforms.lapse_rates(daily).write.mode("overwrite").parquet(
            str(output_root / "lapse_rates")
        )
        input_rows, validated_rows, output_rows = (
            weather.count(),
            validated.count(),
            enriched.count(),
        )
        metrics = {
            "input_rows": input_rows,
            "validated_rows": validated_rows,
            "rejected_or_duplicate_rows": input_rows - validated_rows,
            "unmatched_location_rows": validated_rows - output_rows,
            "output_rows": output_rows,
            "daily_rows": daily.count(),
            "input_partitions": weather.rdd.getNumPartitions(),
            "shuffle_partitions": 4,
            "spark_master": spark.sparkContext.master,
            "spark_version": spark.version,
            "implementation": "pyspark",
            "transformation_version": "pipeline-v1",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": time.perf_counter() - started,
        }
        atomic_json(output_root / "pipeline_metrics.json", metrics)
        return metrics
    finally:
        spark.stop()
