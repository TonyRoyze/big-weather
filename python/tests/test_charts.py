from datetime import date

import pandas as pd
import pytest
from weather_analysis.charts import load_chart_data
from weather_analysis.storage import DatasetStore


def test_chart_query_filters_dates_locations_and_columns(published):
    _, root = published
    frame, rows, bucket = load_chart_data(
        DatasetStore(root), ["b"], "2024-01-02", "2024-01-02", ["daily_precipitation_mm"]
    )
    assert rows == 1
    assert bucket == 1
    assert list(frame.columns) == ["location_id", "date", "daily_precipitation_mm"]
    assert frame.location_id.tolist() == ["b"]
    assert frame.daily_precipitation_mm.tolist() == [2.0]


def test_chart_payload_bound_and_rainfall_mean():
    class Store:
        def read(self, *args, **kwargs):
            return pd.DataFrame([
                {"location_id": str(loc), "date": day, "daily_precipitation_mm": 2.0}
                for loc in range(10)
                for day in pd.date_range("2020-01-01", "2025-12-31")
            ])

    frame, rows, bucket = load_chart_data(
        Store(), list(map(str, range(10))), date(2020, 1, 1), date(2025, 12, 31),
        ["daily_precipitation_mm"],
    )
    assert rows == 21920
    assert len(frame) <= 6000
    assert bucket == 4
    assert (frame.daily_precipitation_mm == 2.0).all()


def test_chart_query_rejects_unknown_metric(published):
    with pytest.raises(ValueError, match="Unknown chart metric"):
        load_chart_data(DatasetStore(published[1]), ["a"], "2024-01-01", "2024-01-02", ["bad"])


def test_raw_preview_keeps_incomplete_days_missing_and_ignores_uncommitted(raw_preview):
    from weather_analysis.charts import load_preview_data, preview_catalog

    incomplete = raw_preview / 'raw/weather/location_id=other/year=2024'
    incomplete.mkdir(parents=True)
    (incomplete / 'weather.parquet').write_bytes(b'not committed')
    chunks = preview_catalog(raw_preview)
    assert len(chunks) == 1
    frame = load_preview_data(chunks, ['hill'], '2024-01-01', '2024-01-02',
                              'daily_precipitation_mm')
    assert frame.observed_hours.tolist() == [24, 23]
    assert frame.daily_precipitation_mm.iloc[0] == 24
    assert pd.isna(frame.daily_precipitation_mm.iloc[1])
    with pytest.raises(ValueError, match='1–93'):
        load_preview_data(chunks, ['hill'], '2024-01-01', '2024-12-31',
                          'daily_precipitation_mm')
