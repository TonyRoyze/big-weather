from datetime import date
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

from weather_ingest.pipeline import ingest, weather_frame


def sample_payload():
    return {
        "hourly": {
            "time": ["2024-01-01T00:00", "2024-01-01T01:00"],
            "temperature_2m": [20.0, 19.5],
            "precipitation": [0.0, 0.4],
            "wind_speed_10m": [2.0, 2.5],
            "relative_humidity_2m": [70, 72],
        }
    }


def test_weather_frame_has_stable_schema():
    frame = weather_frame(sample_payload(), "colombo", 2024)
    assert list(frame.columns) == [
        "location_id",
        "timestamp",
        "temperature_2m",
        "precipitation",
        "wind_speed_10m",
        "relative_humidity_2m",
        "source_year",
        "ingested_at",
    ]
    assert str(frame.timestamp.dtype) == "datetime64[ns, UTC]"


def test_ingest_partitions_by_location_and_year(tmp_path: Path):
    class FakeClient:
        def historical_weather(self, *args):
            return sample_payload()

    locations = pd.DataFrame(
        [
            {
                "location_id": "colombo",
                "name": "Colombo",
                "country": "Sri Lanka",
                "country_code": "LK",
                "region": "South Asia",
                "latitude": 6.93,
                "longitude": 79.85,
                "elevation_m": 8.0,
                "timezone": "Asia/Colombo",
            }
        ]
    )
    files, rows = ingest(
        locations, FakeClient(), tmp_path, date(2024, 1, 1), date(2024, 1, 1)
    )
    output = tmp_path / "raw/weather/location_id=colombo/year=2024/weather.parquet"
    assert (files, rows) == (1, 2)
    assert output.exists()
    parquet_schema = pq.read_schema(output)
    assert "location_id" not in parquet_schema.names
    assert "timestamp[us" in str(parquet_schema.field("timestamp").type)


def test_weather_frame_rejects_missing_variable():
    payload = sample_payload()
    del payload["hourly"]["precipitation"]
    with pytest.raises(RuntimeError, match="missing fields"):
        weather_frame(payload, "colombo", 2024)
