"""Local trusted notebook runtime; Spark actions execute distributed DataFrame plans."""
import atexit
import os
from pathlib import Path
import sys

from pyspark.sql import SparkSession, Window, functions as F

from .storage import DatasetStore


def past_average(frame, column, hours=24, output=None):
    """Per-location calendar-hour window excluding the current observation.

    Calculate before cutting the displayed/validation time range to retain history.
    Gaps remain gaps: avg uses available non-null readings, without imputation.
    """
    if not isinstance(hours, int) or hours < 1:
        raise ValueError('hours must be a positive integer')
    window = Window.partitionBy('location_id').orderBy(
        F.col('timestamp').cast('long')).rangeBetween(-hours*3600, -1)
    return frame.withColumn(output or f'{column}_past_{hours}h', F.avg(column).over(window))


def chronological_split(frame, validation_start, test_start, horizon_hours=0):
    """Global UTC cutoffs, half-open ranges; purge forward labels at boundaries.

    horizon_hours is the furthest future label offset from each row's timestamp.
    Fit imputers/scalers/models on training only. Rolling-origin evaluation can use
    prior validation observations; fixed-origin forecasts must construct features
    only from observations available at that origin.
    """
    import pandas as pd

    valid, test = pd.Timestamp(validation_start), pd.Timestamp(test_start)
    valid = valid.tz_localize('UTC') if valid.tzinfo is None else valid.tz_convert('UTC')
    test = test.tz_localize('UTC') if test.tzinfo is None else test.tz_convert('UTC')
    if pd.isna(valid) or pd.isna(test) or valid >= test or horizon_hours < 0:
        raise ValueError('Require ordered cutoffs and nonnegative horizon_hours')
    timestamp = F.col('timestamp').cast('double')
    label_end = timestamp + horizon_hours*3600
    return (frame.filter(label_end < valid.timestamp()),
            frame.filter((timestamp >= valid.timestamp()) & (label_end < test.timestamp())),
            frame.filter(timestamp >= test.timestamp()))


class NotebookSession:
    def __init__(self, root=None, version=None):
        if root is None:
            root = os.getenv('WEATHER_PLATFORM_ROOT')
        if root is None:
            # Resolve from the script/cwd, not the package installation directory.
            candidates = [Path.cwd(), *Path.cwd().parents]
            root = next((p / 'data/platform' for p in candidates
                         if (p / 'data/platform/active.json').exists()), None)
        if root is None:
            raise FileNotFoundError('Set WEATHER_PLATFORM_ROOT to a published dataset store')
        self.store = DatasetStore(root, version or os.getenv('WEATHER_DATASET_VERSION'))
        if sys.platform == 'darwin' and not os.getenv('JAVA_HOME'):
            for prefix in ('/opt/homebrew', '/usr/local'):
                java_home = Path(prefix) / 'opt/openjdk@21/libexec/openjdk.jdk/Contents/Home'
                if (java_home / 'bin/java').exists():
                    os.environ['JAVA_HOME'] = str(java_home)
                    break
        os.environ.setdefault('SPARK_LOCAL_IP', '127.0.0.1')
        os.environ.setdefault('PYSPARK_PYTHON', sys.executable)
        partitions = int(os.getenv('SPARK_PARTITIONS', '8'))
        if partitions < 1:
            raise ValueError('SPARK_PARTITIONS must be positive')
        self.spark = (SparkSession.builder.appName('Big Weather Notebook')
            .master(os.getenv('SPARK_MASTER', 'local[4]'))
            .config('spark.sql.session.timeZone', 'UTC')
            .config('spark.sql.shuffle.partitions', str(partitions))
            .getOrCreate())
        self.spark.sparkContext.setLogLevel('WARN')
        self.weather = (self.table('enriched_weather').repartition(partitions, 'location_id')
                        .sortWithinPartitions('location_id', 'timestamp'))
        self.daily = self.table('daily_metrics')
        self.locations = self.table('locations')
        print(f'Spark notebook dataset: {self.store.version}; '
              f'{self.store.manifest["tables"]["enriched_weather"]["rows"]:,} hourly rows')
        atexit.register(self.close)

    def table(self, name):
        return self.spark.read.parquet(str(self.store.table_path(name).resolve()))

    def close(self):
        self.spark.stop()
