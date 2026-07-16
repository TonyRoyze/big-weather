from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .client import HOURLY_VARIABLES, OpenMeteoClient, OpenMeteoError


@dataclass(frozen=True)
class LocationSeed:
    location_id: str
    query: str
    country_code: str
    region: str


def load_seeds(path: Path) -> list[LocationSeed]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [LocationSeed(**row) for row in csv.DictReader(handle)]


def resolve_locations(seeds: list[LocationSeed], client: OpenMeteoClient) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for seed in seeds:
        result = client.geocode(seed.query, seed.country_code)
        latitude = float(result["latitude"])
        longitude = float(result["longitude"])
        records.append(
            {
                "location_id": seed.location_id,
                "name": result["name"],
                "country": result.get("country", seed.country_code),
                "country_code": seed.country_code,
                "region": seed.region,
                "latitude": latitude,
                "longitude": longitude,
                "elevation_m": client.elevation(latitude, longitude),
                "timezone": result.get("timezone", "UTC"),
            }
        )
    locations = pd.DataFrame.from_records(records)
    if locations["location_id"].duplicated().any():
        raise ValueError("location_id values must be unique")
    return locations


def weather_frame(payload: dict[str, object], location_id: str, year: int) -> pd.DataFrame:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise OpenMeteoError(f"historical response for {location_id}/{year} has no hourly data")
    expected = {"time", *HOURLY_VARIABLES}
    missing = expected.difference(hourly)
    if missing:
        raise OpenMeteoError(f"historical response missing fields: {sorted(missing)}")
    frame = pd.DataFrame({key: hourly[key] for key in expected})
    frame = frame.rename(columns={"time": "timestamp"})
    frame.insert(0, "location_id", location_id)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["source_year"] = year
    frame["ingested_at"] = datetime.now(timezone.utc)
    return frame[
        [
            "location_id",
            "timestamp",
            "temperature_2m",
            "precipitation",
            "wind_speed_10m",
            "relative_humidity_2m",
            "source_year",
            "ingested_at",
        ]
    ]


def ingest(
    locations: pd.DataFrame,
    client: OpenMeteoClient,
    data_root: Path,
    start_date: date,
    end_date: date,
) -> tuple[int, int]:
    if end_date < start_date:
        raise ValueError("end date must not precede start date")
    locations_path = data_root / "raw" / "locations"
    locations_path.mkdir(parents=True, exist_ok=True)
    locations.to_parquet(locations_path / "locations.parquet", index=False)

    files_written = 0
    rows_written = 0
    for row in locations.itertuples(index=False):
        for year in range(start_date.year, end_date.year + 1):
            chunk_start = max(start_date, date(year, 1, 1))
            chunk_end = min(end_date, date(year, 12, 31))
            payload = client.historical_weather(
                row.latitude, row.longitude, chunk_start.isoformat(), chunk_end.isoformat()
            )
            frame = weather_frame(payload, row.location_id, year)
            output_dir = (
                data_root / "raw" / "weather" / f"location_id={row.location_id}" / f"year={year}"
            )
            output_dir.mkdir(parents=True, exist_ok=True)
            # Partition keys live in the Hive-style path and are discovered by Spark.
            frame.drop(columns=["location_id"]).to_parquet(
                output_dir / "weather.parquet",
                index=False,
                coerce_timestamps="us",
                allow_truncated_timestamps=True,
            )
            files_written += 1
            rows_written += len(frame)
    return files_written, rows_written
