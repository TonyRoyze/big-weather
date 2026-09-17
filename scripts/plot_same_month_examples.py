"""Selected distribution views for the same-month report, sourced from saved daily data."""

import os

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from compare_same_month_years import OUT


def main():
    daily = pd.read_csv(OUT / "tables/same_month_daily.csv")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), layout="constrained")
    examples = [
        (
            "lk_matara",
            1,
            "temperature_2m",
            "Matara · January temperature",
            "Daily mean temperature (°C)",
        ),
        (
            "lk_colombo",
            11,
            "relative_humidity_2m",
            "Colombo · November humidity",
            "Daily mean relative humidity (%)",
        ),
    ]
    for ax, (site, month, field, title, unit) in zip(axes, examples):
        sub = daily[(daily.location_id == site) & (daily.month == month)]
        values = [sub[sub.year == year][field].to_numpy() for year in range(2020, 2026)]
        ax.boxplot(values, tick_labels=range(2020, 2026), showmeans=True)
        rng = np.random.default_rng(42)
        for i, v in enumerate(values, 1):
            ax.scatter(i + rng.uniform(-0.15, 0.15, len(v)), v, s=14, alpha=0.45, color="#167b79")
        ax.set(title=title, ylabel=unit, xlabel="Year")
        ax.grid(axis="y", alpha=0.15)
    fig.savefig(OUT / "figures/same_month_examples.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
