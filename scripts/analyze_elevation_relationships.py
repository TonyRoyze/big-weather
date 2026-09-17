"""Plot matched site-level relationships and assess weather importance for elevation.

Uses the frozen common-coverage panel; each location is one observation. Country
GroupKFold prevents sites from a held-out country entering its training set.
"""

import hashlib
import json
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/replication"
FEATURES = {
    "temperature_2m": ("Temperature", "°C"),
    "precipitation": ("Daily precipitation", "mm/day"),
    "wind_speed_10m": ("Wind speed at 10 m", "m/s"),
    "relative_humidity_2m": ("Relative humidity", "%"),
    "surface_pressure": ("Surface pressure", "hPa"),
    "cloud_cover": ("Cloud cover", "%"),
    "shortwave_radiation": ("Shortwave radiation", "W/m²"),
}


def main():
    panel_path = OUT / "panel.parquet"
    manifest = json.loads((OUT / "manifest.json").read_text())
    data = pd.read_parquet(panel_path)
    assert len(data) == manifest["common_rows"]
    assert not data.duplicated(["location_id", "timestamp"]).any()
    assert data[list(FEATURES)].notna().all().all()
    assert data.groupby("location_id").size().eq(manifest["common_days"] * 24).all()
    sites = data.groupby("location_id")[list(FEATURES)].mean()
    sites["precipitation"] *= 24  # Complete days: hourly means to mean daily totals.
    meta = data.groupby("location_id")[["name", "country", "elevation_m"]].first()
    sites = sites.join(meta).reset_index()
    assert len(sites) == manifest["locations"]
    sites.to_csv(OUT / "tables/elevation_weather_features.csv", index=False)
    correlations = []
    for scope, subset in [("Regional", sites), ("Sri Lanka", sites[sites.country == "LK"])]:
        for variable in FEATURES:
            r, p = stats.pearsonr(subset.elevation_m, subset[variable])
            rho, sp = stats.spearmanr(subset.elevation_m, subset[variable])
            correlations.append(
                {
                    "scope": scope,
                    "variable": variable,
                    "n": len(subset),
                    "pearson": r,
                    "p": p,
                    "spearman": rho,
                    "spearman_p": sp,
                }
            )
    pd.DataFrame(correlations).to_csv(
        OUT / "tables/elevation_weather_correlations.csv", index=False
    )
    plt.rcParams.update(
        {"font.size": 10, "savefig.dpi": 180, "axes.spines.top": False, "axes.spines.right": False}
    )
    for fields, filename in [
        (
            ["precipitation", "wind_speed_10m", "relative_humidity_2m"],
            "elevation_rain_wind_humidity",
        ),
        (
            ["surface_pressure", "cloud_cover", "shortwave_radiation"],
            "elevation_pressure_cloud_radiation",
        ),
    ]:
        fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), layout="constrained")
        for ax, field in zip(axes, fields):
            for is_lk, color, label in [
                (False, "#9aa9b4", "Other regional sites"),
                (True, "#167b79", "Sri Lanka"),
            ]:
                subset = sites[(sites.country == "LK") == is_lk]
                ax.scatter(
                    subset.elevation_m,
                    subset[field],
                    color=color,
                    s=29,
                    alpha=0.85,
                    edgecolor="white",
                    linewidth=0.4,
                    label=label,
                )
            r = stats.pearsonr(sites.elevation_m, sites[field]).statistic
            ax.set(
                title=f"{FEATURES[field][0]} · r = {r:+.3f}",
                xlabel="Elevation (m)",
                ylabel=f"Mean {FEATURES[field][0].lower()} ({FEATURES[field][1]})",
            )
            ax.grid(alpha=0.15)
        axes[0].legend(frameon=False, fontsize=8, loc="best")
        fig.savefig(OUT / f"figures/{filename}.png")
        plt.close(fig)
    folds = list(GroupKFold(n_splits=5).split(sites, groups=sites.country))
    predictions = []
    importance = []
    fold_records = []
    scores = []
    for variant, fields in [
        ("All weather features", list(FEATURES)),
        ("Without surface pressure", [f for f in FEATURES if f != "surface_pressure"]),
    ]:
        all_predictions = np.empty(len(sites))
        baseline = np.empty(len(sites))
        visited = np.zeros(len(sites), dtype=int)
        for fold, (tr, te) in enumerate(folds, 1):
            assert set(sites.iloc[tr].country).isdisjoint(sites.iloc[te].country)
            assert set(sites.iloc[tr].location_id).isdisjoint(sites.iloc[te].location_id)
            Xtrain = sites.iloc[tr][fields]
            Xtest = sites.iloc[te][fields]
            ytrain = sites.iloc[tr].elevation_m
            ytest = sites.iloc[te].elevation_m
            model = RandomForestRegressor(
                n_estimators=300,
                max_depth=6,
                min_samples_leaf=2,
                max_features=1.0,
                random_state=42,
                n_jobs=2,
            ).fit(Xtrain, ytrain)
            pred = model.predict(Xtest)
            all_predictions[te] = pred
            baseline[te] = ytrain.mean()
            visited[te] += 1
            perm = permutation_importance(
                model,
                Xtest,
                ytest,
                scoring="neg_mean_absolute_error",
                n_repeats=20,
                random_state=42 + fold,
                n_jobs=1,
            )
            for j, field in enumerate(fields):
                importance.append(
                    {
                        "variant": variant,
                        "fold": fold,
                        "test_sites": len(te),
                        "feature": field,
                        "split_importance": model.feature_importances_[j],
                        "mae_increase_m": perm.importances_mean[j],
                        "repeat_sd_m": perm.importances_std[j],
                    }
                )
            for j, idx in enumerate(te):
                predictions.append(
                    {
                        "variant": variant,
                        "fold": fold,
                        "location_id": sites.iloc[idx].location_id,
                        "country": sites.iloc[idx].country,
                        "actual_m": float(ytest.iloc[j]),
                        "predicted_m": pred[j],
                        "baseline_m": float(ytrain.mean()),
                    }
                )
            fold_records.append(
                {
                    "variant": variant,
                    "fold": fold,
                    "test_countries": ",".join(sorted(set(sites.iloc[te].country))),
                    "train_sites": len(tr),
                    "test_sites": len(te),
                    "mae_m": mean_absolute_error(ytest, pred),
                }
            )
        assert (visited == 1).all()
        scores.append(
            {
                "variant": variant,
                "sites": len(sites),
                "mae_m": mean_absolute_error(sites.elevation_m, all_predictions),
                "r2": r2_score(sites.elevation_m, all_predictions),
                "baseline_mae_m": mean_absolute_error(sites.elevation_m, baseline),
            }
        )
    raw = pd.DataFrame(importance)
    raw.to_csv(OUT / "tables/elevation_importance_folds.csv", index=False)
    pd.DataFrame(predictions).to_csv(OUT / "tables/elevation_oof_predictions.csv", index=False)
    pd.DataFrame(fold_records).to_csv(OUT / "tables/elevation_country_folds.csv", index=False)
    pd.DataFrame(scores).to_csv(OUT / "tables/elevation_model_metrics.csv", index=False)
    summaries = []
    for (variant, feature), group in raw.groupby(["variant", "feature"]):
        weights = group.test_sites
        summaries.append(
            {
                "variant": variant,
                "feature": feature,
                "mae_increase_m": np.average(group.mae_increase_m, weights=weights),
                "split_importance": np.average(group.split_importance, weights=weights),
                "fold_sd_m": np.sqrt(
                    np.average(
                        (group.mae_increase_m - np.average(group.mae_increase_m, weights=weights))
                        ** 2,
                        weights=weights,
                    )
                ),
            }
        )
    summary = pd.DataFrame(summaries)
    summary.to_csv(OUT / "tables/elevation_feature_importance.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
    for ax, variant in zip(axes, ["All weather features", "Without surface pressure"]):
        sub = summary[summary.variant == variant].sort_values("mae_increase_m")
        ax.barh(
            [FEATURES[f][0] for f in sub.feature],
            sub.mae_increase_m,
            color="#167b79",
            xerr=sub.fold_sd_m,
            error_kw={"elinewidth": 1, "capsize": 3, "ecolor": "#50616a"},
        )
        ax.axvline(0, color="#777", lw=0.7)
        ax.set(title=variant, xlabel="Increase in held-out elevation MAE (m)")
    fig.savefig(OUT / "figures/elevation_feature_importance.png")
    plt.close(fig)
    result = {
        "status": "passed",
        "source_fingerprint": manifest["fingerprint"],
        "panel_sha256": hashlib.sha256(panel_path.read_bytes()).hexdigest(),
        "analysis_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "target": "elevation_m",
        "observation_unit": "one period mean per location",
        "sites": len(sites),
        "countries": int(sites.country.nunique()),
        "features": list(FEATURES),
        "validation": "5-fold GroupKFold by country; one held-out prediction per site",
        "permutation_repeats": 20,
        "permutation_scoring": "negative mean absolute error",
        "seed": 42,
        "model_parameters": {
            "n_estimators": 300,
            "max_depth": 6,
            "min_samples_leaf": 2,
            "max_features": 1.0,
        },
        "tuning": "none",
        "metrics": scores,
        "checks": [
            "balanced coverage",
            "complete inputs",
            "unique hourly keys",
            "disjoint train/test countries and sites",
            "one held-out prediction per site",
        ],
    }
    (OUT / "elevation_analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    print(pd.DataFrame(correlations).to_string(index=False))
    print(pd.DataFrame(scores).to_string(index=False))
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
