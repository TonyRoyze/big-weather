"""Task 4: Data quality assessment.

Missingness (overall / by location / by year / by month), duplicates, and
plausibility checks on physical variables. Sri Lanka is tropical (never
snows), so snowfall/snow_depth are expected to be always ~0 - that is a
genuine physical fact, not a data quality problem, and is documented as such
rather than flagged as an error.
"""
import pandas as pd

from config import PROCESSED, TABLES

DF_PATH = PROCESSED / "analytical_dataset.parquet"

# Plausible physical ranges for a tropical coastal/lowland climate. These are
# generous physical bounds (not climatological averages) used only to catch
# genuine sensor/pipeline errors - not to strip legitimate extremes.
PLAUSIBLE_RANGES = {
    "temperature_2m": (-10, 55),       # deg C, global-safe bound
    "apparent_temperature": (-20, 65),
    "dew_point_2m": (-20, 35),
    "relative_humidity_2m": (0, 100),
    "precipitation": (0, 500),         # mm/hour; extreme tropical downpour ceiling
    "rain": (0, 500),
    "wind_speed_10m": (0, 60),         # m/s; ~216 km/h, well above cyclone-force gusts
    "wind_speed_100m": (0, 75),
    "wind_gusts_10m": (0, 90),
    "pressure_msl": (870, 1085),       # hPa; recorded global extremes
    "surface_pressure": (850, 1085),
    "cloud_cover": (0, 100),
    "latitude": (-90, 90),
    "longitude": (-180, 180),
    "elevation_m": (-430, 8849),       # Dead Sea to Everest
}


def main():
    df = pd.read_parquet(DF_PATH)
    n = len(df)

    # ---- Missingness overall ----
    miss = df.isna().sum().rename("missing_count").reset_index().rename(columns={"index": "column"})
    miss["missing_pct"] = (miss["missing_count"] / n * 100).round(3)
    miss = miss.sort_values("missing_pct", ascending=False)
    miss.to_csv(TABLES / "task4_missing_overall.csv", index=False)
    print("=== MISSING VALUES (columns with any missing) ===")
    print(miss[miss.missing_count > 0].to_string(index=False))

    # ---- Missingness by location / year / month ----
    key_vars = ["temperature_2m", "precipitation", "wind_speed_10m", "relative_humidity_2m",
                "pressure_msl", "boundary_layer_height", "total_column_integrated_water_vapour"]
    key_vars = [c for c in key_vars if c in df.columns]

    by_loc = df.groupby("location_id")[key_vars].apply(lambda g: g.isna().mean() * 100).round(2)
    by_loc.to_csv(TABLES / "task4_missing_by_location.csv")
    print("\n=== MISSING % BY LOCATION (key variables) ===")
    print(by_loc.to_string())

    by_year = df.groupby("year")[key_vars].apply(lambda g: g.isna().mean() * 100).round(2)
    by_year.to_csv(TABLES / "task4_missing_by_year.csv")
    print("\n=== MISSING % BY YEAR (key variables) ===")
    print(by_year.to_string())

    by_month = df.groupby("month")[key_vars].apply(lambda g: g.isna().mean() * 100).round(2)
    by_month.to_csv(TABLES / "task4_missing_by_month.csv")
    print("\n=== MISSING % BY MONTH (key variables) ===")
    print(by_month.to_string())

    # boundary_layer_height / total_column_integrated_water_vapour are 8.54% missing overall.
    # Check WHERE those gaps fall (which years) to explain the pattern.
    if "boundary_layer_height" in df.columns:
        blh_gap_by_year = df.groupby("year")["boundary_layer_height"].apply(lambda g: g.isna().sum())
        print("\nboundary_layer_height missing count by year:")
        print(blh_gap_by_year.to_string())

    # ---- Duplicates ----
    exact_dupes = df.duplicated().sum()
    key_dupes = df.duplicated(subset=["location_id", "timestamp"]).sum()
    print(f"\nExact duplicate rows: {exact_dupes}")
    print(f"Duplicate (location_id, timestamp) rows: {key_dupes}")

    # ---- Plausibility / invalid value checks ----
    print("\n=== PLAUSIBILITY CHECKS (values outside generous physical bounds) ===")
    invalid_rows = []
    for col, (lo, hi) in PLAUSIBLE_RANGES.items():
        if col not in df.columns:
            continue
        bad = df[(df[col] < lo) | (df[col] > hi)]
        invalid_rows.append({"column": col, "valid_range": f"[{lo}, {hi}]",
                              "n_invalid": len(bad), "pct_invalid": round(len(bad) / n * 100, 4)})
    invalid_df = pd.DataFrame(invalid_rows)
    invalid_df.to_csv(TABLES / "task4_plausibility_checks.csv", index=False)
    print(invalid_df.to_string(index=False))

    # ---- Invalid dates ----
    ts = pd.to_datetime(df["timestamp"])
    bad_dates = ((ts.dt.year < 2020) | (ts.dt.year > 2025)).sum()
    print(f"\nRows with timestamp outside expected 2020-2025 range: {bad_dates}")

    # ---- Extreme value inspection (genuine extremes vs errors) ----
    print("\n=== TOP 10 HIGHEST TEMPERATURE OBSERVATIONS (checked for plausibility, not removed) ===")
    top_temp = df.nlargest(10, "temperature_2m")[["location_id", "timestamp", "temperature_2m", "relative_humidity_2m"]]
    print(top_temp.to_string(index=False))

    print("\n=== TOP 10 HIGHEST PRECIPITATION OBSERVATIONS (checked for plausibility, not removed) ===")
    top_precip = df.nlargest(10, "precipitation")[["location_id", "timestamp", "precipitation", "cloud_cover"]]
    print(top_precip.to_string(index=False))

    print("\n=== TOP 10 HIGHEST WIND SPEED OBSERVATIONS ===")
    top_wind = df.nlargest(10, "wind_speed_10m")[["location_id", "timestamp", "wind_speed_10m", "wind_gusts_10m"]]
    print(top_wind.to_string(index=False))

    # Snow variables are structurally zero in a tropical climate - document, don't flag as error.
    print(f"\nsnowfall non-zero count: {(df['snowfall'] > 0).sum()} (expected 0 - tropical climate, no snow)")
    print(f"snow_depth non-zero count: {(df['snow_depth'] > 0).sum()} (expected 0 - tropical climate, no snow)")


if __name__ == "__main__":
    main()
