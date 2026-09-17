"""Freeze committed January–August 2026 data into complete site-month summaries."""

import calendar
import hashlib
import json
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds
from analyze_elevation_relationships import FEATURES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/replication"
DATA = ROOT / "data/regional-2020-2025"


def main():
    records = []
    for meta in sorted((DATA / "raw/weather").glob("location_id=*/year=2026/_source*.json")):
        path = meta.with_name(meta.name.replace("_source", "weather").replace(".json", ".parquet"))
        if not path.exists():
            continue
        records.append(
            {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "metadata_path": str(meta),
                "metadata_sha256": hashlib.sha256(meta.read_bytes()).hexdigest(),
            }
        )
    raw = (
        ds.dataset(
            [r["path"] for r in records],
            format="parquet",
            partitioning="hive",
            partition_base_dir=str(DATA / "raw/weather"),
        )
        .to_table(columns=["location_id", "timestamp", *FEATURES])
        .to_pandas()
    )
    raw.timestamp = pd.to_datetime(raw.timestamp, utc=True)
    raw = raw[raw.timestamp.between("2026-01-01", "2026-08-31 23:00:00+00:00")].copy()
    assert not raw.duplicated(["location_id", "timestamp"]).any()
    assert raw[list(FEATURES)].notna().all().all()
    assert raw.timestamp.eq(raw.timestamp.dt.floor("h")).all()
    raw["month"] = raw.timestamp.dt.month
    grouped = raw.groupby(["location_id", "month"])
    monthly = grouped[list(FEATURES)].mean()
    monthly["precipitation"] *= 24
    monthly["hours"] = grouped.size()
    monthly = monthly.reset_index()
    assert len(monthly) == 800 and monthly.location_id.nunique() == 100
    assert all(r.hours == calendar.monthrange(2026, r.month)[1] * 24 for r in monthly.itertuples())
    meta_path = OUT / "tables/elevation_monthly_sites.csv"
    meta = pd.read_csv(meta_path).drop_duplicates("location_id")[
        ["location_id", "country", "latitude", "longitude", "elevation_m"]
    ]
    monthly = monthly.merge(meta, on="location_id", validate="many_to_one")
    assert monthly.country.notna().all()
    monthly["elevation_km"] = monthly.elevation_m / 1000
    for r in records:
        assert hashlib.sha256(Path(r["path"]).read_bytes()).hexdigest() == r["sha256"]
        assert (
            hashlib.sha256(Path(r["metadata_path"]).read_bytes()).hexdigest()
            == r["metadata_sha256"]
        )
    pd.DataFrame(records).to_csv(OUT / "tables/elevation_2026_source_files.csv", index=False)
    monthly.to_csv(OUT / "tables/elevation_2026_jan_aug_sites.csv", index=False)
    (OUT / "elevation_2026_snapshot.json").write_text(
        json.dumps(
            {
                "start": "2026-01-01",
                "end": "2026-08-31",
                "hourly_rows": len(raw),
                "site_months": len(monthly),
                "sites": 100,
                "source_files": len(records),
                "source_fingerprint": hashlib.sha256(
                    json.dumps(records, sort_keys=True).encode()
                ).hexdigest(),
                "metadata_sha256": hashlib.sha256(meta_path.read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )
    print(len(raw), "hourly rows;", len(monthly), "complete site-months")


if __name__ == "__main__":
    main()
