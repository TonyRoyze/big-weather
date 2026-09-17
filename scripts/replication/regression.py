"""Task 12: Regression modelling - quantifying geographical/elevation effects
on temperature.

Design choice: predictors are restricted to GEOGRAPHICAL and TEMPORAL
variables (elevation, latitude, longitude, month, year) - never
contemporaneous weather variables (humidity, pressure, wind, cloud cover).
Those weather variables are themselves consequences of the same underlying
geography/season, so including them as "predictors" of temperature would
blur the research question (does geography explain weather?) into a
different, more circular one (does weather explain weather?). That
predictive-power question is deliberately left to the ML section, which
handles it with explicit leakage screening.

Standard errors are cluster-robust by location_id: elevation/latitude/
longitude are literally constant within a location, repeated across ~51,000
hourly rows, so ordinary (non-clustered) SEs would treat 51,000 pseudo-
independent observations as if they were genuinely independent draws of the
geography effect, when the real independent sample size for a geography
effect is 6. Clustering fixes the SEs (and therefore the p-values) to
reflect that honestly; it does not change the point estimates.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt

from config import PROCESSED, TABLES, FIGURES

DF_PATH = PROCESSED / "analytical_dataset.parquet"


def load():
    df = pd.read_parquet(DF_PATH)
    df["month"] = pd.to_datetime(df["timestamp"]).dt.month
    df["year"] = pd.to_datetime(df["timestamp"]).dt.year
    return df


def fit_clustered(df, formula, label):
    model = smf.ols(formula, data=df)
    res = model.fit(cov_type="cluster", cov_kwds={"groups": df["location_id"]})
    print(f"\n{'='*90}\n{label}\nFormula: {formula}\n{'='*90}")
    print(res.summary())
    return res


def main():
    df = load()

    print("### MODEL 1: Temperature ~ Elevation ###")
    print("Justification: the project's core question - the simplest direct test of an "
          "elevation (lapse-rate) effect, with no other geographic confounders controlled for.")
    m1 = fit_clustered(df, "temperature_2m ~ elevation_m", "Model 1: Temperature ~ Elevation")

    print("\n### MODEL 2: Temperature ~ Elevation + Latitude + Longitude ###")
    print("Justification: elevation alone cannot be interpreted causally when it is confounded "
          "with location (Task 8 showed the elevation-temperature correlation flips sign "
          "seasonally, a classic confounding symptom). Adding latitude/longitude lets us see "
          "elevation's effect net of the north-south/east-west climatic gradient.")
    m2 = fit_clustered(df, "temperature_2m ~ elevation_m + latitude + longitude",
                        "Model 2: Temperature ~ Elevation + Latitude + Longitude")

    print("\n### MODEL 3: Temperature ~ Elevation + Latitude + Longitude + Month + Year ###")
    print("Justification: month captures Sri Lanka's monsoon-driven seasonal cycle and year "
          "captures any inter-annual trend/anomaly - both are legitimate geographic/temporal "
          "controls. Contemporaneous weather variables (humidity, pressure, wind, cloud cover) "
          "are deliberately EXCLUDED here: they are outcomes of the same weather system as "
          "temperature, not independent geographic explanators, and including them would answer "
          "a different, circular question ('does weather predict weather?') instead of the "
          "geography question this model is built to answer.")
    m3 = fit_clustered(df, "temperature_2m ~ elevation_m + latitude + longitude + C(month) + year",
                        "Model 3: + Month + Year")

    # Comparison table
    comparison = pd.DataFrame({
        "Model": ["1: Elevation only", "2: + Lat/Lon", "3: + Month + Year"],
        "R_squared": [m1.rsquared, m2.rsquared, m3.rsquared],
        "Adj_R_squared": [m1.rsquared_adj, m2.rsquared_adj, m3.rsquared_adj],
        "Elevation_coef": [m1.params.get("elevation_m"), m2.params.get("elevation_m"), m3.params.get("elevation_m")],
        "Elevation_p_value_clustered": [m1.pvalues.get("elevation_m"), m2.pvalues.get("elevation_m"),
                                         m3.pvalues.get("elevation_m")],
    })
    comparison.to_csv(TABLES / "task12_regression_comparison.csv", index=False)
    print("\n=== MODEL COMPARISON SUMMARY ===")
    print(comparison.round(5).to_string(index=False))

    # Save full coefficient tables
    for name, res in [("model1", m1), ("model2", m2), ("model3", m3)]:
        out = pd.DataFrame({"coef": res.params, "std_err": res.bse, "p_value": res.pvalues,
                             "ci_low": res.conf_int()[0], "ci_high": res.conf_int()[1]})
        out.to_csv(TABLES / f"task12_{name}_coefficients.csv")

    # Diagnostic plot: actual vs fitted for Model 3 (best-specified)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fitted = m3.fittedvalues
    resid = m3.resid
    axes[0].scatter(fitted, df["temperature_2m"], alpha=0.02, s=3)
    lims = [df["temperature_2m"].min(), df["temperature_2m"].max()]
    axes[0].plot(lims, lims, "r--")
    axes[0].set_xlabel("Fitted temperature"); axes[0].set_ylabel("Actual temperature")
    axes[0].set_title("Model 3: Actual vs Fitted")

    axes[1].scatter(fitted, resid, alpha=0.02, s=3)
    axes[1].axhline(0, color="r", linestyle="--")
    axes[1].set_xlabel("Fitted temperature"); axes[1].set_ylabel("Residual")
    axes[1].set_title("Model 3: Residuals vs Fitted")
    fig.tight_layout()
    fig.savefig(FIGURES / "21_regression_diagnostics_model3.png")
    plt.close(fig)

    print(f"\nModel 3 R^2 = {m3.rsquared:.4f} - geography+season explain "
          f"{m3.rsquared*100:.1f}% of hourly temperature variance across the 6 locations.")


if __name__ == "__main__":
    main()
