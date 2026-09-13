"""Compare local[1] and local[4] on identical raw inputs, preserving each run.

Run after installation from the repository root. No ingestion or publication occurs.
Times include Spark startup and validation but exclude sbt startup/compilation;
wall_seconds includes those costs. Alternate order across repetitions.
"""

import argparse
import json
import os
from pathlib import Path
import statistics
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--input", type=Path, default=Path("data/raw"))
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
if args.repeats < 1:
    parser.error("repeats must be positive")
args.output.mkdir(parents=True, exist_ok=False)
results = []
for trial in range(1, args.repeats + 1):
    for threads in [1, 4] if trial % 2 else [4, 1]:
        target = args.output / f"local-{threads}-trial-{trial}"
        # sbt runMain handles quoted paths; subprocess bypasses shell interpretation.
        command = (
            "runMain lk.ac.ds4004.weather.WeatherJob "
            f"--input {json.dumps(str(args.input.resolve()))} "
            f"--output {json.dumps(str(target.resolve()))}"
        )
        started = time.perf_counter()
        with (args.output / f"local-{threads}-trial-{trial}.log").open("w") as log:
            subprocess.run(
                ["sbt", command],
                check=True,
                stdout=log,
                stderr=subprocess.STDOUT,
                env={
                    **os.environ,
                    "SPARK_MASTER": f"local[{threads}]",
                    "SPARK_LOCAL_IP": "127.0.0.1",
                },
            )
        metrics = json.loads((target / "pipeline_metrics.json").read_text())
        metrics.update(trial=trial, wall_seconds=time.perf_counter() - started)
        results.append(metrics)
        print(f"local[{threads}], trial {trial}: {metrics['duration_seconds']:.2f}s", flush=True)
        (args.output / "runs.json").write_text(json.dumps(results, indent=2) + "\n")
keys = [
    "input_rows",
    "output_rows",
    "daily_rows",
    "rejected_or_duplicate_rows",
    "unmatched_location_rows",
]
if any(len({run[k] for run in results}) != 1 for k in keys):
    raise SystemExit("Row-count mismatch: inspect outputs before interpreting performance")
medians = {
    str(n): statistics.median(
        r["duration_seconds"] for r in results if r["spark_master"] == f"local[{n}]"
    )
    for n in [1, 4]
}
summary = {
    "repeats": args.repeats,
    "median_seconds": medians,
    "local_1_over_local_4": medians["1"] / medians["4"],
    "row_counts_match": True,
    "limitations": "Local thread parallelism only; OS/JVM cache and run order affect timing. "
    "Use at least three repetitions on an otherwise idle machine. "
    "Matching counts alone do not prove all numerical outputs identical.",
}
(args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
