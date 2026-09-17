import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from weather_ingest.study import (
    BudgetClient,
    QuotaPause,
    download,
    frame_from_payload,
    load_locations,
    study_plan,
)
from weather_ingest.variables import ARCHIVE_VARIABLES


def small_plan():
    locations = pd.DataFrame(
        [
            {
                "location_id": "hill",
                "query": "Hill",
                "country_code": "LK",
                "region": "South Asia",
                "latitude": 7.0,
                "longitude": 80.0,
            }
        ]
    )
    return study_plan(locations, date(2020, 1, 1), date(2020, 1, 1))


def payload():
    return {
        "hourly": {
            "time": pd.date_range("2020-01-01", periods=24, freq="h").astype(str).tolist(),
            **{v: [None] * 24 for v in ARCHIVE_VARIABLES},
        },
        "hourly_units": {v: "test-unit" for v in ARCHIVE_VARIABLES},
    }


class FakeClient:
    def __init__(self):
        self.calls = 0

    def get(self, url, params, cost=1):
        self.calls += 1
        return {"elevation": [2000.0]} if url.endswith("/elevation") else payload()


def test_regional_plan():
    locations = load_locations(Path("config/locations_regional_100.csv"))
    plan = study_plan(locations, date(2020, 1, 1), date(2025, 12, 31))
    assert len(locations) == 100
    assert (locations.country_code == "LK").sum() == 30
    assert plan["expected_rows"] == 5_260_800
    assert len(plan["chunks"]) == 600
    assert len(set(plan["variables"])) == 47


def test_resume_and_configuration_integrity(tmp_path):
    client, plan = FakeClient(), small_plan()
    assert download(plan, tmp_path, client)["status"] == "complete"
    assert download(plan, tmp_path, client)["completed_rows"] == 24
    assert client.calls == 2  # no new API calls on resume
    file = next(tmp_path.rglob("weather.parquet"))
    frame = pd.read_parquet(file)
    assert set(ARCHIVE_VARIABLES).issubset(frame.columns)
    assert frame.temperature_2m.dtype == "float64"  # all-null columns are typed
    assert json.loads(file.with_name("_source.json").read_text())["null_counts"]["rain"] == 24
    changed = dict(plan, model="era5")
    with pytest.raises(ValueError, match="configuration changed"):
        download(changed, tmp_path, client)
    file.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Checkpoint mismatch"):
        download(plan, tmp_path, client)


def test_rejects_hour_gaps_duplicates_and_missing_features():
    chunk = small_plan()["chunks"][0]
    broken = payload()
    broken["hourly"]["time"][1] = broken["hourly"]["time"][0]
    with pytest.raises(RuntimeError, match="every requested UTC hour"):
        frame_from_payload(broken, chunk)
    broken = payload()
    del broken["hourly"]["rain"]
    with pytest.raises(RuntimeError, match="Missing hourly fields"):
        frame_from_payload(broken, chunk)


def test_pause_is_resumable(tmp_path):
    class PausedClient(FakeClient):
        def get(self, url, params, cost=1):
            if not url.endswith("/elevation"):
                raise QuotaPause("daily budget")
            return super().get(url, params, cost)

    assert download(small_plan(), tmp_path, PausedClient())["status"] == "paused"
    assert download(small_plan(), tmp_path, FakeClient())["status"] == "complete"


def test_quota_counts_failures_and_prevents_network(tmp_path, monkeypatch):
    client = BudgetClient(tmp_path / "budget.json")
    calls = []

    def failed(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("connection failed")

    monkeypatch.setattr(client.session, "get", failed)
    with pytest.raises(RuntimeError, match="connection failed"):
        client.get("https://example.com", {}, cost=400)
    with pytest.raises(QuotaPause):
        client.get("https://example.com", {}, cost=200)
    assert len(calls) == 1


def test_incomplete_study_cannot_process_or_publish(tmp_path):
    from weather_analysis.pipeline import process
    from weather_analysis.storage import publish

    (tmp_path / "study-plan.json").write_text("{}")
    (tmp_path / "ingestion-status.json").write_text('{"status": "paused"}')
    with pytest.raises(ValueError, match="incomplete"):
        process(tmp_path / "raw", tmp_path / "processed")
    with pytest.raises(ValueError, match="incomplete"):
        publish(tmp_path, tmp_path / "platform", "partial-study")


def two_locations():
    one = pd.DataFrame(small_plan()["locations"])
    return pd.concat(
        [one, one.assign(location_id="coast", query="Coast", latitude=8.0)], ignore_index=True
    )


class WindowClient:
    def __init__(self, pause_after=None):
        self.weather_calls = []
        self.pause_after = pause_after

    def get(self, url, params, cost=1):
        if url.endswith("/elevation"):
            return {"elevation": [2000.0, 10.0]}
        if self.pause_after is not None and len(self.weather_calls) >= self.pause_after:
            raise QuotaPause("test quota")
        self.weather_calls.append(params)
        times = pd.date_range(
            params["start_date"],
            pd.Timestamp(params["end_date"]) + pd.Timedelta(hours=23),
            freq="h",
        )
        return {
            "hourly": {
                "time": times.astype(str).tolist(),
                **{v: [1.0] * len(times) for v in ARCHIVE_VARIABLES},
            }
        }


def test_latest_first_sweeps_all_locations_and_year_boundary():
    from weather_ingest.study import latest_first_plan

    plan = latest_first_plan(two_locations(), date(2023, 12, 28), date(2024, 1, 8))
    assert [(c["location_id"], c["start"], c["end"]) for c in plan["chunks"][:4]] == [
        ("hill", "2024-01-02", "2024-01-08"),
        ("coast", "2024-01-02", "2024-01-08"),
        ("hill", "2024-01-01", "2024-01-01"),
        ("coast", "2024-01-01", "2024-01-01"),
    ]
    assert sum(c["hours"] for c in plan["chunks"]) == 12 * 24 * 2
    for loc in ["hill", "coast"]:
        days = [
            day
            for c in plan["chunks"]
            if c["location_id"] == loc
            for day in pd.date_range(c["start"], c["end"])
        ]
        assert len(days) == len(set(days)) == 12


def test_latest_first_pause_resumes_remaining_locations_before_older_window(tmp_path):
    from weather_ingest.study import latest_first_plan

    plan = latest_first_plan(two_locations(), date(2024, 1, 1), date(2024, 1, 14))
    client = WindowClient(pause_after=1)
    result = download(plan, tmp_path, client, max_requests=100)
    assert result["active_window"]["completed_locations"] == 1
    assert result["completed_rows"] == 7 * 24
    resume = WindowClient()
    result = download(plan, tmp_path, resume, max_requests=1)
    assert resume.weather_calls[0]["latitude"] == 8.0
    assert resume.weather_calls[0]["start_date"] == "2024-01-08"
    assert result["active_window"]["end"] == "2024-01-07"
    assert result["completed_chunks"] == 2
    assert download(plan, tmp_path, resume, max_requests=100)["status"] == "complete"


def test_migration_preserves_downloads_and_resume_plan(tmp_path):
    from weather_ingest.study import build_plan, chunk_paths, digest

    old = study_plan(two_locations(), date(2020, 1, 1), date(2020, 1, 2))
    download(old, tmp_path, WindowClient(), max_requests=1)
    output = chunk_paths(tmp_path, old["chunks"][0])[0]
    before = digest(output)
    plan = build_plan(two_locations(), tmp_path, end=date(2020, 1, 9))
    client = WindowClient()
    result = download(plan, tmp_path, client, max_requests=100)
    assert result["status"] == "complete"
    assert digest(output) == before
    assert json.loads((tmp_path / "study-plan-before-latest-first.json").read_text()) == old
    assert build_plan(two_locations(), tmp_path) == plan
    assert [(c["start_date"], c["end_date"]) for c in client.weather_calls] == [
        ("2020-01-03", "2020-01-09"),
        ("2020-01-03", "2020-01-09"),
        ("2020-01-01", "2020-01-02"),
    ]
    import pyarrow.dataset as ds

    frame = (
        ds.dataset(tmp_path / "raw/weather", format="parquet", partitioning="hive")
        .to_table()
        .to_pandas()
    )
    assert len(frame) == 9 * 24 * 2
    assert not frame.duplicated(["location_id", "timestamp"]).any()


def test_latest_plan_leap_day_and_invalid_size():
    from weather_ingest.study import latest_first_plan

    plan = latest_first_plan(two_locations(), date(2024, 2, 28), date(2024, 3, 1))
    assert plan["expected_rows"] == 3 * 24 * 2
    with pytest.raises(ValueError, match="1–31"):
        latest_first_plan(two_locations(), date(2024, 2, 28), date(2024, 3, 1), window_days=0)


def test_busy_importer_leaves_status_and_data_untouched(tmp_path):
    import fcntl

    from weather_ingest.study import IngestionBusy

    status = tmp_path / "ingestion-status.json"
    status.write_text('{"status": "downloading"}')
    with (tmp_path / ".ingest.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(IngestionBusy, match="Another importer is running"):
            download(small_plan(), tmp_path, None)
    assert status.read_text() == '{"status": "downloading"}'
    assert not (tmp_path / "study-plan.json").exists()
    assert not (tmp_path / "raw").exists()
