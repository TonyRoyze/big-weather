"""Run only server-compiled read-only SQL in a bounded Spark subprocess."""

import json
import sys
from pathlib import Path


def run(path):
    from pyspark.sql import SparkSession
    from pyspark.sql.types import DoubleType, StringType, StructField, StructType

    request = json.loads(path.read_text())
    spark = (
        SparkSession.builder.master("local[2]")
        .appName("Ask Big Weather")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        spark.read.option("basePath", request["base"]).parquet(
            *request["paths"]
        ).createOrReplaceTempView("weather")
        schema = StructType(
            [
                StructField("location_id", StringType()),
                StructField("name", StringType()),
                StructField("country", StringType()),
                StructField("elevation_m", DoubleType()),
            ]
        )
        records = [
            {**r, "elevation_m": float(r["elevation_m"]) if r["elevation_m"] is not None else None}
            for r in request["locations"]
        ]
        spark.createDataFrame(records, schema).createOrReplaceTempView("locations")
        rows = spark.sql(request["sql"]).toJSON().collect()
        (path.parent / "result.json").write_text("[" + ",".join(rows) + "]")
    finally:
        spark.stop()


if __name__ == "__main__":
    run(Path(sys.argv[1]))
