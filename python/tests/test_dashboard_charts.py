import pandas as pd
import pytest

from weather_analysis.dashboard_charts import summarize


def locations(high=2000):
    return pd.DataFrame([
        {"location_id": "a", "name": "Coast", "elevation_m": 0},
        {"location_id": "b", "name": "Peak", "elevation_m": high},
    ])


def test_daily_statistics_and_calendar_buckets():
    frame = pd.DataFrame({"location_id": ["a"] * 3, "date": ["2024-01-31", "2024-02-01", "2024-02-02"], "wind_speed_10m": [2., 4., None]})
    result = summarize(frame, locations(), ["wind_speed_10m"], daily_values=True)
    data = result["metrics"]["wind_speed_10m"]
    assert len(result["bands"]) == 4
    assert data["stats"] == {"count": 2, "mean": 3., "min": 2., "max": 4., "median": 3., "variance": 1.}
    assert data["timeline"]["weekly"] == [{"band": 0, "bucket": "2024-01-29", "mean": 3., "count": 2, "variance": 1.}]
    assert [r["bucket"] for r in data["timeline"]["monthly"]] == ["2024-01-01", "2024-02-01"]
    assert sum(b["count"] for b in data["histogram"]) == 2
    assert data["scatter"][0]["mean"] == 3


def test_high_region_single_value_and_missing_values():
    frame = pd.DataFrame({"location_id": ["b"], "date": ["2024-01-01"], "surface_pressure": [800.], "wind_speed_10m": [None]})
    result = summarize(frame, locations(4000), ["surface_pressure", "wind_speed_10m"], daily_values=True)
    assert len(result["bands"]) == 5
    assert result["metrics"]["surface_pressure"]["scatter"][0]["band"] == 4
    assert result["metrics"]["surface_pressure"]["stats"]["variance"] == 0
    assert result["metrics"]["wind_speed_10m"]["stats"] is None
    assert result["metrics"]["wind_speed_10m"]["timeline"]["daily"] == []


def test_incomplete_hours_excluded():
    frame = pd.DataFrame({"location_id": ["a"] * 47, "date": ["2024-01-01"] * 24 + ["2024-01-02"] * 23, "wind_speed_10m": [2.] * 24 + [10.] * 23})
    data = summarize(frame, locations(), ["wind_speed_10m"])["metrics"]["wind_speed_10m"]
    assert data["stats"]["count"] == 1
    assert data["stats"]["mean"] == 2
