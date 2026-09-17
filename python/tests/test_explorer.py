import json
from datetime import date

import pandas as pd
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi.testclient import TestClient
from weather_analysis.explorer import create_app


@pytest.fixture
def preview(tmp_path):
    locations = tmp_path / "raw/locations"
    locations.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "location_id": "a",
                "name": "Coast",
                "country": "LK",
                "region": "South Asia",
                "latitude": 7.0,
                "longitude": 80.0,
                "elevation_m": 12.0,
            }
        ]
    ).to_parquet(locations / "part.parquet", index=False)
    hourly = tmp_path / "raw/weather/location_id=a/year=2024"
    hourly.mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=47, freq="h", tz="UTC"),
            "temperature_2m": [20.0] * 24 + [30.0] * 23,
            "precipitation": [2.0] * 47,
        }
    )
    frame = pd.concat(
        [
            frame,
            pd.DataFrame(
                {
                    "timestamp": pd.date_range("2024-01-04", periods=24, freq="h", tz="UTC"),
                    "temperature_2m": [25.0] * 24,
                    "precipitation": [1.0] * 24,
                }
            ),
        ],
        ignore_index=True,
    )
    frame.to_parquet(hourly / "weather.parquet", index=False)
    (hourly / "_source.json").write_text(
        json.dumps(
            {
                "request": {
                    "location_id": "a",
                    "start": "2024-01-01",
                    "end": "2024-01-04",
                }
            }
        )
    )
    return TestClient(create_app(raw_root=tmp_path))


def query(client, **kwargs):
    return client.get(
        "/api/window",
        params={
            "metric": "precipitation",
            "start": "2024-01-01",
            "end": "2024-01-03",
            "locations": ["a"],
            **kwargs,
        },
    )


def test_preview_metadata_and_complete_day_aggregation(preview):
    meta = preview.get("/api/metadata").json()
    assert meta["preview"] is True
    assert {f["id"] for f in meta["features"]} == {"temperature_2m", "precipitation"}
    response = query(preview)
    assert response.status_code == 200
    rows = response.json()["records"]
    assert rows == [
        {"location_id": "a", "date": "2024-01-01", "value": 48.0, "hours": 24},
        {"location_id": "a", "date": "2024-01-02", "value": None, "hours": 23},
    ]
    assert query(preview, metric="temperature_2m").json()["records"][0]["value"] == 20.0
    assert query(preview).json()["records"] == rows


@pytest.mark.parametrize(
    "changes",
    [
        {"metric": "bad"},
        {"start": "2024-02-01", "end": "2024-01-01"},
        {"end": "2024-12-31"},
        {"start": "2023-12-31"},
        {"locations": ["unknown"]},
        {"start": "not-a-date"},
    ],
)
def test_invalid_query(preview, changes):
    assert query(preview, **changes).status_code == 422


def test_revision_mismatch(preview):
    assert query(preview, fingerprint="old").status_code == 409


def test_empty_window(preview):
    response = query(preview, start="2024-01-03", end="2024-01-03")
    assert response.status_code == 200
    assert response.json()["records"] == []


def test_published_source_and_missing_source(published, tmp_path):
    client = TestClient(create_app(root=published[1]))
    assert client.get("/api/metadata").json()["preview"] is False
    assert query(client, end=str(date(2024, 1, 2))).status_code == 200
    missing = TestClient(create_app(root=tmp_path / "absent"))
    assert missing.get("/api/metadata").status_code == 503


def test_new_committed_week_refreshes_preview(preview, tmp_path):
    old = preview.get("/api/metadata").json()
    folder = tmp_path / "raw/weather/location_id=a/year=2024"
    file = folder / "weather-2024-01-05-2024-01-05.parquet"
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-05", periods=24, freq="h", tz="UTC"),
            "temperature_2m": [30.0] * 24,
            "precipitation": [0.0] * 24,
        }
    ).to_parquet(file)
    assert preview.get("/api/metadata").json()["fingerprint"] == old["fingerprint"]
    (folder / "_source-2024-01-05-2024-01-05.json").write_text(
        json.dumps(
            {
                "request": {
                    "location_id": "a",
                    "start": "2024-01-05",
                    "end": "2024-01-05",
                }
            }
        )
    )
    fresh = preview.get("/api/metadata").json()
    assert fresh["end"] == "2024-01-05"
    assert fresh["fingerprint"] != old["fingerprint"]
    assert query(preview, fingerprint=old["fingerprint"]).status_code == 409
    assert query(preview, start="2024-01-05", end="2024-01-05").json()["records"][0]["value"] == 0


@pytest.mark.parametrize("period", ["weekly", "monthly", "yearly"])
def test_periods_preserve_missing_days_and_aggregate_complete_selection(preview, tmp_path, period):
    response = query(preview, period=period, end="2024-01-04")
    assert response.status_code == 200
    assert response.json()["period"] == period
    assert response.json()["records"][0]["value"] is None
    # Complete the missing days, then verify totals and means across the period.
    path = tmp_path / "raw/weather/location_id=a/year=2024/weather.parquet"
    frame = pd.read_parquet(path)
    frame = pd.concat([frame, pd.DataFrame({
        "timestamp": pd.date_range("2024-01-02T23:00Z", periods=25, freq="h"),
        "temperature_2m": [30.0] + [25.0] * 24,
        "precipitation": [2.0] * 25,
    })], ignore_index=True)
    frame.to_parquet(path, index=False)
    refreshed = TestClient(create_app(raw_root=tmp_path))
    rows = query(refreshed, period=period, end="2024-01-04").json()["records"]
    assert rows == [{"location_id": "a", "date": "2024-01-01", "value": 168.0, "hours": 96}]
    assert query(refreshed, period=period, end="2024-01-04", metric="temperature_2m").json()["records"][0]["value"] == 25.0
    assert query(refreshed, period="unsupported").status_code == 422


@pytest.mark.parametrize('aggregation,expected', [('mean', 36.0), ('min', 24.0), ('max', 48.0), ('sum', 72.0)])
def test_selectable_period_aggregation(preview, tmp_path, aggregation, expected):
    path = tmp_path / 'raw/weather/location_id=a/year=2024/weather.parquet'
    frame = pd.read_parquet(path)
    frame = frame[frame.timestamp.dt.day.isin([1, 4])].copy()
    frame.loc[frame.timestamp.dt.day == 4, 'timestamp'] -= pd.Timedelta(days=2)
    frame.to_parquet(path, index=False)
    client = TestClient(create_app(raw_root=tmp_path))
    response = query(client, end='2024-01-02', period='weekly', aggregation=aggregation)
    assert response.status_code == 200
    assert response.json()['aggregation'] == aggregation
    assert response.json()['records'][0]['value'] == expected
    assert query(client, aggregation='invalid').status_code == 422
    assert query(client, metric='temperature_2m', aggregation='sum').status_code == 422


def test_analytics_complete_days_and_validation(preview):
    params = {"metric": "temperature_2m", "start": "2024-01-01", "end": "2024-01-04", "locations": ["a"]}
    response = preview.get('/api/analytics', params=params)
    assert response.status_code == 200
    data = response.json()['metrics']['temperature_2m']
    assert data['stats']['count'] == 2
    assert data['stats']['mean'] == 22.5
    assert data['stats']['variance'] == 6.25
    assert data['timeline']['weekly'][0]['count'] == 2
    assert preview.get('/api/analytics', params={**params, 'fingerprint': 'old'}).status_code == 409
    assert preview.get('/api/analytics', params={**params, 'locations': ['missing']}).status_code == 422
    assert preview.get('/api/analytics', params={**params, 'metric': 'missing'}).status_code == 422
    empty = preview.get('/api/analytics', params={**params, 'start': '2024-01-03', 'end': '2024-01-03'})
    assert empty.status_code == 200
    assert empty.json()['metrics']['temperature_2m']['stats'] is None
