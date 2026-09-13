"""Small offline dataset with independently known temperature means."""

from datetime import date

import pandas as pd
import pytest

from weather_analysis.storage import publish


@pytest.fixture
def published(tmp_path):
    source = tmp_path / "source"
    raw = source / "raw/locations"
    raw.mkdir(parents=True)
    locations = pd.DataFrame(
        [
            dict(
                location_id="a",
                name="Coast",
                country="Test",
                region="North",
                latitude=10.0,
                longitude=20.0,
                elevation_m=10.0,
            ),
            dict(
                location_id="b",
                name="Hill",
                country="Test",
                region="North",
                latitude=11.0,
                longitude=21.0,
                elevation_m=1500.0,
            ),
        ]
    )
    locations.to_parquet(raw / "locations.parquet", index=False)
    records = []
    for location, temps, band in [("a", [20.0, 22.0], "lowland"), ("b", [10.0, 12.0], "highland")]:
        for day, temp in enumerate(temps, 1):
            record = locations.set_index("location_id").loc[location].to_dict()
            record.update(
                location_id=location,
                temperature_2m=temp,
                precipitation=float(day),
                wind_speed_10m=2.0,
                relative_humidity_2m=70.0,
                season="winter",
                year=2024,
                source_year=2024,
                date=date(2024, 1, day),
                elevation_band=band,
                timestamp=pd.Timestamp(f"2024-01-0{day}", tz="UTC"),
            )
            records.append(record)
    hourly = pd.DataFrame(records)
    daily = hourly.rename(
        columns={
            "temperature_2m": "daily_avg_temperature_c",
            "precipitation": "daily_precipitation_mm",
            "wind_speed_10m": "daily_avg_wind_speed_ms",
        }
    )
    daily["temperature_30d_rolling_avg_c"] = daily.daily_avg_temperature_c
    yearly = locations.assign(
        year=2024, annual_avg_temperature_c=[21.0, 11.0], temperature_yoy_change_c=float("nan")
    )
    lapse = pd.DataFrame(
        [
            dict(
                season="winter",
                slope_c_per_m=-0.0067,
                lapse_rate_c_per_km=-6.7,
                intercept_c=21.0,
                r2=0.9,
                rmse_c=1.0,
                sample_size=4,
            )
        ]
    )
    summaries = pd.DataFrame(
        [
            dict(
                elevation_band="lowland",
                region="North",
                season="winter",
                year=2024,
                avg_temperature_c=21.0,
                total_precipitation_mm=3.0,
                avg_wind_speed_ms=2.0,
                avg_relative_humidity_pct=70.0,
                observation_count=2,
            )
        ]
    )
    for name, frame in {
        "enriched_weather": hourly,
        "daily_metrics": daily,
        "yearly_metrics": yearly,
        "lapse_rates": lapse,
        "summaries": summaries,
    }.items():
        folder = source / "processed" / name
        folder.mkdir(parents=True)
        frame.to_parquet(folder / "part.parquet", index=False, coerce_timestamps="us")
    root = tmp_path / "platform"
    publish(source, root, "test-v1")
    return source, root
