"""Read-only explorer API with bounded Spark jobs for plain-English analysis."""

import hashlib
import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from time import perf_counter
from typing import Annotated

import pandas as pd
import pyarrow.dataset as ds
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from weather_analysis.ask import AskRequest, answer
from weather_analysis.charts import preview_catalog
from weather_analysis.dashboard_charts import METRICS as DASHBOARD_METRICS, summarize
from weather_analysis.storage import ATTRIBUTION, DatasetStore

# Aggregations have explicit units; directional/categorical variables are not averaged.
FEATURES = {
    "temperature_2m": ("Temperature", "°C", "mean"),
    "precipitation": ("Precipitation", "mm/day", "sum"),
    "relative_humidity_2m": ("Relative humidity", "%", "mean"),
    "wind_speed_10m": ("Wind speed · 10 m", "m/s", "mean"),
    "apparent_temperature": ("Feels-like temperature", "°C", "mean"),
    "dew_point_2m": ("Dew point", "°C", "mean"),
    "cloud_cover": ("Cloud cover", "%", "mean"),
    "surface_pressure": ("Surface pressure", "hPa", "mean"),
    "soil_temperature_0_to_7cm": ("Soil temperature · 0–7 cm", "°C", "mean"),
    "soil_moisture_0_to_7cm": ("Soil moisture · 0–7 cm", "m³/m³", "mean"),
    "shortwave_radiation": ("Shortwave radiation", "W/m²", "mean"),
    "snow_depth": ("Snow depth", "m", "mean"),
}


class ExplorerData:
    def __init__(self, root, raw_root=None):
        self.store = None if raw_root else DatasetStore(root)
        self.path = (
            Path(raw_root) / "raw/weather"
            if raw_root
            else self.store.table_path("enriched_weather")
        )
        catalog = preview_catalog(raw_root) if raw_root else []
        if raw_root and not catalog:
            raise ValueError("No committed weather chunks yet")
        self.dataset = ds.dataset(
            [c["path"] for c in catalog] if raw_root else self.path,
            format="parquet",
            partitioning="hive",
            partition_base_dir=str(self.path.resolve()),
        )
        self.locations = (
            pd.read_parquet(Path(raw_root) / "raw/locations")
            if raw_root
            else self.store.read("locations")
        )
        if raw_root:
            self.version = "unpublished-preview"
            self.fingerprint = hashlib.sha256(
                repr(
                    tuple(
                        (
                            c["path"],
                            Path(c["path"]).stat().st_size,
                            Path(c["path"]).stat().st_mtime_ns,
                        )
                        for c in catalog
                    )
                ).encode()
            ).hexdigest()
            self.start = date.fromisoformat(min(c["start"] for c in catalog))
            self.end = date.fromisoformat(max(c["end"] for c in catalog))
        else:
            self.version = self.store.version
            self.fingerprint = self.store.manifest["fingerprint"]
            coverage = self.store.manifest["coverage"]
            self.start = date.fromisoformat(coverage["start"][:10])
            self.end = date.fromisoformat(coverage["end"][:10])
        self.features = {k: v for k, v in FEATURES.items() if k in self.dataset.schema.names}
        self.window = lru_cache(maxsize=32)(self._window)
        self.analytics = lru_cache(maxsize=8)(self._analytics)

    def metadata(self):
        fields = [
            "location_id",
            "name",
            "country",
            "region",
            "latitude",
            "longitude",
            "elevation_m",
        ]
        return {
            "version": self.version,
            "fingerprint": self.fingerprint,
            "preview": self.store is None,
            "start": str(self.start),
            "end": str(self.end),
            "attribution": ATTRIBUTION,
            "locations": json.loads(self.locations[fields].to_json(orient="records")),
            "features": [
                {"id": k, "label": v[0], "unit": v[1], "aggregation": v[2]}
                for k, v in self.features.items()
            ],
        }

    def _analytics(self, metric, start, end, locations):
        if metric not in self.features:
            raise ValueError("Choose an available weather feature.")
        if start > end or (end - start).days >= 3660 or start < self.start or end > self.end:
            raise ValueError("Choose 1–3660 days within dataset coverage.")
        if not locations or len(locations) > 100 or set(locations) - set(self.locations.location_id):
            raise ValueError("Choose 1–100 known locations.")
        metrics = list(dict.fromkeys([metric, *[m for m in DASHBOARD_METRICS if m in self.features]]))
        predicate = (ds.field("timestamp") >= pd.Timestamp(start, tz="UTC")) & (
            ds.field("timestamp") < pd.Timestamp(end + timedelta(days=1), tz="UTC")
        ) & ds.field("location_id").isin(locations)
        if "year" in self.dataset.schema.names:
            predicate &= ds.field("year").isin(list(range(start.year, end.year + 1)))
        # Reduce bounded chunks before concatenation: never retain a multi-year hourly scan.
        daily_frames = []
        cursor = start
        while cursor <= end:
            stop = min(cursor + timedelta(days=31), end + timedelta(days=1))
            chunk_filter = predicate & (ds.field("timestamp") >= pd.Timestamp(cursor, tz="UTC")) & (ds.field("timestamp") < pd.Timestamp(stop, tz="UTC"))
            frame = self.dataset.to_table(columns=["location_id", "timestamp", *metrics], filter=chunk_filter).to_pandas()
            frame["date"] = pd.to_datetime(frame.timestamp, utc=True).dt.strftime("%Y-%m-%d")
            groups = frame.groupby(["location_id", "date"])[metrics]
            daily = groups.agg({m: "sum" if m == "precipitation" else "mean" for m in metrics}).where(groups.count() == 24)
            daily_frames.append(daily.reset_index())
            cursor = stop
        daily = pd.concat(daily_frames, ignore_index=True)
        selected = self.locations[self.locations.location_id.isin(locations)]
        return summarize(daily, selected, metrics, daily_values=True)

    def _window(self, metric, start, end, locations, period="daily", aggregation="auto"):
        if metric not in self.features:
            raise ValueError("Choose an available weather feature.")
        aggregation = self.features[metric][2] if aggregation == "auto" else aggregation
        if aggregation not in {"mean", "min", "max", "sum"}:
            raise ValueError("Choose mean, minimum, maximum, or total.")
        if aggregation == "sum" and self.features[metric][2] != "sum":
            raise ValueError("Totals are available only for precipitation.")
        limits = {"daily": 93, "weekly": 366, "monthly": 1096, "yearly": 3660}
        if period not in limits:
            raise ValueError("Choose daily, weekly, monthly, or yearly.")
        if start > end or (end - start).days >= limits[period]:
            raise ValueError(f"Request a range of 1–{limits[period]} days.")
        if start < self.start or end > self.end:
            raise ValueError("Dates must be inside the dataset coverage.")
        if not locations or len(locations) > 100:
            raise ValueError("Choose 1–100 locations.")
        if set(locations) - set(self.locations.location_id):
            raise ValueError("Unknown location.")
        field = ds.field("timestamp")
        predicate = (field >= pd.Timestamp(start, tz="UTC")) & (
            field < pd.Timestamp(end + timedelta(days=1), tz="UTC")
        )
        predicate &= ds.field("location_id").isin(locations)
        # The raw dataset is partitioned by year as well as location.
        if "year" in self.dataset.schema.names:
            predicate &= ds.field("year").isin(list(range(start.year, end.year + 1)))
        frame = self.dataset.to_table(
            columns=["location_id", "timestamp", metric], filter=predicate
        ).to_pandas()
        input_rows = len(frame)
        if frame.empty:
            records = []
        else:
            frame["date"] = pd.to_datetime(frame.timestamp, utc=True).dt.strftime("%Y-%m-%d")
            grouped = frame.groupby(["location_id", "date"])[metric]
            counts = grouped.count()
            values = (
                grouped.sum(min_count=1) if self.features[metric][2] == "sum" else grouped.mean()
            )
            # Incomplete UTC days stay missing; especially important for rainfall totals.
            values = values.where(counts == 24)
            result = pd.DataFrame({"value": values, "hours": counts}).reset_index()
            if period != "daily":
                frequency = {"weekly": "W-SUN", "monthly": "M", "yearly": "Y"}[period]
                result["period"] = pd.to_datetime(result.date).dt.to_period(frequency)
                buckets = result.groupby(["location_id", "period"])
                totals = buckets.value.sum(min_count=1) if aggregation == "sum" else buckets.value.agg(aggregation)
                expected = pd.Series([
                    (min(bucket.end_time.date(), end) - max(bucket.start_time.date(), start)).days + 1
                    for _, bucket in totals.index
                ], index=totals.index)
                totals = totals.where(buckets.value.count() == expected)
                result = pd.DataFrame({"value": totals, "hours": buckets.hours.sum()}).reset_index()
                result["date"] = result.period.dt.start_time.dt.strftime("%Y-%m-%d")
                result = result.drop(columns="period")
            records = json.loads(result.to_json(orient="records"))
        return {
            "metric": metric,
            "period": period,
            "aggregation": aggregation,
            "start": str(start),
            "end": str(end),
            "version": self.version,
            "fingerprint": self.fingerprint,
            "input_rows": input_rows,
            "records": records,
        }


def create_app(root="data/platform", raw_root=None, static_dir=None):
    app = FastAPI(title="Big Weather Explorer", version="0.1.0")

    @lru_cache(maxsize=1)
    def cached_source(revision):
        try:
            return ExplorerData(root, raw_root)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(
                503,
                "No usable dataset. Publish a release or run the explicitly "
                "labelled raw preview with make explorer-raw.",
            ) from exc

    def source():
        if raw_root:
            # A metadata commit is the publication boundary for a raw preview file.
            revisions = tuple(
                (str(p), p.stat().st_mtime_ns)
                for p in sorted(
                    (Path(raw_root) / "raw/weather").glob("location_id=*/year=*/_source*.json")
                )
            )
        else:
            active = Path(root) / "active.json"
            revisions = active.stat().st_mtime_ns if active.exists() else None
        return cached_source(revisions)

    @app.get("/api/metadata")
    def metadata():
        return source().metadata()

    @app.get("/api/window")
    def window(
        metric: str,
        start: date,
        end: date,
        locations: Annotated[list[str], Query(min_length=1, max_length=100)],
        fingerprint: str | None = None,
        period: str = "daily",
        aggregation: str = "auto",
    ):
        data = source()
        if fingerprint is not None and fingerprint != data.fingerprint:
            raise HTTPException(409, "Dataset changed. Reload the explorer.")
        started = perf_counter()
        try:
            result = data.window(metric, start, end, tuple(sorted(set(locations))), period, aggregation)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {**result, "query_ms": round((perf_counter() - started) * 1000, 2)}

    @app.get("/api/analytics")
    def analytics(
        metric: str, start: date, end: date,
        locations: Annotated[list[str], Query(min_length=1, max_length=100)],
        fingerprint: str | None = None,
    ):
        data = source()
        if fingerprint is not None and fingerprint != data.fingerprint:
            raise HTTPException(409, "Dataset changed. Reload the explorer.")
        try:
            return data.analytics(metric, start, end, tuple(sorted(set(locations))))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/ask/status")
    def ask_status():
        import os

        if os.getenv("WEATHER_AI_PROVIDER", "codex") == "codex":
            from .codex_demo import status

            return status()
        return {
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "provider": "openai",
            "message": "OpenAI API: set OPENAI_API_KEY on the server if not configured.",
        }

    @app.post("/api/ask")
    def ask(request: AskRequest):
        try:
            return answer(request.question, source(), raw_root or root)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(503, str(exc)) from exc
        except Exception as exc:
            # Provider errors can contain request details; do not expose credentials or prompts.
            raise HTTPException(
                502,
                "The analysis provider could not complete this request. Check its sign-in and usage limits.",
            ) from exc

    if static_dir and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="explorer")
    return app


def main():
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="data/platform")
    parser.add_argument("--raw-root", help="Explicitly preview incomplete downloaded data")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--static-dir", default="explorer/dist")
    args = parser.parse_args()
    uvicorn.run(
        create_app(args.root, args.raw_root, args.static_dir), host="127.0.0.1", port=args.port
    )


if __name__ == "__main__":
    main()
