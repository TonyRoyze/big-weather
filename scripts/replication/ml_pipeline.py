"""Tasks 13-18: ML target selection, leakage screening, models, tuning,
evaluation, interpretability.

TARGET SELECTION (Task 13): temperature_2m.
  - Rainfall (precipitation) is zero-inflated (~85% of hours are exactly 0mm)
    and driven by convective/stochastic processes at hourly resolution -
    a regression target here would be dominated by predicting zero and
    would not cleanly test the geography/elevation research question.
  - Wind speed is heavily influenced by very local turbulence/surface
    roughness not captured by 6 coarse ERA5 grid points.
  - Temperature is continuous, has the clearest, best-understood physical
    relationship to geography (latitude/elevation) and season of any
    variable here, and Task 12's regression already showed geography+season
    explain a real (20%) share of its variance - a legitimate, motivated
    prediction target directly aligned with the project's core objective.

LEAKAGE SCREENING (Task 14): predictors are restricted to GEOGRAPHICAL +
TEMPORAL variables only (elevation, latitude, longitude, month, hour, year).
Excluded as leakage or leakage-adjacent:
  - apparent_temperature, wet_bulb_temperature_2m, dew_point_2m,
    vapour_pressure_deficit: each is computed FROM temperature_2m (plus
    humidity/wind) by definition/near-deterministic thermodynamic formulae -
    including them would let the model "predict" temperature from something
    that is nearly an algebraic transform of temperature itself.
  - soil_temperature_0_to_7cm .. 100_to_255cm: near-surface soil temperature
    is thermally coupled to and lags air temperature very tightly at these
    depths - using it would leak most of the answer.
  - All other contemporaneous weather variables (humidity, pressure, wind,
    cloud cover, radiation, precipitation) are EXCLUDED too, for the same
    research-question-clarity reason as the regression task: this model
    tests whether geography+time (not other weather) predict temperature.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from sklearn.inspection import permutation_importance

from config import PROCESSED, TABLES, FIGURES, RANDOM_STATE

DF_PATH = PROCESSED / "analytical_dataset.parquet"
FEATURES = ["elevation_m", "latitude", "longitude", "month_sin", "month_cos",
            "hour_sin", "hour_cos", "year"]
TARGET = "temperature_2m"


def prepare(df):
    df = df.copy()
    ts = pd.to_datetime(df["timestamp"])
    df["month"] = ts.dt.month
    df["hour"] = ts.dt.hour
    df["year"] = ts.dt.year
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["timestamp"] = ts
    return df


def time_split(df):
    train = df[df["year"] <= 2024].sort_values("timestamp")
    test = df[df["year"] == 2025].sort_values("timestamp")
    print(f"Time-based split: train = {train['year'].min()}-{train['year'].max()} "
          f"(n={len(train):,}), test = 2025 (n={len(test):,})")
    return train, test


def evaluate(name, y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    return {"Model": name, "MAE": mae, "RMSE": rmse, "R2": r2}


def main():
    df = pd.read_parquet(DF_PATH)
    df = prepare(df)
    train, test = time_split(df)
    Xtr, ytr = train[FEATURES], train[TARGET]
    Xte, yte = test[FEATURES], test[TARGET]

    results = []

    # ---- Baseline: mean predictor ----
    dummy = DummyRegressor(strategy="mean").fit(Xtr, ytr)
    results.append(evaluate("Baseline (mean)", yte, dummy.predict(Xte)))

    # ---- Linear Regression ----
    lr = LinearRegression().fit(Xtr, ytr)
    pred_lr = lr.predict(Xte)
    results.append(evaluate("Linear Regression", yte, pred_lr))

    # ---- Random Forest ----
    rf = RandomForestRegressor(n_estimators=200, max_depth=12, random_state=RANDOM_STATE, n_jobs=-1)
    rf.fit(Xtr, ytr)
    pred_rf = rf.predict(Xte)
    results.append(evaluate("Random Forest", yte, pred_rf))

    # ---- Gradient Boosting ----
    gb = GradientBoostingRegressor(n_estimators=200, max_depth=3, learning_rate=0.1, random_state=RANDOM_STATE)
    gb.fit(Xtr, ytr)
    pred_gb = gb.predict(Xte)
    results.append(evaluate("Gradient Boosting", yte, pred_gb))

    # ---- XGBoost (if available) ----
    xgb_model = None
    try:
        from xgboost import XGBRegressor
        xgb_model = XGBRegressor(n_estimators=300, max_depth=5, learning_rate=0.05,
                                  subsample=0.8, colsample_bytree=0.8, random_state=RANDOM_STATE,
                                  n_jobs=-1)
        xgb_model.fit(Xtr, ytr)
        pred_xgb = xgb_model.predict(Xte)
        results.append(evaluate("XGBoost", yte, pred_xgb))
    except ImportError:
        print("xgboost not available, skipping.")

    res_df = pd.DataFrame(results)
    res_df.to_csv(TABLES / "task16_model_comparison.csv", index=False)
    print("\n=== MODEL COMPARISON (test = 2025, held out) ===")
    print(res_df.round(4).to_string(index=False))

    best_name = res_df.loc[res_df["RMSE"].idxmin(), "Model"]
    print(f"\nBest model by RMSE: {best_name}")

    # ---- Hyperparameter tuning: Random Forest (best interpretable tree model) ----
    print("\n=== HYPERPARAMETER TUNING: Random Forest (RandomizedSearchCV, time-aware CV) ===")
    tscv = TimeSeriesSplit(n_splits=4)
    param_dist = {
        "n_estimators": [100, 200, 300],
        "max_depth": [6, 10, 14, None],
        "min_samples_leaf": [1, 5, 20],
        "max_features": ["sqrt", 0.7, 1.0],
    }
    search = RandomizedSearchCV(
        RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=-1),
        param_distributions=param_dist, n_iter=10, cv=tscv,
        scoring="neg_root_mean_squared_error", random_state=RANDOM_STATE, n_jobs=-1,
    )
    search.fit(Xtr, ytr)
    tuned_rf = search.best_estimator_
    pred_tuned = tuned_rf.predict(Xte)
    tuned_result = evaluate("Random Forest (tuned)", yte, pred_tuned)
    print(f"Best params: {search.best_params_}")
    print(f"Untuned RF test RMSE: {results[2]['RMSE']:.4f}")
    print(f"Tuned RF test RMSE:   {tuned_result['RMSE']:.4f}")

    tuning_summary = pd.DataFrame([
        {"stage": "baseline_untuned_rf", **{k: v for k, v in results[2].items() if k != "Model"}},
        {"stage": "tuned_rf", **{k: v for k, v in tuned_result.items() if k != "Model"}, "best_params": str(search.best_params_)},
    ])
    tuning_summary.to_csv(TABLES / "task17_tuning_summary.csv", index=False)

    # append tuned result to comparison table
    res_df = pd.concat([res_df, pd.DataFrame([tuned_result])], ignore_index=True)
    res_df.to_csv(TABLES / "task16_model_comparison.csv", index=False)

    # ---- Evaluation plots: actual vs predicted + residuals (best model) ----
    best_pred = {"Baseline (mean)": dummy.predict(Xte), "Linear Regression": pred_lr,
                 "Random Forest": pred_rf, "Gradient Boosting": pred_gb,
                 "Random Forest (tuned)": pred_tuned}
    if xgb_model is not None:
        best_pred["XGBoost"] = pred_xgb
    chosen_pred = best_pred[best_name] if best_name in best_pred else pred_tuned

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].scatter(yte, chosen_pred, alpha=0.05, s=4, color="#4C72B0")
    lims = [yte.min(), yte.max()]
    axes[0].plot(lims, lims, "r--")
    axes[0].set_xlabel("Actual temperature (deg C)"); axes[0].set_ylabel("Predicted temperature (deg C)")
    axes[0].set_title(f"Actual vs Predicted - {best_name} (test=2025)")

    resid = yte.values - chosen_pred
    axes[1].scatter(chosen_pred, resid, alpha=0.05, s=4, color="#DD8452")
    axes[1].axhline(0, color="r", linestyle="--")
    axes[1].set_xlabel("Predicted temperature (deg C)"); axes[1].set_ylabel("Residual (Actual - Predicted)")
    axes[1].set_title(f"Residuals - {best_name}")
    fig.tight_layout()
    fig.savefig(FIGURES / "22_ml_actual_vs_predicted.png")
    plt.close(fig)

    # Prediction error by location (does the model fail for particular sites?)
    err_by_loc = test.copy()
    err_by_loc["abs_error"] = np.abs(yte.values - chosen_pred)
    err_summary = err_by_loc.groupby("name")["abs_error"].mean().sort_values()
    err_summary.to_csv(TABLES / "task16_error_by_location.csv")
    print("\n=== MAE by location (test set, best model) ===")
    print(err_summary.round(3).to_string())

    # ---- Interpretability: feature importance / permutation importance ----
    model_for_interp = tuned_rf
    importances = pd.Series(model_for_interp.feature_importances_, index=FEATURES).sort_values(ascending=False)
    importances.to_csv(TABLES / "task18_feature_importance.csv")
    print("\n=== BUILT-IN FEATURE IMPORTANCE (tuned Random Forest) ===")
    print(importances.round(4).to_string())

    perm = permutation_importance(model_for_interp, Xte, yte, n_repeats=5, random_state=RANDOM_STATE, n_jobs=-1)
    perm_series = pd.Series(perm.importances_mean, index=FEATURES).sort_values(ascending=False)
    perm_series.to_csv(TABLES / "task18_permutation_importance.csv")
    print("\n=== PERMUTATION IMPORTANCE (test set, tuned Random Forest) ===")
    print(perm_series.round(4).to_string())

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    importances.plot(kind="barh", ax=axes[0], color="#4C72B0")
    axes[0].set_title("Built-in feature importance (RF)")
    axes[0].invert_yaxis()
    perm_series.plot(kind="barh", ax=axes[1], color="#55A868")
    axes[1].set_title("Permutation importance (test set)")
    axes[1].invert_yaxis()
    fig.tight_layout()
    fig.savefig(FIGURES / "23_feature_importance.png")
    plt.close(fig)

    # SHAP (sampled for speed)
    try:
        import shap
        sample = Xte.sample(min(2000, len(Xte)), random_state=RANDOM_STATE)
        explainer = shap.TreeExplainer(model_for_interp)
        shap_values = explainer.shap_values(sample)
        fig = plt.figure(figsize=(9, 6))
        shap.summary_plot(shap_values, sample, show=False)
        plt.tight_layout()
        plt.savefig(FIGURES / "24_shap_summary.png")
        plt.close(fig)
        mean_abs_shap = pd.Series(np.abs(shap_values).mean(axis=0), index=FEATURES).sort_values(ascending=False)
        mean_abs_shap.to_csv(TABLES / "task18_shap_mean_abs.csv")
        print("\n=== MEAN |SHAP VALUE| BY FEATURE ===")
        print(mean_abs_shap.round(4).to_string())
    except ImportError:
        print("shap not available, skipping SHAP analysis.")

    print("\nML pipeline complete.")


if __name__ == "__main__":
    main()
