from __future__ import annotations

import argparse
import os
from datetime import date
from pathlib import Path

from .client import OpenMeteoClient
from .pipeline import ingest, load_seeds, resolve_locations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest Open-Meteo data as partitioned Parquet")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--locations", type=Path, default=Path("config/locations.csv"))
    ingest_parser.add_argument("--data-root", type=Path, default=None)
    ingest_parser.add_argument("--start-date", type=date.fromisoformat, default=date(2019, 1, 1))
    ingest_parser.add_argument("--end-date", type=date.fromisoformat, default=date(2024, 12, 31))
    ingest_parser.add_argument("--limit", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data_root = args.data_root or Path(os.getenv("WEATHER_DATA_ROOT", "data"))
    cache_path = Path(os.getenv("OPEN_METEO_CACHE", "data/cache/open_meteo"))
    delay = float(os.getenv("OPEN_METEO_DELAY_SECONDS", "0.12"))
    client = OpenMeteoClient(cache_path, delay)
    seeds = load_seeds(args.locations)
    if args.limit is not None:
        seeds = seeds[: args.limit]
    locations = resolve_locations(seeds, client)
    files, rows = ingest(locations, client, data_root, args.start_date, args.end_date)
    print(f"Ingestion complete: {len(locations)} locations, {files} files, {rows:,} rows")


if __name__ == "__main__":
    main()

