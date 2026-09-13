"""Isolated PySpark worker invoked by the job service, never by dashboard pages."""

import json
import os
from pathlib import Path
import sys
import time

from .spec import validate_spec
from .storage import atomic_json


def run(request: Path) -> None:
    from pyspark.sql import SparkSession, functions as F

    payload = json.loads(request.read_text())
    spec = validate_spec(payload["spec"])
    started = time.perf_counter()
    spark = (
        SparkSession.builder.appName("Big Weather Custom Analysis")
        .master(os.getenv("SPARK_MASTER", "local[4]"))
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "4")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        frame = spark.read.parquet(payload["input"])
        for field, values in spec["filters"].items():
            predicate = (
                F.col(field).between(*values) if field == "date" else F.col(field).isin(values)
            )
            frame = frame.filter(predicate)
        frame = frame.cache()
        input_rows = frame.count()
        expressions = [
            getattr(F, op)(F.col(metric)).alias(f"{metric}_{op}")
            for metric, ops in spec["aggregations"].items()
            for op in ops
        ]
        result = frame.groupBy(*spec["group_by"]).agg(*expressions)
        result.write.mode("errorifexists").parquet(payload["output"])
        output_rows = spark.read.parquet(payload["output"]).count()
        atomic_json(
            request.parent / "worker_metrics.json",
            {
                "input_rows": input_rows,
                "output_rows": output_rows,
                "spark_seconds": time.perf_counter() - started,
                "spark_master": spark.sparkContext.master,
                "input_partitions": frame.rdd.getNumPartitions(),
                "shuffle_partitions": int(spark.conf.get("spark.sql.shuffle.partitions")),
            },
        )
    finally:
        spark.stop()


if __name__ == "__main__":
    run(Path(sys.argv[1]))
