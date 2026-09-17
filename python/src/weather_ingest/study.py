"""Resumable, quota-aware import for the pinned regional study.

One writer per study; a shared quota ledger serializes this importer across roots.
Run `big-weather --watch` to download the regional study.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import re
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from weather_analysis.storage import atomic_json

from .variables import ARCHIVE_VARIABLES, MODEL

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"


class OpenMeteoError(RuntimeError):
    pass


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_locations(path):
    frame = pd.read_csv(path)
    required = {"location_id", "query", "country_code", "region", "latitude", "longitude"}
    if required - set(frame.columns) or frame.empty or frame.isna().any().any():
        raise ValueError("Location CSV must contain complete identifiers, names and coordinates")
    if frame.location_id.duplicated().any() or frame[["latitude", "longitude"]].duplicated().any():
        raise ValueError("Locations and coordinates must be unique")
    if not frame.location_id.map(lambda x: bool(re.fullmatch(r"[a-z0-9_]+", x))).all():
        raise ValueError("Location identifiers must use lowercase letters, digits and underscores")
    if not frame.latitude.between(-90, 90).all() or not frame.longitude.between(-180, 180).all():
        raise ValueError("Invalid coordinates")
    return frame


def study_plan(locations, start, end):
    if end < start:
        raise ValueError("End date must not precede start date")
    chunks = []
    for row in locations.itertuples(index=False):
        for year in range(start.year, end.year + 1):
            first, last = max(start, date(year, 1, 1)), min(end, date(year, 12, 31))
            chunks.append(
                {
                    "location_id": row.location_id,
                    "latitude": float(row.latitude),
                    "longitude": float(row.longitude),
                    "year": year,
                    "start": first.isoformat(),
                    "end": last.isoformat(),
                    "hours": ((last - first).days + 1) * 24,
                }
            )
    return {
        "model": MODEL,
        "variables": list(ARCHIVE_VARIABLES),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "tilt": 0,
        "azimuth": 0,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "locations": locations.to_dict("records"),
        "chunks": chunks,
        "expected_rows": sum(c["hours"] for c in chunks),
        "estimated_weighted_calls": sum(request_cost(c) for c in chunks),
    }


def chunk_paths(root, chunk):
    directory = (
        Path(root) / "raw/weather" / f"location_id={chunk['location_id']}" / f"year={chunk['year']}"
    )
    suffix = f"-{chunk['start']}-{chunk['end']}" if "window_start" in chunk else ""
    return directory / f"weather{suffix}.parquet", directory / f"_source{suffix}.json"


def verified_chunks(root, plan):
    """Validate committed checkpoints before reusing them or changing the schedule."""
    complete = []
    for chunk in plan["chunks"]:
        output, metadata = chunk_paths(root, chunk)
        if output.exists() and metadata.exists():
            saved = json.loads(metadata.read_text())
            if saved["request"] != chunk or saved["sha256"] != digest(output):
                raise ValueError(f"Checkpoint mismatch: {output}; inspect before resuming")
            complete.append(chunk)
        elif output.exists() or metadata.exists():
            # A normal resume retries an uncommitted pair. Migration must not orphan it.
            continue
    return complete


def latest_first_plan(locations, start, end, retained=(), window_days=7):
    """Sweep every location for a recent window before requesting an older window.

    Retained chunks are verified legacy yearly files. Subtract their intervals so
    existing downloads and new weekly files never contain overlapping hours.
    """
    if not 1 <= window_days <= 31:
        raise ValueError("Window size must be 1–31 days")
    plan = study_plan(locations, start, end)
    chunks = []
    last = end
    while last >= start:
        first = max(start, date(last.year, 1, 1), last - timedelta(days=window_days - 1))
        for row in locations.itertuples(index=False):
            gaps = [(first, last)]
            for old in retained:
                if old["location_id"] != row.location_id:
                    continue
                old_start, old_end = (
                    date.fromisoformat(old["start"]),
                    date.fromisoformat(old["end"]),
                )
                remaining = []
                for a, b in gaps:
                    if old_end < a or old_start > b:
                        remaining.append((a, b))
                    else:
                        if a < old_start:
                            remaining.append((a, old_start - timedelta(days=1)))
                        if b > old_end:
                            remaining.append((old_end + timedelta(days=1), b))
                gaps = remaining
            for a, b in reversed(gaps):
                chunks.append(
                    {
                        "location_id": row.location_id,
                        "latitude": float(row.latitude),
                        "longitude": float(row.longitude),
                        "year": a.year,
                        "start": str(a),
                        "end": str(b),
                        "hours": ((b - a).days + 1) * 24,
                        "window_start": str(first),
                        "window_end": str(last),
                    }
                )
        last = first - timedelta(days=1)
    plan.update(
        schedule="latest-first",
        window_days=window_days,
        archive_delay_days=5,
        chunks=[*chunks, *retained],
    )
    plan["estimated_weighted_calls"] = sum(request_cost(c) for c in plan["chunks"])
    if sum(c["hours"] for c in plan["chunks"]) != plan["expected_rows"]:
        raise ValueError("Retained checkpoints must lie inside the requested date range")
    return plan


def build_plan(locations, root, start=None, end=None, schedule="latest-first", window_days=None):
    """Pin the initial latest date; resume the same window boundaries on later days."""
    path = Path(root) / "study-plan.json"
    saved = json.loads(path.read_text()) if path.exists() else None
    start = start or (date.fromisoformat(saved["start"]) if saved else date(2020, 1, 1))
    if end is None:
        end = (
            date.fromisoformat(saved["end"])
            if saved and (saved.get("schedule") == "latest-first" or schedule == "location-year")
            else datetime.now(UTC).date() - timedelta(days=5)
            if schedule == "latest-first"
            else date(2025, 12, 31)
        )
    if window_days is None:
        window_days = saved.get("window_days", 7) if saved else 7
    if schedule == "location-year":
        return study_plan(locations, start, end)
    if end > datetime.now(UTC).date() - timedelta(days=5):
        raise ValueError("ERA5-Seamless is delayed by 5 days; choose an earlier end date")
    if saved and saved.get("schedule") == "latest-first":
        # Regenerate with the original legacy chunks, not the newly downloaded weeks.
        retained = [c for c in saved["chunks"] if "window_start" not in c]
    else:
        retained = verified_chunks(root, saved) if saved else []
    return latest_first_plan(locations, start, end, retained, window_days)


def validate_schedule_change(root, old, new):
    """Allow one migration of scheduling/date coverage without touching old files."""
    ignored = {
        "chunks",
        "end",
        "expected_rows",
        "estimated_weighted_calls",
        "schedule",
        "window_days",
        "archive_delay_days",
    }
    if (
        old.get("schedule") == "latest-first"
        or new.get("schedule") != "latest-first"
        or {k: v for k, v in old.items() if k not in ignored}
        != {k: v for k, v in new.items() if k not in ignored}
        or new["end"] < old["end"]
    ):
        raise ValueError(
            "Study configuration changed: use a new data root to prevent mixing datasets"
        )
    retained = verified_chunks(root, old)
    for chunk in old["chunks"]:
        output, metadata = chunk_paths(root, chunk)
        if output.exists() != metadata.exists():
            raise ValueError(
                "Resume the legacy schedule to finish its uncommitted checkpoint first"
            )
    if any(c not in new["chunks"] for c in retained):
        raise ValueError("Schedule migration must retain every completed checkpoint")
    atomic_json(Path(root) / "study-plan-before-latest-first.json", old)


def request_cost(chunk):
    # Round upward; the provider uses fractional weighted counts.
    return math.ceil(max(1, len(ARCHIVE_VARIABLES) / 10) * max(1, chunk["hours"] / 24 / 14))


class QuotaPause(RuntimeError):
    pass


class BudgetClient:
    """Conservative rolling free-tier limits; charges failed attempts too.

    Only this importer shares the ledger; other processes/IP users can also use quota.
    No automatic retries that could bypass accounting, and no credentials in metadata.
    """

    def __init__(self, ledger):
        self.ledger = Path(ledger)
        self.ledger.parent.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "big-weather-regional-study/1 (academic)"

    def get(self, url, params, cost=1):
        with self.ledger.with_suffix(".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            now = time.time()
            events = json.loads(self.ledger.read_text())["events"] if self.ledger.exists() else []
            events = [e for e in events if now - e[0] < 86400]
            for seconds, limit in [(60, 500), (3600, 4500), (86400, 9000)]:
                recent = [e for e in events if now - e[0] < seconds]
                if sum(e[1] for e in recent) + cost > limit:
                    wait = math.ceil(recent[0][0] + seconds - now)
                    raise QuotaPause(f"Local {seconds}s quota budget reached; resume in ~{wait}s")
            events.append([now, cost])
            atomic_json(self.ledger, {"events": events})
        response = self.session.get(url, params=params, timeout=120)
        if response.status_code == 429:
            raise QuotaPause("Provider rate limit reached. Keep completed files and resume later.")
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("error"):
            raise OpenMeteoError(payload.get("reason", "API error"))
        return payload


def frame_from_payload(payload, chunk):
    hourly = payload.get("hourly", {})
    missing = set(ARCHIVE_VARIABLES) - set(hourly)
    if missing or "time" not in hourly:
        raise OpenMeteoError(f"Missing hourly fields: {sorted(missing)}")
    frame = pd.DataFrame({name: hourly[name] for name in ("time", *ARCHIVE_VARIABLES)})
    frame = frame.rename(columns={"time": "timestamp"})
    frame.timestamp = pd.to_datetime(frame.timestamp, utc=True)
    expected = pd.date_range(chunk["start"], periods=chunk["hours"], freq="h", tz="UTC")
    if not pd.DatetimeIndex(frame.timestamp).equals(expected):
        raise OpenMeteoError("Response must contain every requested UTC hour exactly once in order")
    # Explicit float64 keeps all-null variables readable with the same Spark schema.
    for name in ARCHIVE_VARIABLES:
        frame[name] = pd.to_numeric(frame[name], errors="raise").astype("float64")
    frame["source_year"] = chunk["year"]
    frame["ingested_at"] = datetime.now(UTC)
    return frame


class IngestionBusy(RuntimeError):
    """Another process owns this study’s download lock."""


def download(plan, root, client, max_requests=6):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".ingest.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise IngestionBusy(
                f"Another importer is running for {root}. "
                "Keep only one ingestion command running; completed downloads are safe."
            ) from exc
        return _download(plan, root, client, max_requests)


def _download(plan, root, client, max_requests):
    plan_path = root / "study-plan.json"
    if plan_path.exists() and json.loads(plan_path.read_text()) != plan:
        validate_schedule_change(root, json.loads(plan_path.read_text()), plan)
    if not plan_path.exists() and (root / "raw").exists():
        raise ValueError("Use a new data root; untracked raw data already exists")
    atomic_json(plan_path, plan)
    complete = verified_chunks(root, plan)
    completed = {str(chunk_paths(root, c)[0]) for c in complete}
    status = {
        "status": "downloading",
        "schedule": plan.get("schedule", "location-year"),
        "expected_chunks": len(plan["chunks"]),
        "expected_rows": plan["expected_rows"],
        "completed_chunks": len(complete),
        "completed_rows": sum(c["hours"] for c in complete),
    }

    entries = [(c, str(chunk_paths(root, c)[0])) for c in plan["chunks"]]

    def progress():
        pending = [c for c, path in entries if path not in completed]
        if pending and "window_start" in pending[0]:
            current = pending[0]
            remaining = {
                c["location_id"]
                for c in pending
                if c.get("window_start") == current["window_start"]
            }
            status["active_window"] = {
                "start": current["window_start"],
                "end": current["window_end"],
                "completed_locations": len(plan["locations"]) - len(remaining),
                "total_locations": len(plan["locations"]),
            }
        else:
            status.pop("active_window", None)
        atomic_json(root / "ingestion-status.json", status)

    atomic_json(root / "ingestion-status.json", status)
    try:
        location_path = root / "raw/locations/locations.parquet"
        if not location_path.exists():
            locations = pd.DataFrame(plan["locations"]).rename(columns={"query": "name"})
            payload = client.get(
                ELEVATION_URL,
                {
                    "latitude": ",".join(locations.latitude.astype(str)),
                    "longitude": ",".join(locations.longitude.astype(str)),
                },
                cost=len(locations),
            )
            elevations = payload.get("elevation", [])
            if len(elevations) != len(locations) or any(v is None for v in elevations):
                raise OpenMeteoError("Missing location elevations")
            locations["elevation_m"] = elevations
            locations["country"] = locations.country_code
            locations["timezone"] = "UTC"
            location_path.parent.mkdir(parents=True, exist_ok=True)
            temp = location_path.with_suffix(".tmp")
            locations.to_parquet(temp, index=False)
            temp.replace(location_path)
        requests_made = 0
        for chunk in plan["chunks"]:
            output, metadata = chunk_paths(root, chunk)
            if str(output) in completed:
                continue
            if requests_made >= max_requests:
                break
            progress()
            params = dict(
                latitude=chunk["latitude"],
                longitude=chunk["longitude"],
                start_date=chunk["start"],
                end_date=chunk["end"],
                hourly=",".join(plan["variables"]),
                models=plan["model"],
                **{
                    k: plan[k]
                    for k in (
                        "timezone",
                        "wind_speed_unit",
                        "temperature_unit",
                        "precipitation_unit",
                        "tilt",
                        "azimuth",
                    )
                },
            )
            print(
                f"Downloading {chunk['location_id']} / {chunk['start']} to {chunk['end']} "
                f"({chunk['hours']} hours)",
                flush=True,
            )
            payload = client.get(ARCHIVE_URL, params, cost=request_cost(chunk))
            frame = frame_from_payload(payload, chunk)
            # Recent reanalysis can still be unavailable despite the nominal delay.
            # Do not permanently checkpoint an entirely unavailable temperature day.
            if (
                plan.get("schedule") == "latest-first"
                and frame.groupby(frame.timestamp.dt.date).temperature_2m.count().eq(0).any()
            ):
                status["retry_after_seconds"] = 3600
                raise QuotaPause(
                    "Requested reanalysis is not available yet; retry this window later"
                )
            output.parent.mkdir(parents=True, exist_ok=True)
            temp = output.with_suffix(".tmp")
            frame.to_parquet(
                temp, index=False, coerce_timestamps="us", allow_truncated_timestamps=True
            )
            temp.replace(output)
            atomic_json(
                metadata,
                {
                    "request": chunk,
                    "model": plan["model"],
                    "hourly_units": payload.get("hourly_units", {}),
                    "grid": {
                        k: payload.get(k)
                        for k in ("latitude", "longitude", "elevation", "timezone")
                    },
                    "null_counts": {k: int(frame[k].isna().sum()) for k in plan["variables"]},
                    "sha256": digest(output),
                    "downloaded_at": datetime.now(UTC).isoformat(),
                },
            )
            requests_made += 1
            completed.add(str(output))
            status["completed_chunks"] += 1
            status["completed_rows"] += chunk["hours"]
            progress()
        status["status"] = (
            "complete" if status["completed_chunks"] == len(plan["chunks"]) else "paused"
        )
    except QuotaPause as exc:
        status.update(status="paused", reason=str(exc))
    except Exception as exc:
        status.update(status="failed", reason=str(exc))
        raise
    finally:
        progress()
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--locations", type=Path, default=Path("config/locations_regional_100.csv"))
    parser.add_argument("--data-root", type=Path, default=Path("data/regional-2020-2025"))
    parser.add_argument(
        "--start-date", type=date.fromisoformat, help="Defaults to saved start or 2020-01-01"
    )
    parser.add_argument(
        "--end-date",
        type=date.fromisoformat,
        help="Defaults to latest ERA5 date; pinned on first run",
    )
    parser.add_argument(
        "--schedule", choices=["latest-first", "location-year"], default="latest-first"
    )
    parser.add_argument(
        "--window-days", type=int, default=None, help="Days per all-location sweep (1–31)"
    )
    parser.add_argument(
        "--watch", action="store_true", help="Resume batches every minute until complete"
    )
    parser.add_argument("--plan", action="store_true", help="Print plan without network calls")
    parser.add_argument(
        "--max-requests", type=int, default=100, help="Maximum new weather requests in this run"
    )
    parser.add_argument("--ledger", type=Path, default=Path("data/cache/regional-api-usage.json"))
    args = parser.parse_args()
    if args.max_requests < 1:
        parser.error("--max-requests must be positive")
    plan = build_plan(
        load_locations(args.locations),
        args.data_root,
        args.start_date,
        args.end_date,
        args.schedule,
        args.window_days,
    )
    if args.plan:
        print(
            json.dumps(
                {k: v for k, v in plan.items() if k not in ("locations", "chunks")}, indent=2
            )
        )
        print(
            f"{len(plan['locations'])} locations; {len(plan['chunks'])} chunks; schedule: {plan.get('schedule', 'location-year')}"
        )
        return
    client = BudgetClient(args.ledger)
    while True:
        try:
            result = download(plan, args.data_root, client, args.max_requests)
        except IngestionBusy as exc:
            raise SystemExit(str(exc)) from None
        print(json.dumps(result, indent=2), flush=True)
        if not args.watch or result["status"] == "complete":
            break
        delay = result.get("retry_after_seconds", 60)
        print(f"Paused; rechecking in {delay} seconds. Ctrl+C is safe; rerun to resume.", flush=True)
        time.sleep(delay)
    if result["status"] != "complete":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
