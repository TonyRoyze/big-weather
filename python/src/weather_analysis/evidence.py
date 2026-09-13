"""Export descriptive evidence and provenance; interpretation remains a team task."""

import json
from pathlib import Path

from .storage import DatasetStore, atomic_json


def markdown_table(frame) -> str:
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        cells = [f"{v:.4f}" if isinstance(v, float) else str(v) for v in row]
        lines.append("| " + " | ".join(v.replace("|", "\\|") for v in cells) + " |")
    return "\n".join(lines)


def export_evidence(store: DatasetStore, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    daily = store.read("daily_metrics")
    yearly = store.read("yearly_metrics")
    lapse = store.read("lapse_rates").sort_values("season")
    ranking = (
        daily.groupby(["location_id", "name", "elevation_band"], observed=True)
        .agg(
            mean_daily_temperature_c=("daily_avg_temperature_c", "mean"),
            mean_daily_precipitation_mm=("daily_precipitation_mm", "mean"),
            mean_daily_wind_ms=("daily_avg_wind_speed_ms", "mean"),
            observed_days=("date", "count"),
        )
        .reset_index()
    )
    # Equal weight per location avoids letting locations with more records dominate a band.
    bands = (
        ranking.groupby("elevation_band", observed=True)
        .agg(
            mean_location_temperature_c=("mean_daily_temperature_c", "mean"),
            mean_location_daily_precipitation_mm=("mean_daily_precipitation_mm", "mean"),
            locations=("location_id", "count"),
        )
        .reset_index()
    )
    baseline = yearly.groupby("location_id").annual_avg_temperature_c.transform("mean")
    anomalies = yearly.assign(anomaly_vs_study_mean_c=yearly.annual_avg_temperature_c - baseline)
    extremes = daily.nlargest(20, "daily_precipitation_mm")[
        ["location_id", "name", "date", "daily_precipitation_mm"]
    ]
    tables = {
        "location_comparison": ranking,
        "elevation_comparison": bands,
        "annual_anomalies": anomalies,
        "wettest_location_days": extremes,
        "seasonal_lapse_rates": lapse,
    }
    for name, frame in tables.items():
        frame.to_parquet(output / f"{name}.parquet", index=False)
    metadata = {
        "dataset": store.manifest,
        "method_version": "evidence-v1",
        "methods": {
            "location_comparison": "Equal-weight daily means; precipitation is mean daily total in mm/day.",
            "elevation_comparison": "Equal-weight location means, not pooled precipitation totals.",
            "annual_anomalies": "Annual mean minus this location's mean of observed annual means; not a climate normal.",
            "wettest_location_days": "Top 20 observed daily precipitation totals; not hourly extremes.",
            "seasonal_lapse_rates": "Existing pooled daily OLS: temperature ~ elevation, by local season. Not causal.",
        },
    }
    atomic_json(output / "metadata.json", metadata)
    sections = [
        "# Reproducible evidence — descriptive, pending team interpretation",
        f"Dataset: `{store.version}`. Fingerprint: `{store.manifest['fingerprint']}`.",
        f"Coverage: {json.dumps(store.manifest['coverage'])}. {store.manifest['attribution']}",
        "Generated with `weather-analysis evidence`. Tables are newly exported from the published "
        "Scala outputs, not custom-job cache results. See metadata.json for full provenance.",
    ]
    for name in ["elevation_comparison", "seasonal_lapse_rates", "wettest_location_days"]:
        sections.extend(
            [
                f"## {name.replace('_', ' ').title()}",
                metadata["methods"][name],
                markdown_table(tables[name]),
            ]
        )
    sections.extend(
        [
            "## Interpretation limits",
            "Locations are selected, not a random global sample. Latitude, region and season confound "
            "elevation associations. Repeated days per location are not independent regression samples. "
            "The short study window does not establish a long-term climate trend. Spark removes rows "
            "missing any required weather variable or failing range checks and drops duplicate hourly keys; "
            "daily metrics therefore describe retained hours. Review pipeline counts and coverage before "
            "comparing totals. The lapse-rate output is a signed slope (°C/km), not a positive cooling magnitude.",
            "## Team findings to complete",
            "For each claim, record owner, question, evidence file/job ID, filters, denominator, "
            "effect size, visualization and limitations. Do not treat this generated table as a causal finding.",
        ]
    )
    report = output / "findings.md"
    report.write_text("\n\n".join(sections) + "\n")
    return report
