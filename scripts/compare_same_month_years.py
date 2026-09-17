"""Compare the same calendar month across 2020–2025 within each historical site."""

import calendar
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from analyze_elevation_relationships import FEATURES
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/replication"
B = 4999


def f_stat(x):
    means = x.mean(axis=-1)
    between = x.shape[-1] * np.square(means - means.mean(axis=-1, keepdims=True)).sum(axis=-1)
    within = np.square(x - means[..., None]).sum(axis=(-1, -2))
    return np.divide(
        between / (x.shape[-2] - 1),
        within / (x.shape[-2] * (x.shape[-1] - 1)),
        out=np.zeros_like(between),
        where=within > 0,
    )


def test(x, block=7):
    rng = np.random.default_rng(20260916)

    def shuffled(values):
        result = np.empty((B, *values.shape))
        for start in range(0, values.shape[1], block):
            order = np.argsort(rng.random((B, values.shape[0])), axis=1)
            result[:, :, start : start + block] = values[order, start : start + block]
        return result

    level = float(f_stat(x))
    level_p = (1 + np.count_nonzero(f_stat(shuffled(x)) >= level - 1e-12)) / (B + 1)
    centered = x - np.median(x, axis=1, keepdims=True)
    spread = float(f_stat(np.abs(centered)))
    perm = shuffled(centered)
    perm = np.abs(perm - np.median(perm, axis=2, keepdims=True))
    spread_p = (1 + np.count_nonzero(f_stat(perm) >= spread - 1e-12)) / (B + 1)
    return level, level_p, spread, spread_p


def main():
    sources = pd.read_csv(OUT / "tables/source_files.csv")
    sites = pd.read_csv(OUT / "tables/original_six_annual.csv").location_id.unique()
    sources = sources[sources.year.between(2020, 2025) & sources.location_id.isin(sites)]
    frames = []
    for r in sources.itertuples():
        p = Path(r.path)
        assert hashlib.sha256(p.read_bytes()).hexdigest() == r.sha256
        d = pq.ParquetFile(p).read(columns=["timestamp", *FEATURES]).to_pandas()
        d["location_id"] = r.location_id
        frames.append(d)
    data = pd.concat(frames, ignore_index=True)
    data.timestamp = pd.to_datetime(data.timestamp, utc=True)
    assert not data.duplicated(["location_id", "timestamp"]).any()
    assert data[list(FEATURES)].notna().all().all()
    data["date"] = data.timestamp.dt.floor("D")
    group = data.groupby(["location_id", "date"])
    assert group.size().eq(24).all()
    daily = group[list(FEATURES)].mean().reset_index()
    daily["precipitation"] *= 24
    daily["year"] = daily.date.dt.year
    daily["month"] = daily.date.dt.month
    daily["day"] = daily.date.dt.day
    daily = daily[~((daily.month == 2) & (daily.day == 29))]
    daily.to_csv(OUT / "tables/same_month_daily.csv", index=False)
    records, summaries = [], []
    for (site, month), sub in daily.groupby(["location_id", "month"]):
        for field in FEATURES:
            x = sub.pivot(index="year", columns="day", values=field).to_numpy()
            assert x.shape == (6, calendar.monthrange(2021, month)[1]) and np.isfinite(x).all()
            f, p, bf, bp = test(x)
            records.append(
                {
                    "location_id": site,
                    "month": month,
                    "variable": field,
                    "level_F": f,
                    "level_p": p,
                    "spread_F": bf,
                    "spread_p": bp,
                }
            )
            for year, values in zip(range(2020, 2026), x):
                summaries.append(
                    {
                        "location_id": site,
                        "month": month,
                        "variable": field,
                        "year": year,
                        "mean": values.mean(),
                        "median": np.median(values),
                        "sd": values.std(ddof=1),
                        "q25": np.quantile(values, 0.25),
                        "q75": np.quantile(values, 0.75),
                    }
                )
        print(site, month, flush=True)
    results = pd.DataFrame(records)
    for ix in results.groupby(["location_id", "variable"]).groups.values():
        adjusted = multipletests(
            results.loc[ix, ["level_p", "spread_p"]].to_numpy().ravel(), method="holm"
        )[1].reshape(-1, 2)
        results.loc[ix, "level_p_holm"] = adjusted[:, 0]
        results.loc[ix, "spread_p_holm"] = adjusted[:, 1]
    results.to_csv(OUT / "tables/same_month_year_tests.csv", index=False)
    pd.DataFrame(summaries).to_csv(OUT / "tables/same_month_year_summaries.csv", index=False)
    figdir = OUT / "figures/same_month"
    figdir.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "savefig.dpi": 160})
    for (site, field), tests in results.groupby(["location_id", "variable"]):
        selected = tests[(tests.level_p_holm < 0.05) | (tests.spread_p_holm < 0.05)]
        if site == "lk_matara" and field == "temperature_2m":
            selected = tests  # Show January and all other months, including null results.
        if selected.empty:
            continue
        fig, axes = plt.subplots(
            int(np.ceil(len(selected) / 3)),
            3,
            figsize=(12, 3 * int(np.ceil(len(selected) / 3))),
            squeeze=False,
            layout="constrained",
        )
        for ax, r in zip(axes.flat, selected.itertuples()):
            sub = daily[(daily.location_id == site) & (daily.month == r.month)]
            groups = [sub[sub.year == y][field].to_numpy() for y in range(2020, 2026)]
            ax.boxplot(groups, tick_labels=[str(y)[2:] for y in range(2020, 2026)], showmeans=True)
            rng = np.random.default_rng(42)
            for i, v in enumerate(groups, 1):
                ax.scatter(
                    i + rng.uniform(-0.16, 0.16, len(v)), v, s=7, alpha=0.35, color="#167b79"
                )
            ax.set(
                title=f"{calendar.month_name[r.month]} · level p={r.level_p_holm:.3f}\nspread p={r.spread_p_holm:.3f}",
                ylabel=FEATURES[field][1],
                xlabel="Year (20xx)",
            )
            ax.grid(axis="y", alpha=0.15)
        for ax in list(axes.flat)[len(selected) :]:
            ax.axis("off")
        fig.suptitle(
            f"{site.replace('lk_', '').title()} · {FEATURES[field][0]} · same month across years",
            fontsize=14,
        )
        fig.savefig(figdir / f"{site}_{field}.png")
        plt.close(fig)
    matara = results[(results.location_id == "lk_matara") & (results.variable == "temperature_2m")]
    (OUT / "same_month_years.json").write_text(
        json.dumps(
            {
                "years": [2020, 2025],
                "sites": 6,
                "comparisons": len(results),
                "permutations": B,
                "block_days": 7,
                "unit": "daily mean; daily total for precipitation",
                "leap_day": "excluded for matched calendar-day positions",
                "multiplicity": "Holm across 12 months x 2 tests separately for each location-feature; not global across all features/sites",
                "method": "ANOVA level statistic; Brown-Forsythe spread statistic, median-centered residual permutations; year labels shuffled within matched 7-day calendar blocks",
                "assumptions": "Exchangeability of year blocks under null; approximate temporal dependence treatment; dependencies across block boundaries not retained",
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )
    print(matara.to_string(index=False))


if __name__ == "__main__":
    main()
