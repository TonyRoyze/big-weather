"""Publish immutable local snapshots; readers resolve one version per request."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import uuid

import pandas as pd
import pyarrow.dataset as ds

TABLES = (
    "locations",
    "enriched_weather",
    "daily_metrics",
    "summaries",
    "yearly_metrics",
    "lapse_rates",
)
ATTRIBUTION = "Open-Meteo; ERA5 (Copernicus/ECMWF); elevation: Copernicus DEM GLO-90 (2021)."
REQUIRED = {
    "locations": {
        "location_id",
        "name",
        "country",
        "region",
        "latitude",
        "longitude",
        "elevation_m",
    },
    "enriched_weather": {
        "location_id",
        "timestamp",
        "date",
        "year",
        "season",
        "region",
        "elevation_band",
        "temperature_2m",
        "precipitation",
        "wind_speed_10m",
        "relative_humidity_2m",
    },
    "daily_metrics": {
        "location_id",
        "name",
        "region",
        "date",
        "elevation_m",
        "elevation_band",
        "season",
        "daily_avg_temperature_c",
        "daily_precipitation_mm",
        "daily_avg_wind_speed_ms",
        "temperature_30d_rolling_avg_c",
    },
    "summaries": {
        "elevation_band",
        "region",
        "season",
        "year",
        "avg_temperature_c",
        "total_precipitation_mm",
        "avg_wind_speed_ms",
        "avg_relative_humidity_pct",
        "observation_count",
    },
    "yearly_metrics": {
        "location_id",
        "name",
        "year",
        "annual_avg_temperature_c",
        "temperature_yoy_change_c",
    },
    "lapse_rates": {
        "season",
        "slope_c_per_m",
        "lapse_rate_c_per_km",
        "intercept_c",
        "r2",
        "rmse_c",
        "sample_size",
    },
}


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", value):
        raise ValueError("Use 1–80 letters, digits, underscores or hyphens for identifiers")
    return value


def atomic_json(path: Path, value: dict) -> None:
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(temp, path)


def publish(data_root: Path, store_root: Path, version: str) -> dict:
    """Snapshot completed PySpark outputs, validate key integrity, then activate.

    Run only after ingestion/processing finish. Existing versions are never replaced.
    Hash every copied Parquet file so manifests identify actual data, not just labels.
    """
    study_plan = data_root / "study-plan.json"
    if study_plan.exists():
        state = json.loads((data_root / "ingestion-status.json").read_text())
        if state["status"] != "complete":
            raise ValueError("Regional ingestion is incomplete")
    identifier(version)
    releases = store_root / "releases"
    releases.mkdir(parents=True, exist_ok=True)
    target = releases / version
    if target.exists():
        raise FileExistsError(f"Dataset version already exists: {version}")
    stage = releases / f".staging-{uuid.uuid4().hex}"
    stage.mkdir()
    try:
        tables, checksums = {}, {}
        for name in TABLES:
            source = data_root / ("raw/locations" if name == "locations" else f"processed/{name}")
            if not source.is_dir() or not list(source.rglob("*.parquet")):
                raise ValueError(f"Missing Parquet dataset: {source}")
            shutil.copytree(source, stage / name)
            dataset = ds.dataset(stage / name, format="parquet", partitioning="hive")
            missing = REQUIRED[name] - set(dataset.schema.names)
            if missing:
                raise ValueError(f"{name} is missing required columns: {sorted(missing)}")
            tables[name] = {"rows": dataset.count_rows(), "schema": str(dataset.schema)}
            for file in sorted((stage / name).rglob("*.parquet")):
                with file.open("rb") as handle:
                    checksums[str(file.relative_to(stage))] = hashlib.file_digest(
                        handle, "sha256"
                    ).hexdigest()
        locations = pd.read_parquet(stage / "locations")
        weather = pd.read_parquet(stage / "enriched_weather", columns=["location_id", "timestamp"])
        daily = pd.read_parquet(stage / "daily_metrics", columns=["location_id", "date"])
        if locations.empty or weather.empty or daily.empty:
            raise ValueError("Cannot publish an empty dataset")
        if locations.location_id.duplicated().any() or locations.location_id.isna().any():
            raise ValueError("Locations must have unique non-null identifiers")
        if weather.isna().any().any() or weather.duplicated().any():
            raise ValueError("Hourly location/timestamp keys must be unique and non-null")
        if daily.isna().any().any() or daily.duplicated().any():
            raise ValueError("Daily location/date keys must be unique and non-null")
        if not set(weather.location_id).issubset(set(locations.location_id)):
            raise ValueError("Weather contains unknown locations")
        weather["timestamp"] = pd.to_datetime(weather.timestamp, utc=True)
        expected_hours = (
            int((weather.timestamp.max() - weather.timestamp.min()).total_seconds() / 3600) + 1
        )
        counts = weather.groupby("location_id").size()
        coverage_by_location = [
            {
                "location_id": loc,
                "observed_hours": int(counts.get(loc, 0)),
                "expected_hours_in_study_window": expected_hours,
                "missing_hours_in_study_window": expected_hours - int(counts.get(loc, 0)),
            }
            for loc in sorted(locations.location_id)
        ]
        fingerprint = hashlib.sha256(json.dumps(checksums, sort_keys=True).encode()).hexdigest()
        manifest = {
            "version": version,
            "fingerprint": fingerprint,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "coverage": {
                "start": weather.timestamp.min().isoformat(),
                "end": weather.timestamp.max().isoformat(),
            },
            "tables": tables,
            "checksums": checksums,
            "attribution": ATTRIBUTION,
            "quality": {
                "duplicate_hourly_keys": 0,
                "duplicate_daily_keys": 0,
                "unknown_locations": 0,
                "coverage_by_location": coverage_by_location,
            },
        }
        if study_plan.exists():
            plan = json.loads(study_plan.read_text())
            if len(weather) != plan["expected_rows"] or set(locations.location_id) != {
                loc["location_id"] for loc in plan["locations"]
            }:
                raise ValueError("Processed data does not cover the complete regional study")
            if any(c["missing_hours_in_study_window"] for c in coverage_by_location):
                raise ValueError("Regional study has missing hourly observations")
            manifest["study"] = plan
            manifest["attribution"] += " Regional model: ERA5-Seamless (ERA5 + ERA5-Land)."
            shutil.copytree(data_root / "raw/weather", stage / "source_metadata",
                            ignore=lambda path, names: [n for n in names if not (n.startswith("_source") and n.endswith(".json"))
                                and not (Path(path) / n).is_dir()])
        metrics = data_root / "processed/pipeline_metrics.json"
        if metrics.exists():
            manifest["pipeline"] = json.loads(metrics.read_text())
        atomic_json(stage / "manifest.json", manifest)
        stage.rename(target)
        atomic_json(store_root / "active.json", {"version": version})
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)


class DatasetStore:
    """Use one instance for a consistent release across all reads in a page/job."""

    def __init__(self, root: Path | str = "data/platform", version: str | None = None):
        self.root = Path(root)
        if version is None:
            try:
                version = json.loads((self.root / "active.json").read_text())["version"]
            except FileNotFoundError as exc:
                raise FileNotFoundError("No published dataset. Run make publish first.") from exc
        self.version = identifier(version)
        self.path = self.root / "releases" / self.version
        self.manifest = json.loads((self.path / "manifest.json").read_text())

    def table_path(self, name: str) -> Path:
        if name not in TABLES:
            raise ValueError(f"Unknown dataset: {name}")
        return self.path / name

    def read(self, name: str, columns=None, filters=None) -> pd.DataFrame:
        return pd.read_parquet(self.table_path(name), columns=columns, filters=filters)

    def get_overview(self) -> dict:
        return self.manifest.copy()
