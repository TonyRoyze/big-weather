"""Rank-based historical comparisons and 2026 monthly elevation-band comparisons."""

import argparse
import calendar
import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from analyze_elevation_relationships import FEATURES
from scipy.stats import fligner, kruskal, norm, rankdata, spearmanr
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/replication"
B = 9999


def score_stat(scores):
    return (
        scores.shape[1] * np.square(scores.mean(axis=1) - scores.mean()).sum() / scores.var(ddof=1)
    )


def block_score_test(scores, block=7):
    observed = score_stat(scores)
    rng = np.random.default_rng(20260917)
    totals = np.zeros((B, scores.shape[0]))
    for start in range(0, scores.shape[1], block):
        order = np.argsort(rng.random(totals.shape), axis=1)
        totals += scores[:, start : start + block].sum(axis=1)[order]
    null = (
        scores.shape[1]
        * np.square(totals / scores.shape[1] - scores.mean()).sum(axis=1)
        / scores.var(ddof=1)
    )
    return observed, (1 + np.count_nonzero(null >= observed - 1e-10)) / (B + 1)


def historical():
    daily = pd.read_csv(OUT / "tables/same_month_daily.csv")
    rows = []
    for (site, month), group in daily.groupby(["location_id", "month"]):
        for field in FEATURES:
            x = group.pivot(index="year", columns="day", values=field).to_numpy()
            assert x.shape[0] == 6 and np.isfinite(x).all()
            ranks = rankdata(x).reshape(x.shape)
            dev = np.abs(x - np.median(x, axis=1, keepdims=True))
            scores = norm.ppf(0.5 + rankdata(dev).reshape(x.shape) / (2 * (x.size + 1)))
            h, p = block_score_test(ranks)
            f, fp = block_score_test(scores)
            assert np.isclose(h, kruskal(*x).statistic)
            assert np.isclose(f, fligner(*x, center="median").statistic)
            rows.append(
                {
                    "location_id": site,
                    "month": month,
                    "variable": field,
                    "kw_H": h,
                    "level_p": p,
                    "fligner_stat": f,
                    "spread_p": fp,
                }
            )
    results = pd.DataFrame(rows)
    for ix in results.groupby(["location_id", "variable"]).groups.values():
        adj = multipletests(
            results.loc[ix, ["level_p", "spread_p"]].to_numpy().ravel(), method="holm"
        )[1].reshape(-1, 2)
        results.loc[ix, "level_p_holm"] = adj[:, 0]
        results.loc[ix, "spread_p_holm"] = adj[:, 1]
    results.to_csv(OUT / "tables/nonparametric_same_month_tests.csv", index=False)
    print(
        "Historical:",
        (results.level_p_holm < 0.05).sum(),
        "rank;",
        (results.spread_p_holm < 0.05).sum(),
        "spread",
        flush=True,
    )


def elevation():
    monthly = pd.read_csv(OUT / "tables/elevation_2026_jan_aug_sites.csv")
    assert len(monthly) == 800 and monthly.groupby("location_id").month.nunique().eq(8).all()
    meta = monthly[monthly.month == 1].sort_values("location_id")
    labels = np.digitize(meta.elevation_m, [500, 1500])
    counts = np.bincount(labels, minlength=3)
    assert (counts >= 5).all()
    rng = np.random.default_rng(20260917)
    perms = np.broadcast_to(labels, (B, len(labels))).copy()
    for country in meta.country.unique():
        ix = np.flatnonzero(meta.country.to_numpy() == country)
        order = np.argsort(rng.random((B, len(ix))), axis=1)
        perms[:, ix] = labels[ix][order]
    masks = [(perms == g).astype(float) for g in range(3)]
    rows = []
    descriptions = []
    for field, (label, unit) in FEATURES.items():
        fig, axes = plt.subplots(4, 2, figsize=(11, 12), layout="constrained")
        for ax, month in zip(axes.flat, range(1, 9)):
            sub = monthly[monthly.month == month].sort_values("location_id")
            assert sub.location_id.tolist() == meta.location_id.tolist()
            y = sub[field].to_numpy()
            ranks = rankdata(y)
            groups = [y[labels == g] for g in range(3)]
            stat = float(kruskal(*groups).statistic)
            # Ties corrected by sample rank variance, equal to scipy Kruskal H.
            observed = sum(
                len(v) * (ranks[labels == g].mean() - ranks.mean()) ** 2
                for g, v in enumerate(groups)
            ) / ranks.var(ddof=1)
            assert np.isclose(observed, stat)
            null = sum(
                counts[g] * np.square(mask @ ranks / counts[g] - ranks.mean())
                for g, mask in enumerate(masks)
            ) / ranks.var(ddof=1)
            p = (1 + np.count_nonzero(null >= stat - 1e-10)) / (B + 1)
            rows.append(
                {
                    "variable": field,
                    "month": month,
                    "kw_H": stat,
                    "p": p,
                    "spearman_rho": spearmanr(meta.elevation_m, y).statistic,
                }
            )
            for g, v in enumerate(groups):
                descriptions.append(
                    {
                        "variable": field,
                        "month": month,
                        "band": g,
                        "n": len(v),
                        "median": np.median(v),
                        "q25": np.quantile(v, 0.25),
                        "q75": np.quantile(v, 0.75),
                    }
                )
            ax.boxplot(
                groups,
                tick_labels=[
                    f"<500 m\nn={counts[0]}",
                    f"500–<1500 m\nn={counts[1]}",
                    f"≥1500 m\nn={counts[2]}",
                ],
            )
            for g, v in enumerate(groups, 1):
                ax.scatter(
                    g + rng.uniform(-0.13, 0.13, len(v)), v, s=13, alpha=0.5, color="#167b79"
                )
            ax.set(
                title=calendar.month_name[month],
                ylabel=f"{label} ({unit})",
            )
            ax.grid(axis="y", alpha=0.15)
        fig.suptitle(f"{label} across elevation bands · 2026", fontsize=14)
        fig.savefig(ROOT / f"docs/report/img/nonparam_elevation_{field}.png", dpi=180)
        plt.close(fig)
    result = pd.DataFrame(rows)
    result["p_holm"] = multipletests(result.p, method="holm")[1]
    result.to_csv(OUT / "tables/nonparametric_elevation_months.csv", index=False)
    pd.DataFrame(descriptions).to_csv(
        OUT / "tables/nonparametric_elevation_band_summaries.csv", index=False
    )
    print("Elevation bands", counts.tolist(), flush=True)
    print(result.to_string(index=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--elevation-only", action="store_true")
    args = parser.parse_args()
    if not args.elevation_only:
        historical()
    elevation()
    (OUT / "nonparametric_tests.json").write_text(
        json.dumps(
            {
                "historical": "Kruskal–Wallis ranks and Fligner–Killeen normal scores of median-centred absolute deviations; matched calendar-block score permutations",
                "historical_correction": "Holm within each site/feature, 24 tests",
                "historical_block_days": 7,
                "permutations": B,
                "seed": 20260917,
                "elevation": "Kruskal–Wallis elevation bands; label permutations restricted within country",
                "elevation_correction": "Holm over all 56 feature/month tests",
                "elevation_band_edges_m": [500, 1500],
                "months_2026": list(range(1, 9)),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "daily_sha256": hashlib.sha256(
                    (OUT / "tables/same_month_daily.csv").read_bytes()
                ).hexdigest(),
                "monthly_sha256": hashlib.sha256(
                    (OUT / "tables/elevation_2026_jan_aug_sites.csv").read_bytes()
                ).hexdigest(),
                "limitations": "Score permutation conditional on estimated medians; temporal dependence across blocks and spatial dependence within countries remain; not causal or an interaction test",
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
