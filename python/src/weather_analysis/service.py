"""Synchronous local jobs with SQLite history, bounded Spark execution and TTL cache."""

from __future__ import annotations

from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import uuid

import pandas as pd

from .spec import TRANSFORM_VERSION, cache_key, validate_spec
from .storage import DatasetStore, atomic_json, identifier


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AnalysisService:
    def __init__(
        self,
        root: Path | str = "data/platform",
        version: str | None = None,
        ttl_seconds: int = 86400,
        timeout_seconds: int = 600,
    ):
        self.store = DatasetStore(root, version)
        self.root = Path(root).resolve()
        self.jobs = self.root / "jobs"
        self.jobs.mkdir(exist_ok=True)
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs "
                "(id TEXT PRIMARY KEY, cache_key TEXT, completed_at REAL, metadata TEXT)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS cache_lookup ON jobs(cache_key, completed_at)")

    def _db(self):
        return sqlite3.connect(self.root / "jobs.sqlite", timeout=30)

    def _save(self, meta: dict, key: str, completed: float | None = None):
        atomic_json(self.jobs / meta["job_id"] / "metadata.json", meta)
        with self._db() as db:
            db.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?)",
                (meta["job_id"], key, completed, json.dumps(meta)),
            )

    def submit_job(self, spec: dict) -> str:
        """Validate then run synchronously. Returns an ID, including for failed jobs.

        A local file lock serializes Spark jobs and cache lookup to prevent duplicate
        work across browser sessions. Graceful failures and worker timeouts are recorded.
        """
        spec = validate_spec(spec)
        key = cache_key(spec, self.store.version, self.store.manifest["fingerprint"])
        job_id = uuid.uuid4().hex
        directory = self.jobs / job_id
        directory.mkdir()
        meta = {
            "job_id": job_id,
            "spec": spec,
            "dataset_version": self.store.version,
            "fingerprint": self.store.manifest["fingerprint"],
            "transform_version": TRANSFORM_VERSION,
            "status": "queued",
            "created_at": now(),
            "cache_hit": False,
        }
        self._save(meta, key)
        with (self.root / "worker.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            started = time.perf_counter()
            meta.update(status="running", started_at=now())
            self._save(meta, key)
            try:
                with self._db() as db:
                    hits = db.execute(
                        "SELECT metadata FROM jobs WHERE cache_key=? AND completed_at>? "
                        "ORDER BY completed_at DESC",
                        (key, time.time() - self.ttl_seconds),
                    ).fetchall()
                hit = next(
                    (
                        json.loads(row[0])
                        for row in hits
                        if (
                            self.jobs / json.loads(row[0])["result_job_id"] / "result.parquet"
                        ).exists()
                    ),
                    None,
                )
                if hit:
                    meta.update(
                        cache_hit=True,
                        result_job_id=hit["result_job_id"],
                        input_rows=hit["input_rows"],
                        output_rows=hit["output_rows"],
                    )
                else:
                    request = {
                        "spec": spec,
                        "input": str(self.store.table_path("enriched_weather").resolve()),
                        "output": str(directory / "result.parquet"),
                    }
                    atomic_json(directory / "request.json", request)
                    with (directory / "worker.log").open("w") as log:
                        process = subprocess.Popen(
                            [
                                sys.executable,
                                "-m",
                                "weather_analysis.worker",
                                str(directory / "request.json"),
                            ],
                            stdout=log,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                            env={**os.environ, "SPARK_LOCAL_IP": "127.0.0.1"},
                        )
                        try:
                            code = process.wait(timeout=self.timeout_seconds)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait()
                            raise RuntimeError(
                                f"Spark exceeded {self.timeout_seconds}s; see worker.log"
                            ) from None
                    if code:
                        raise RuntimeError(
                            f"Spark exited with code {code}; see {directory / 'worker.log'}"
                        )
                    meta.update(
                        json.loads((directory / "worker_metrics.json").read_text()),
                        result_job_id=job_id,
                    )
                meta.update(
                    status="completed",
                    completed_at=now(),
                    duration_seconds=time.perf_counter() - started,
                )
                # Cache hits do not extend the original computation's TTL.
                self._save(meta, key, None if hit else time.time())
            except Exception as exc:
                meta.update(
                    status="failed",
                    error=str(exc),
                    completed_at=now(),
                    duration_seconds=time.perf_counter() - started,
                )
                self._save(meta, key)
        return job_id

    def get_job_status(self, job_id: str) -> dict:
        identifier(job_id)
        with self._db() as db:
            row = db.execute("SELECT metadata FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown job: {job_id}")
        return json.loads(row[0])

    def load_job_result(self, job_id: str) -> pd.DataFrame:
        meta = self.get_job_status(job_id)
        if meta["status"] != "completed":
            raise ValueError(f"Job is {meta['status']}: {meta.get('error', '')}")
        result = pd.read_parquet(self.jobs / identifier(meta["result_job_id"]) / "result.parquet")
        return result.sort_values(meta["spec"]["group_by"]).reset_index(drop=True)

    def list_jobs(self) -> list[dict]:
        with self._db() as db:
            rows = db.execute("SELECT metadata FROM jobs ORDER BY rowid DESC").fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_overview(self) -> dict:
        return self.store.get_overview()
