"""Reproduce the reference project's methods on a fingerprinted, coverage-matched snapshot.

See reports/replication/README.md for provenance, adaptations and commands.
"""

import argparse
import calendar
import hashlib
import importlib.metadata
import json
import os
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("OMP_NUM_THREADS", "4")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from scipy import stats
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "75aa5b3b00cbe3630833ad49902026171a054332"
METRICS = [
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "relative_humidity_2m",
    "pressure_msl",
]
ORIGINAL = ["lk_jaffna", "lk_batticaloa", "lk_trincomalee", "lk_colombo", "lk_matara", "lk_galle"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, default=str, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data/regional-2020-2025")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/replication")
    parser.add_argument("--resume-ml", action="store_true")
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    tables = out / "tables"
    figures = out / "figures"
    tables.mkdir(exist_ok=True)
    figures.mkdir(exist_ok=True)
    # Reuse upstream preparation, evaluation, clustered regression and screening definitions.
    config = types.ModuleType("config")
    config.PROCESSED = out
    config.TABLES = tables
    config.FIGURES = figures
    config.RANDOM_STATE = 42
    sys.modules["config"] = config
    sys.path.insert(0, str(ROOT / "scripts/replication"))
    from data_quality import PLAUSIBLE_RANGES
    from ml_pipeline import FEATURES, evaluate, prepare
    from regression import fit_clustered

    plt.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 160,
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    if not args.resume_ml:
        records = []
        for metadata in sorted(
            (args.data_root / "raw/weather").glob("location_id=*/year=*/_source*.json")
        ):
            file = metadata.with_name(
                metadata.name.replace("_source", "weather").replace(".json", ".parquet")
            )
            if not file.exists():
                continue
            request = json.loads(metadata.read_text())["request"]
            records.append(
                {
                    "path": str(file.resolve()),
                    "sha256": sha(file),
                    "bytes": file.stat().st_size,
                    "metadata_sha256": sha(metadata),
                    **request,
                }
            )
        pd.DataFrame(records).to_csv(tables / "source_files.csv", index=False)
        fingerprint = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()
        print("Reading committed snapshot", len(records), fingerprint, flush=True)
        dataset = ds.dataset(
            [r["path"] for r in records],
            format="parquet",
            partitioning="hive",
            partition_base_dir=str((args.data_root / "raw/weather").resolve()),
        )
        raw = dataset.to_table().to_pandas()
        raw["timestamp"] = pd.to_datetime(raw.timestamp, utc=True)
        assert raw.duplicated(["location_id", "timestamp"]).sum() == 0, (
            "Overlapping chunks: stop instead of double counting"
        )
        assert raw.timestamp.notna().all()
        assert (raw.timestamp == raw.timestamp.dt.floor("h")).all()
        locations = pd.read_parquet(args.data_root / "raw/locations")
        weather_columns = [
            c for c in raw.select_dtypes("number").columns if c not in {"year", "source_year"}
        ]
        miss = raw[weather_columns].isna().sum().rename("missing").to_frame()
        miss["percent"] = miss.missing / len(raw) * 100
        miss.to_csv(tables / "missingness.csv")
        raw.groupby(raw.timestamp.dt.year)[weather_columns].agg(lambda s: s.isna().sum()).to_csv(
            tables / "missingness_by_year.csv"
        )
        frame = raw.merge(locations, on="location_id", validate="many_to_one")
        assert len(frame) == len(raw) and frame.latitude.notna().all()
        bounds = dict(PLAUSIBLE_RANGES)
        # Reference thresholds assumed coastal Sri Lanka. Broaden thermal and pressure
        # screens for Himalayan sites; these are screening bounds, not deletion rules.
        bounds.update(
            temperature_2m=(-90, 60),
            apparent_temperature=(-100, 75),
            dew_point_2m=(-100, 60),
            surface_pressure=(300, 1100),
        )
        quality = []
        for col, (low, high) in bounds.items():
            if col in frame:
                quality.append(
                    {
                        "variable": col,
                        "lower": low,
                        "upper": high,
                        "outside": int(((frame[col] < low) | (frame[col] > high)).sum()),
                    }
                )
        pd.DataFrame(quality).to_csv(tables / "plausibility.csv", index=False)
        coverage = (
            frame.groupby("location_id")
            .agg(start=("timestamp", "min"), end=("timestamp", "max"), hours=("timestamp", "size"))
            .reset_index()
            .merge(locations, on="location_id")
        )
        coverage.to_csv(tables / "coverage.csv", index=False)
        frame["date"] = frame.timestamp.dt.floor("D")
        frame["month"] = frame.timestamp.dt.month
        frame["year"] = frame.timestamp.dt.year
        grouped = frame.groupby(["location_id", "date"])
        daycounts = grouped[METRICS].count()
        daily = grouped[METRICS].mean()
        daily["precipitation"] = grouped.precipitation.sum(min_count=1)
        daily = daily.where(daycounts == 24)
        daily["hours"] = grouped.size()
        daily = daily.reset_index().merge(locations, on="location_id", validate="many_to_one")
        valid = daily[(daily.hours == 24) & daily[METRICS].notna().all(axis=1)]
        shared = valid.groupby("date").location_id.nunique()
        shared = shared[shared == len(coverage)].index
        assert len(shared), "No complete common daily coverage"
        end = shared.max()
        start = end
        dateset = set(shared)
        while start - pd.Timedelta(days=1) in dateset:
            start -= pd.Timedelta(days=1)
        panel = frame[(frame.date >= start) & (frame.date <= end)].copy()
        assert len(panel) == len(coverage) * ((end - start).days + 1) * 24
        panel.to_parquet(out / "panel.parquet", index=False)
        dpanel = daily[daily.date.between(start, end)].copy()
        dpanel.to_parquet(out / "daily_panel.parquet", index=False)
        agg = (
            dpanel.groupby("location_id")[METRICS]
            .mean()
            .reset_index()
            .merge(locations, on="location_id")
        )
        agg["period_rainfall_mm"] = (
            dpanel.groupby("location_id").precipitation.sum().reindex(agg.location_id).values
        )
        agg.to_csv(tables / "location_summary.csv", index=False)
        panel[METRICS].describe().T.to_csv(tables / "hourly_summary.csv")
        corrs = []
        for scope, group in [
            ("Regional", agg),
            ("Sri Lanka", agg[agg.country == "LK"]),
            ("Original six", agg[agg.location_id.isin(ORIGINAL)]),
        ]:
            for x in ["elevation_m", "latitude", "longitude"]:
                for y in METRICS:
                    r, p = stats.pearsonr(group[x], group[y])
                    rho, sp = stats.spearmanr(group[x], group[y])
                    corrs.append(
                        {
                            "scope": scope,
                            "n": len(group),
                            "predictor": x,
                            "outcome": y,
                            "r": float(r),
                            "p": float(p),
                            "spearman": float(rho),
                            "spearman_p": float(sp),
                        }
                    )
        pd.DataFrame(corrs).to_csv(tables / "correlations.csv", index=False)
        pd.DataFrame(
            [
                {"metric": m, "statistic": float(result.statistic), "p": float(result.pvalue)}
                for m in METRICS[:2]
                for result in [
                    stats.kruskal(*[g[m].values for _, g in dpanel.groupby("location_id")])
                ]
            ]
        ).to_csv(tables / "location_tests.csv", index=False)
        # Same complete six-site, six-year comparison as upstream, now including Matara 2025.
        hist = frame[frame.location_id.isin(ORIGINAL) & frame.year.between(2020, 2025)]
        annual = (
            hist.groupby(["location_id", "year"])
            .agg(
                hours=("timestamp", "size"),
                temperature=("temperature_2m", "mean"),
                rainfall_mm=("precipitation", "sum"),
                wind=("wind_speed_10m", "mean"),
            )
            .reset_index()
        )
        annual["expected_hours"] = annual.year.map(
            lambda y: (366 if calendar.isleap(y) else 365) * 24
        )
        annual["complete"] = annual.hours == annual.expected_hours
        annual.to_csv(tables / "original_six_annual.csv", index=False)
        regressions = []
        for scope, sub in [("Regional", panel), ("Sri Lanka", panel[panel.country == "LK"])]:
            formulas = [
                "temperature_2m ~ elevation_m",
                "temperature_2m ~ elevation_m + latitude + longitude",
                "temperature_2m ~ elevation_m + latitude + longitude + C(month)",
            ]
            if scope == "Regional":
                formulas.append(
                    "temperature_2m ~ elevation_m + latitude + longitude + C(month) + C(country)"
                )
            for i, formula in enumerate(formulas, 1):
                result = fit_clustered(sub, formula, f"{scope}, model {i}")
                pd.DataFrame(
                    {
                        "coef": result.params,
                        "standard_error": result.bse,
                        "p": result.pvalues,
                        "ci_low": result.conf_int()[0],
                        "ci_high": result.conf_int()[1],
                    }
                ).to_csv(tables / f"regression_{scope.replace(' ', '_')}_{i}.csv")
                regressions.append(
                    {
                        "scope": scope,
                        "model": i,
                        "formula": formula,
                        "r2": result.rsquared,
                        "elevation_per_km": result.params.elevation_m * 1000,
                        "p": result.pvalues.elevation_m,
                        "ci_low": result.conf_int().loc["elevation_m", 0] * 1000,
                        "ci_high": result.conf_int().loc["elevation_m", 1] * 1000,
                    }
                )
        pd.DataFrame(regressions).to_csv(tables / "regression_comparison.csv", index=False)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        for ax, (scope, sub) in zip(
            axes,
            [
                ("Regional · 100 locations", agg),
                ("Sri Lanka · 30 locations", agg[agg.country == "LK"]),
            ],
        ):
            sc = ax.scatter(
                sub.elevation_m,
                sub.temperature_2m,
                c=sub.latitude,
                cmap="viridis",
                s=34,
                edgecolor="white",
                linewidth=0.4,
            )
            slope, intercept, *_ = stats.linregress(sub.elevation_m, sub.temperature_2m)
            x = np.array([sub.elevation_m.min(), sub.elevation_m.max()])
            ax.plot(x, intercept + slope * x, color="#a94e32", lw=1.5)
            ax.set(xlabel="Elevation (m)", ylabel="Mean temperature (°C)", title=scope)
            fig.colorbar(sc, ax=ax, label="Latitude (°N)")
        fig.suptitle(f"Identical coverage: {start.date()} to {end.date()}")
        fig.tight_layout()
        fig.savefig(figures / "elevation_temperature.png")
        plt.close(fig)
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
        country = (
            agg.groupby("country")[["temperature_2m", "precipitation"]]
            .mean()
            .sort_values("temperature_2m")
        )
        country.temperature_2m.plot.barh(ax=axes[0], color="#28747a")
        country.precipitation.plot.barh(ax=axes[1], color="#517db0")
        axes[0].set(
            xlabel="Mean temperature (°C)",
            ylabel="Country",
            title="Equal weight per sampled location",
        )
        axes[1].set(
            xlabel="Mean daily rainfall (mm/day)",
            ylabel="Country",
            title="Selected sites, not national estimates",
        )
        fig.tight_layout()
        fig.savefig(figures / "country_weather.png")
        plt.close(fig)
        country.to_csv(tables / "country_summary.csv")
        monthly = (
            dpanel.assign(month=dpanel.date.dt.month)
            .groupby(["country", "month"])
            .temperature_2m.mean()
            .unstack()
        )
        import seaborn as sns

        fig, ax = plt.subplots(figsize=(8, 5))
        sns.heatmap(monthly, annot=True, fmt=".1f", cmap="YlOrRd", ax=ax, cbar_kws={"label": "°C"})
        ax.set(
            xlabel="Month in 2026 (May begins on 5th)",
            ylabel="Country",
            title="Mean temperature at equally weighted sampled sites",
        )
        fig.tight_layout()
        fig.savefig(figures / "monthly_temperature.png")
        plt.close(fig)
        monthly.to_csv(tables / "monthly_temperature.csv")
        # Verify snapshot files have not changed while being read.
        assert all(sha(r["path"]) == r["sha256"] for r in records), (
            "Snapshot changed during analysis; rerun"
        )
        manifest = {
            "created_utc": datetime.now(UTC).isoformat(),
            "reference_repository": "https://github.com/KaumindiHerath/Big_Data_Geospatial_Project",
            "reference_commit": COMMIT,
            "fingerprint": fingerprint,
            "rows": len(frame),
            "committed_files": len(records),
            "raw_bytes": sum(r["bytes"] for r in records),
            "weather_columns": len(weather_columns),
            "locations": len(coverage),
            "countries": int(coverage.country.nunique()),
            "earliest": str(frame.timestamp.min()),
            "latest": str(frame.timestamp.max()),
            "elevation_min": float(coverage.elevation_m.min()),
            "elevation_max": float(coverage.elevation_m.max()),
            "common_start": str(start.date()),
            "common_end": str(end.date()),
            "common_days": (end - start).days + 1,
            "common_rows": len(panel),
            "key_duplicates": 0,
            "missing": miss[miss.missing > 0].reset_index().to_dict("records"),
            "plausibility": quality,
            "versions": {
                name: importlib.metadata.version(name)
                for name in [
                    "pandas",
                    "pyarrow",
                    "scipy",
                    "scikit-learn",
                    "statsmodels",
                    "matplotlib",
                    "xgboost",
                    "shap",
                ]
            },
            "reference_hashes": {
                p.name: sha(p) for p in (ROOT / "scripts/replication").glob("*.py")
            },
        }
        save_json(out / "manifest.json", manifest)
    else:
        panel = pd.read_parquet(out / "panel.parquet")
    print("Starting time-held-out modelling", flush=True)
    prepared = prepare(panel).sort_values(["timestamp", "location_id"]).reset_index(drop=True)
    # Last complete calendar month is held out; never randomly mix future hours into training.
    test_start = prepared.timestamp.max().normalize().replace(day=1)
    train = prepared[prepared.timestamp < test_start]
    test = prepared[prepared.timestamp >= test_start]
    assert len(train) and len(test) and train.timestamp.max() < test.timestamp.min()
    Xtr, ytr = train[FEATURES], train.temperature_2m
    Xte, yte = test[FEATURES], test.temperature_2m
    models = {
        "Mean baseline": DummyRegressor(),
        "Linear regression": LinearRegression(),
        "Random forest": RandomForestRegressor(
            n_estimators=200, max_depth=12, random_state=42, n_jobs=4
        ),
        "Gradient boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.1, random_state=42
        ),
        "XGBoost": XGBRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=4,
        ),
    }
    results = []
    predictions = {}
    for name, model in models.items():
        print("Fitting", name, flush=True)
        model.fit(Xtr, ytr)
        predictions[name] = model.predict(Xte)
        results.append(evaluate(name, yte, predictions[name]))
        pd.DataFrame(results).to_csv(tables / "model_comparison.csv", index=False)
    # Deterministic evenly spaced timestamp sampling bounds tuning cost, without mixing dates.
    # All locations at a selected hour are kept together. Final fit still uses every training row.
    hours = np.array(sorted(train.timestamp.unique()))
    selected_hours = hours[np.linspace(0, len(hours) - 1, min(400, len(hours)), dtype=int)]
    tuning = train[train.timestamp.isin(selected_hours)].reset_index(drop=True)
    folds = []
    for a, b in TimeSeriesSplit(n_splits=4).split(selected_hours):
        tr = np.flatnonzero(tuning.timestamp.isin(selected_hours[a]))
        va = np.flatnonzero(tuning.timestamp.isin(selected_hours[b]))
        folds.append((tr, va))
        assert tuning.iloc[tr].timestamp.max() < tuning.iloc[va].timestamp.min()
    pd.DataFrame(
        [
            {
                "fold": i + 1,
                "train_start": str(tuning.iloc[a].timestamp.min()),
                "train_end": str(tuning.iloc[a].timestamp.max()),
                "validation_start": str(tuning.iloc[b].timestamp.min()),
                "validation_end": str(tuning.iloc[b].timestamp.max()),
                "train_rows": len(a),
                "validation_rows": len(b),
            }
            for i, (a, b) in enumerate(folds)
        ]
    ).to_csv(tables / "tuning_folds.csv", index=False)
    search = RandomizedSearchCV(
        RandomForestRegressor(random_state=42, n_jobs=4),
        {
            "n_estimators": [100, 200, 300],
            "max_depth": [6, 10, 14, None],
            "min_samples_leaf": [1, 5, 20],
            "max_features": ["sqrt", 0.7, 1.0],
        },
        n_iter=10,
        cv=folds,
        scoring="neg_root_mean_squared_error",
        random_state=42,
        n_jobs=1,
        refit=False,
    )
    print("Tuning on", len(tuning), "rows; 10 candidates × 4 chronological folds", flush=True)
    search.fit(tuning[FEATURES], tuning.temperature_2m)
    pd.DataFrame(search.cv_results_).to_csv(tables / "tuning_results.csv", index=False)
    tuned = RandomForestRegressor(**search.best_params_, random_state=42, n_jobs=4).fit(Xtr, ytr)
    predictions["Tuned random forest"] = tuned.predict(Xte)
    results.append(evaluate("Tuned random forest", yte, predictions["Tuned random forest"]))
    pd.DataFrame(results).to_csv(tables / "model_comparison.csv", index=False)
    test_out = test[["location_id", "timestamp", "temperature_2m"]].copy()
    test_out["prediction"] = predictions["Tuned random forest"]
    test_out["absolute_error"] = (test_out.temperature_2m - test_out.prediction).abs()
    test_out.groupby("location_id").absolute_error.mean().to_csv(
        tables / "test_mae_by_location.csv"
    )
    # Group-level importance is descriptive, not a causal effect of correlated predictors.
    importance_sample = test.sample(min(5000, len(test)), random_state=42)
    perm = permutation_importance(
        tuned,
        importance_sample[FEATURES],
        importance_sample.temperature_2m,
        n_repeats=5,
        random_state=42,
        n_jobs=1,
    )
    assert np.allclose(
        perm.importances_mean[
            [i for i, f in enumerate(FEATURES) if importance_sample[f].nunique() == 1]
        ],
        0,
    )
    importance = pd.DataFrame(
        {
            "feature": FEATURES,
            "built_in": tuned.feature_importances_,
            "permutation_r2_drop": perm.importances_mean,
            "permutation_std": perm.importances_std,
        }
    )
    importance.to_csv(tables / "feature_importance.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, col, title in zip(
        axes,
        ["built_in", "permutation_r2_drop"],
        ["Tree split importance", "Permutation importance · R² decrease"],
    ):
        importance.set_index("feature")[col].sort_values().plot.barh(ax=ax, color="#28747a")
        ax.set(title=title, ylabel="")
    fig.tight_layout()
    fig.savefig(figures / "feature_importance.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 4.5))
    small = test_out.sample(min(5000, len(test_out)), random_state=42)
    ax.scatter(small.temperature_2m, small.prediction, s=4, alpha=0.15, color="#28747a")
    lo, hi = yte.min(), yte.max()
    ax.plot([lo, hi], [lo, hi], color="#a94e32")
    ax.set(
        xlabel="Observed temperature (°C)",
        ylabel="Predicted temperature (°C)",
        title="Tuned random forest · held-out August 2026",
    )
    fig.tight_layout()
    fig.savefig(figures / "predicted_temperature.png")
    plt.close(fig)
    print("Computing SHAP for 2,000 test rows", flush=True)
    import shap

    sample = Xte.sample(min(2000, len(Xte)), random_state=42)
    sv = shap.TreeExplainer(tuned).shap_values(sample)
    pd.Series(np.abs(sv).mean(axis=0), index=FEATURES, name="mean_absolute_shap").to_csv(
        tables / "shap_importance.csv"
    )
    shap.summary_plot(sv, sample, show=False)
    plt.tight_layout()
    plt.savefig(figures / "shap_summary.png")
    plt.close()
    save_json(
        out / "ml_manifest.json",
        {
            "train_rows": len(train),
            "test_rows": len(test),
            "train_start": str(train.timestamp.min()),
            "train_end": str(train.timestamp.max()),
            "test_start": str(test.timestamp.min()),
            "test_end": str(test.timestamp.max()),
            "features": FEATURES,
            "best_parameters": search.best_params_,
            "tuning_rows": len(tuning),
            "tuning_candidates": 10,
            "folds": 4,
            "permutation_sample": 5000,
            "shap_sample": len(sample),
            "seed": 42,
        },
    )
    print("Replication completed", flush=True)


if __name__ == "__main__":
    main()
