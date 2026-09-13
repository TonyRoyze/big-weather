"""Verify installed packages, a real Spark Parquet round-trip and bundled data."""

import importlib
import os
from pathlib import Path
import shutil
import sys
import tempfile


def main():
    for module in [
        "pandas",
        "pyarrow",
        "requests_cache",
        "tenacity",
        "pyspark",
        "streamlit",
        "plotly",
        "pytest",
    ]:
        importlib.import_module(module)
    if shutil.which("java") is None:
        raise RuntimeError("Java is not on PATH")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    from pyspark.sql import SparkSession
    from weather_analysis import DatasetStore

    spark = (
        SparkSession.builder.master("local[2]")
        .appName("Big Weather Setup Check")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    try:
        with tempfile.TemporaryDirectory() as temporary:
            output = str(Path(temporary) / "parquet")
            spark.createDataFrame(
                [(1, 2.0), (2, 4.0)], "id long, temperature double"
            ).write.parquet(output)
            frame = spark.read.parquet(output)
            if frame.count() != 2 or frame.groupBy().avg("temperature").first()[0] != 3.0:
                raise RuntimeError("Spark computation/Parquet verification failed")
    finally:
        spark.stop()
    store = DatasetStore(Path(__file__).resolve().parents[1] / "data/platform")
    locations = store.read("locations")
    if locations.empty:
        raise RuntimeError("The bundled location table is empty")
    print(
        f"Setup verified: Python {sys.version.split()[0]}, Spark {spark.version}, "
        f"{len(locations)} locations, dataset {store.version}."
    )


if __name__ == "__main__":
    main()
