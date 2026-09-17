"""Small, filtered chart queries over a published snapshot (no Spark startup)."""

import pandas as pd

METRIC_LABELS = {
    "daily_avg_temperature_c": "Daily mean temperature (°C)",
    "daily_precipitation_mm": "Daily precipitation (mm)",
    "daily_avg_wind_speed_ms": "Daily mean wind speed (m/s)",
    "temperature_30d_rolling_avg_c": "30-day rolling temperature (°C)",
}


def load_chart_data(store, locations, start, end, metrics):
    """Project and filter at the Parquet reader; bound the browser payload to 6,000 rows."""
    if not locations or not metrics:
        raise ValueError("Choose at least one location and metric.")
    if len(locations) > 10:
        raise ValueError("Choose up to 10 locations per request.")
    if set(metrics) - METRIC_LABELS.keys():
        raise ValueError("Unknown chart metric.")
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    if start > end:
        raise ValueError("Start date must be before end date.")
    frame = store.read(
        "daily_metrics",
        columns=["location_id", "date", *metrics],
        filters=[("location_id", "in", list(locations)), ("date", ">=", start),
                 ("date", "<=", end)],
    )
    rows = len(frame)
    bucket_days = 1
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame.date)
        # Use fixed-width calendar buckets so every location shares the same dates.
        days = (end - start).days + 1
        bucket_days = max(1, (days + (6000 // len(locations)) - 1)
                          // (6000 // len(locations)))
        if bucket_days > 1:
            frame["date"] = pd.Timestamp(start) + pd.to_timedelta(
                ((frame.date - pd.Timestamp(start)).dt.days // bucket_days) * bucket_days,
                unit="D",
            )
            # Rainfall stays a mean DAILY total, not a misleading bucket sum.
            frame = frame.groupby(["location_id", "date"], observed=True)[list(metrics)].mean()
            frame = frame.reset_index()
        frame = frame.sort_values(["location_id", "date"])
    return frame, rows, bucket_days


def preview_catalog(root):
    """List committed raw chunks only; never treat an in-flight file as complete."""
    import json
    from pathlib import Path

    root = Path(root)
    chunks = []
    for metadata in sorted((root / 'raw/weather').glob('location_id=*/year=*/_source*.json')):
        file = metadata.with_name(metadata.name.replace('_source', 'weather').replace('.json', '.parquet'))
        if file.exists():
            request = json.loads(metadata.read_text())['request']
            chunks.append({**request, 'path': str(file.resolve())})
    return chunks


def load_preview_data(chunks, locations, start, end, metric):
    """Bounded daily preview from completed raw chunks, with incomplete days missing."""
    import pyarrow.parquet as pq

    fields = {'daily_avg_temperature_c': 'temperature_2m',
              'daily_precipitation_mm': 'precipitation',
              'daily_avg_wind_speed_ms': 'wind_speed_10m'}
    if metric not in fields or not locations or len(locations) > 10:
        raise ValueError('Choose a supported metric and 1–10 locations.')
    start, end = pd.Timestamp(start).date(), pd.Timestamp(end).date()
    if start > end or (end-start).days > 92:
        raise ValueError('Choose a range of 1–93 days.')
    field = fields[metric]
    frames = []
    for chunk in chunks:
        if (chunk['location_id'] not in locations or
                pd.Timestamp(chunk['end']).date() < start or
                pd.Timestamp(chunk['start']).date() > end):
            continue
        # Explicit file reads avoid reading uncommitted chunks or discovering Hive keys twice.
        frame = pq.ParquetFile(chunk['path']).read(columns=['timestamp', field]).to_pandas()
        timestamp = pd.to_datetime(frame.timestamp, utc=True)
        frame = frame.loc[(timestamp >= pd.Timestamp(start, tz='UTC')) &
                          (timestamp < pd.Timestamp(end, tz='UTC') + pd.Timedelta(days=1))].copy()
        frame['date'] = pd.to_datetime(frame.timestamp, utc=True).dt.floor('D')
        frame['location_id'] = chunk['location_id']
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=['location_id', 'date', metric, 'observed_hours'])
    hourly = pd.concat(frames, ignore_index=True).drop_duplicates(['location_id', 'timestamp'])
    groups = hourly.groupby(['location_id', 'date'])[field]
    counts = groups.count()
    values = groups.sum(min_count=1) if field == 'precipitation' else groups.mean()
    return pd.DataFrame({metric: values.where(counts == 24), 'observed_hours': counts}).reset_index()
