"""Recurring monthly seasonality in six complete 2020–2025 coastal histories."""

import calendar
import hashlib
import itertools
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from analyze_elevation_relationships import FEATURES
from scipy.stats import friedmanchisquare, rankdata
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/replication"


def main():
    sources = pd.read_csv(OUT / "tables/source_files.csv")
    historical_sites = pd.read_csv(OUT / "tables/original_six_annual.csv").location_id.unique()
    sources = sources[sources.year.between(2020, 2025) & sources.location_id.isin(historical_sites)]
    frames = []
    for row in sources.itertuples():
        path = Path(row.path)
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row.sha256
        frame = pq.ParquetFile(path).read(columns=["timestamp", *FEATURES]).to_pandas()
        frame["location_id"] = row.location_id
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    data["timestamp"] = pd.to_datetime(data.timestamp, utc=True)
    assert not data.duplicated(["location_id", "timestamp"]).any()
    assert data[list(FEATURES)].notna().all().all()
    data["year"] = data.timestamp.dt.year
    data["month"] = data.timestamp.dt.month
    grouped = data.groupby(["location_id", "year", "month"])
    monthly = grouped[list(FEATURES)].mean()
    monthly["precipitation"] *= 24
    monthly["hours"] = grouped.size()
    monthly = monthly.reset_index()
    assert len(monthly) == 432 and monthly.location_id.nunique() == 6
    assert all(
        r.hours == calendar.monthrange(r.year, r.month)[1] * 24 for r in monthly.itertuples()
    )
    monthly.to_csv(OUT / "tables/historical_monthly_sites.csv", index=False)
    # Fix first year's phase: a common rotation leaves the statistic unchanged.
    shifts = np.array(list(itertools.product(range(12), repeat=5)))
    tests = []
    for location, group in monthly.groupby("location_id"):
        for field in FEATURES:
            matrix = group.pivot(index="year", columns="month", values=field).to_numpy()
            assert matrix.shape == (6, 12)
            ranks = rankdata(matrix, axis=1)
            observed = np.square(ranks.sum(axis=0) - 39).sum()
            total = np.broadcast_to(ranks[0], (len(shifts), 12)).copy()
            for year in range(1, 6):
                total += ranks[year][(np.arange(12)[None, :] + shifts[:, year - 1, None]) % 12]
            null = np.square(total - 39).sum(axis=1)
            p = np.mean(null >= observed - 1e-9)
            q = float(friedmanchisquare(*matrix.T).statistic)
            mean = matrix.mean(axis=0)
            tests.append(
                {
                    "location_id": location,
                    "variable": field,
                    "friedman_Q": q,
                    "kendall_W": q / 66,
                    "rotation_p": p,
                    "peak_month": int(mean.argmax() + 1),
                    "trough_month": int(mean.argmin() + 1),
                    "peak_minus_trough": float(mean.max() - mean.min()),
                }
            )
    tests = pd.DataFrame(tests)
    tests["p_holm"] = multipletests(tests.rotation_p, method="holm")[1]
    tests.to_csv(OUT / "tables/historical_seasonality_tests.csv", index=False)
    cycle = monthly.groupby(["location_id", "month"])[list(FEATURES)].mean().reset_index()
    cycle.to_csv(OUT / "tables/historical_monthly_climatology.csv", index=False)
    plt.rcParams.update({"font.size": 10, "savefig.dpi": 180})
    fig, axes = plt.subplots(4, 2, figsize=(11, 12), layout="constrained")
    for ax, (field, (label, unit)) in zip(axes.flat, FEATURES.items()):
        for location, group in cycle.groupby("location_id"):
            ax.plot(group.month, group[field], label=location.replace("lk_", "").title(), lw=1.4)
        ax.set(
            title=label,
            ylabel=unit,
            xticks=[1, 3, 5, 7, 9, 11],
            xticklabels=["Jan", "Mar", "May", "Jul", "Sep", "Nov"],
        )
        ax.grid(alpha=0.15)
        ax.spines[["top", "right"]].set_visible(False)
    axes.flat[-1].axis("off")
    handles, labels = axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(handles, labels, loc="upper left", frameon=False)
    axes.flat[-1].text(
        0,
        0.2,
        "2020–2025: six complete years per site\nMonthly means averaged equally across years\nRainfall: mean daily total (mm/day)",
    )
    fig.savefig(OUT / "figures/historical_seasonal_cycles.png")
    plt.close(fig)
    result = {
        "years": [2020, 2025],
        "sites": 6,
        "monthly_records": len(monthly),
        "hourly_records": len(data),
        "tests": len(tests),
        "rotations_per_test": len(shifts),
        "method": "Exact within-year circular phase alignment test of monthly ranks; first year fixed; Holm across 42 tests",
        "assumptions": "Independent year blocks; uniformly exchangeable cyclic phase under null; wraparound preserves cyclic, not all chronological, dependence",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_hashes_verified": True,
    }
    (OUT / "historical_seasonality.json").write_text(json.dumps(result, indent=2) + "\n")
    print(tests.to_string(index=False))
    print(
        tests.assign(significant=tests.p_holm < 0.05)
        .groupby("variable")
        .agg(
            significant_sites=("significant", "sum"),
            min_W=("kendall_W", "min"),
            max_W=("kendall_W", "max"),
            max_p=("p_holm", "max"),
        )
        .to_string()
    )


if __name__ == "__main__":
    main()
