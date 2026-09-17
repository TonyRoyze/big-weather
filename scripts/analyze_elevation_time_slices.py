"""Test monthly elevation associations and paired changes using the frozen panel."""

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from analyze_elevation_relationships import FEATURES
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/replication"


def change_test(monthly, field, months):
    """Paired site changes remove time-invariant site differences."""
    base = monthly[monthly.month == months[0]].set_index("location_id")[field]
    changes = monthly[monthly.month.isin(months[1:])].copy()
    changes["change"] = changes[field] - changes.location_id.map(base)
    formula = (
        "change ~ 0 + C(month):C(country) + C(month):latitude"
        " + C(month):longitude + C(month):elevation_km"
    )
    model = smf.ols(formula, changes)
    assert np.linalg.matrix_rank(model.exog) == model.exog.shape[1]
    result = model.fit(cov_type="cluster", cov_kwds={"groups": changes.location_id}, use_t=True)
    names = [x for x in result.params.index if x.endswith(":elevation_km")]
    restriction = np.zeros((len(names), len(result.params)))
    for i, name in enumerate(names):
        restriction[i, result.params.index.get_loc(name)] = 1
    test = result.wald_test(restriction, use_f=True, scalar=True)
    # Conservative diagnostic for correlation between different sites in a country.
    country = model.fit(cov_type="cluster", cov_kwds={"groups": changes.country}, use_t=True)
    country_test = country.wald_test(restriction, use_f=True, scalar=True)
    return {
        "variable": field,
        "months": ",".join(map(str, months)),
        "F": float(test.statistic),
        "df_num": float(test.df_num),
        "df_denom": float(test.df_denom),
        "p": float(test.pvalue),
        "country_cluster_p": float(country_test.pvalue),
    }


def main():
    path = OUT / "panel.parquet"
    data = pd.read_parquet(path)
    data["month"] = data.timestamp.dt.month
    assert not data.duplicated(["location_id", "timestamp"]).any()
    assert data[list(FEATURES)].notna().all().all()
    grouped = data.groupby(["location_id", "month"])
    monthly = grouped[list(FEATURES)].mean()
    monthly["precipitation"] *= 24
    monthly = monthly.join(grouped[["country", "latitude", "longitude", "elevation_m"]].first())
    monthly["hours"] = grouped.size()
    monthly = monthly.reset_index()
    assert len(monthly) == 400
    assert monthly.groupby("month").hours.nunique().eq(1).all()
    assert monthly.groupby("month").hours.first().to_dict() == {5: 648, 6: 720, 7: 744, 8: 744}
    monthly["elevation_km"] = monthly.elevation_m / 1000
    monthly.to_csv(OUT / "tables/elevation_monthly_sites.csv", index=False)
    slopes, changes = [], []
    for field in FEATURES:
        for month, subset in monthly.groupby("month"):
            model = smf.ols(f"{field} ~ elevation_km + latitude + longitude + C(country)", subset)
            assert np.linalg.matrix_rank(model.exog) == model.exog.shape[1]
            result = model.fit(cov_type="HC3", use_t=True)
            lower, upper = result.conf_int().loc["elevation_km"]
            country = model.fit(cov_type="cluster", cov_kwds={"groups": subset.country}, use_t=True)
            slopes.append(
                {
                    "variable": field,
                    "month": month,
                    "n": len(subset),
                    "slope_per_km": result.params["elevation_km"],
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "p": result.pvalues["elevation_km"],
                    "country_cluster_p": country.pvalues["elevation_km"],
                }
            )
        for months in [[5, 6, 7, 8], [6, 7, 8]]:
            changes.append(change_test(monthly, field, months))
    slopes = pd.DataFrame(slopes)
    slopes["p_holm"] = multipletests(slopes.p, method="holm")[1]
    slopes["country_p_holm"] = multipletests(slopes.country_cluster_p, method="holm")[1]
    changes = pd.DataFrame(changes)
    # Correct all seven outcomes and both window choices together.
    changes["p_holm"] = multipletests(changes.p, method="holm")[1]
    changes["country_p_holm"] = multipletests(changes.country_cluster_p, method="holm")[1]
    slopes.to_csv(OUT / "tables/elevation_monthly_tests.csv", index=False)
    changes.to_csv(OUT / "tables/elevation_month_interactions.csv", index=False)
    plt.rcParams.update({"font.size": 10, "savefig.dpi": 180})
    fig, axes = plt.subplots(4, 2, figsize=(11, 12), layout="constrained")
    for ax, (field, (label, unit)) in zip(axes.flat, FEATURES.items()):
        sub = slopes[slopes.variable == field]
        y = sub.slope_per_km
        ax.errorbar(
            sub.month,
            y,
            yerr=[y - sub.ci_lower, sub.ci_upper - y],
            fmt="o-",
            color="#167b79",
            capsize=4,
        )
        ax.axhline(0, color="#999", lw=0.8, linestyle="--")
        ax.set(
            title=label,
            ylabel=f"{unit} per 1,000 m",
            xticks=[5, 6, 7, 8],
            xticklabels=["May*", "June", "July", "August"],
        )
        ax.grid(alpha=0.15)
        ax.spines[["top", "right"]].set_visible(False)
    axes.flat[-1].axis("off")
    axes.flat[-1].text(
        0,
        0.8,
        "Country, latitude and longitude adjusted\n100 sites per month\nBars: pointwise 95% HC3 intervals\n*May covers 5–31 May only\n\nMonthly differences do not establish\na recurring seasonal cycle.",
        va="top",
        linespacing=1.8,
    )
    fig.savefig(OUT / "figures/elevation_monthly_slopes.png")
    plt.close(fig)
    (OUT / "elevation_time_tests.json").write_text(
        json.dumps(
            {
                "panel_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "site_months": len(monthly),
                "monthly_test_count": len(slopes),
                "interaction_test_count": len(changes),
                "multiplicity": "Holm; 28 slopes and 14 interaction tests separately",
                "monthly_covariance": "HC3, Student t",
                "interaction_covariance": "site-clustered, corrected F, 99 denominator df",
                "sensitivity": "country-clustered covariance; 13 clusters; exploratory",
                "seasonality": "Not identifiable as recurring seasonality from four months in one year",
            },
            indent=2,
        )
        + "\n"
    )
    print(slopes.to_string(index=False))
    print(changes.to_string(index=False))


if __name__ == "__main__":
    main()
