# Geospatial Weather and Elevation Analysis — Sri Lanka, 2020–2025

**Option 5: Geospatial Weather and Elevation Analysis**
Big Data Analytics Group Project

All figures referenced (`reports/figures/NN_*.png`), tables (`reports/tables/taskN_*.csv`)
and the interactive map (`reports/maps/sri_lanka_weather_map.html`) are generated
by the scripts in `src/` — see `README.md` to reproduce every number in this
report from raw data. Nothing below is invented; every statistic is read
from a script's output.

---

## 1. Dataset Overview

The raw data (`data/raw/regional-2020-2025/raw/`) is Open-Meteo historical
weather (ERA5 reanalysis model, `era5_seamless`), Hive-partitioned by
`location_id=.../year=.../weather.parquet`, plus one `locations.parquet`
metadata table.

**What's actually on disk:** 35 `weather.parquet` files covering **6 Sri
Lankan locations** (Jaffna, Batticaloa, Trincomalee, Colombo, Matara, Galle)
across **2020–2025** — every year for every location except **Matara, which
is missing 2025** (the download was still in progress on that partition when
it stopped). All 35 files share **one identical schema**: 50 columns,
hourly resolution, UTC timestamps. Concatenated: **306,888 rows × 64
columns** (50 weather variables + partition/join columns).

**A critical provenance finding:** `locations.parquet` actually lists
**100 locations** across Sri Lanka, India, Nepal, Bhutan, Bangladesh,
Myanmar, Thailand, Vietnam, Laos, Cambodia, Malaysia, Indonesia and
Singapore — elevations from 3m to 4298m. `study-plan.json` confirms this was
a planned 100-location × 6-year × hourly study (**5,260,800 expected rows**,
600 planned "chunks"). `ingestion-status.json` shows the job was **paused
after only 35 of 600 chunks** ("Local 3600s quota budget reached"), and
`download.log` shows it was mid-download of `lk_matara / 2025` when it
stopped. What was actually collected is only the 6 Sri Lankan coastal cities
named in this project's brief — a **5.8% completion rate** against the
original plan. This is documented fully in Section 17 (Limitations).

Weather variables (via `_source.json`): temperature, apparent temperature,
dew point, humidity, precipitation/rain/snow, pressure (MSL + surface),
cloud cover (total/low/mid/high), wind (speed/direction at 10m & 100m,
gusts), soil temperature & moisture (4 depth bands), boundary layer height,
wet-bulb temperature, total column water vapour, sunshine duration, and 8
radiation variables. Units (from `_source.json`): °C, %, mm, hPa, m/s,
W/m². Model: `era5_seamless` — a **reanalysis product on a coarse grid
(~9–31km)**, not station observations; "elevation" is the model's grid-cell
orography, not a precise ground survey value (relevant to Section 7/8).

## 2. Data Quality Report

- **Schema consistency:** all 35 files identical (verified programmatically,
  `src/inspect_dataset.py`) — no schema drift across locations or years.
- **Missing values:** only 2 of 50 weather columns have any: `boundary_layer_height`
  and `total_column_integrated_water_vapour`, each **8.54% missing overall**
  (26,208 of 306,888 rows). Root cause isolated: **100% of this gap falls in
  2024** (49.7% of 2024's rows, concentrated Jan–Jun), affecting all 6
  locations similarly — an upstream ERA5-product gap for that field in that
  period, not a processing bug. All other 48 columns: **0% missing**.
- **Duplicates:** **0** exact duplicate rows; **0** duplicate
  `(location_id, timestamp)` rows.
- **Plausibility checks** (generous physical bounds, e.g. temperature
  [-10, 55]°C, wind [0, 60] m/s, pressure [870, 1085] hPa, humidity/cloud
  [0, 100]%, valid lat/lon/elevation): **0 invalid values on any of the 15
  checked variables.**
- **Genuine extremes, not errors:** the 10 highest temperatures (36.9–37.3°C,
  all Batticaloa, clustered on 2023-08-03, 2024-07-21, 2020-06-15) coincide
  with documented Sri Lankan heatwave conditions and carry low-to-moderate
  humidity (31–37%), physically consistent with a real heat event, not a
  sensor fault. The highest wind speeds (13.6–15.0 m/s, gusts to 21.9 m/s) are
  concentrated on **27–28 November 2025 at Jaffna/Trincomalee**, coinciding
  with a real tropical cyclone affecting Sri Lanka's east coast that week —
  again a genuine extreme, kept in the data. The highest precipitation hours
  (17.9–26.4 mm/hr) all occur under 100% cloud cover, consistent with
  monsoon downpours. **No values were removed.**
- **Snow variables** (`snowfall`, `snow_depth`) are always exactly 0 across
  all 306,888 rows — expected and correct for a tropical climate, not a data
  quality issue.

## 3. Data Preprocessing

`src/build_analytical_dataset.py`: locations.parquet filtered to the 6
locations with downloaded weather data → left-joined onto the concatenated
weather data on `location_id` (`validate="many_to_one"`).

**Merge verification:** rows before = **306,888**, rows after = **306,888**,
rows lost = **0**, duplicate `(location_id, timestamp)` after merge = **0**,
unmatched rows (no location metadata) = **0**. The merge is exact — every
weather row found its location, no fan-out, no loss.

Derived columns added: `date`, `year`, `month`, `day`, `hour`, and `season`
(Sri Lanka's four monsoon regimes: Northeast Monsoon Dec–Feb, First
Inter-monsoon Mar–Apr, Southwest Monsoon May–Sep, Second Inter-monsoon
Oct–Nov). Raw data under `data/raw/` is never modified; all derived output
goes to `data/processed/analytical_dataset.parquet`.

## 4. Exploratory Data Analysis

**Overall statistics** (n=306,888 hourly obs, `reports/tables/task6_overall_summary_stats.csv`,
figures `01_overall_distributions_hist.png`, `02_overall_boxplots_zscored.png`):

| Variable | Mean | Std | Min | Median | Max | Skew |
|---|--:|--:|--:|--:|--:|--:|
| Temperature (°C) | 27.35 | 2.16 | 19.2 | 27.0 | 37.3 | 0.87 |
| Apparent temp (°C) | 31.44 | 2.63 | 16.4 | 31.2 | 43.9 | 0.49 |
| Precipitation (mm/hr) | 0.24 | 0.73 | 0.0 | 0.0 | 26.4 | **8.03** |
| Wind speed (m/s) | 3.59 | 2.21 | 0.0 | 3.21 | 15.0 | 0.78 |
| Relative humidity (%) | 80.1 | 11.1 | 27 | 82 | 99 | -1.06 |
| Pressure MSL (hPa) | 1009.6 | 2.4 | 999.4 | 1009.7 | 1019.1 | -0.11 |
| Cloud cover (%) | 72.2 | 31.6 | 0 | 88 | 100 | -0.84 |

Precipitation is heavily right-skewed / zero-inflated (skew=8.03, median=0)
— physically expected for hourly rainfall in any climate. Humidity and
cloud cover are left-skewed (bounded near their 100% ceiling), reflecting
Sri Lanka's persistently humid, cloudy tropical climate.

**Temporal patterns** (figures `03`–`06`, `18`): monthly temperature shows a
clear bimodal seasonal cycle distinct by location (heatmap `08`): the three
dry-zone/east-coast sites (Jaffna, Trincomalee, Batticaloa) peak in
**Jun–Jul** (~29–30°C), while the three wet-zone/south-west sites (Colombo,
Matara, Galle) peak earlier in **Mar–Apr** (~28°C) and are markedly cooler
by mid-year. Mean weather by monsoon season
(`reports/tables/task6_season_summary.csv`):

| Season | Mean Temp (°C) | Mean Precip (mm/hr) | Mean Wind (m/s) |
|---|--:|--:|--:|
| Southwest Monsoon (May–Sep) | 28.05 | 0.20 | 4.44 |
| First Inter-monsoon (Mar–Apr) | 27.86 | 0.14 | 2.55 |
| Second Inter-monsoon (Oct–Nov) | 26.67 | **0.45** | 3.14 |
| Northeast Monsoon (Dec–Feb) | 26.27 | 0.21 | 3.15 |

Wind is strongest during the Southwest Monsoon (as expected), and rainfall
peaks in the Second Inter-monsoon — consistent with Sri Lanka's known
climatology.

**Location comparison** (figure `07`, table `task6_location_summary.csv`):
Jaffna is both the hottest (27.84°C mean) and by far the windiest (5.90 m/s
mean — over 2× every other location, reflecting its exposed northern
peninsula setting), and driest/least humid (78.1%). Galle and Matara are the
coolest (~26.8°C), wettest (rainfall ≈2,770mm and 1,857mm/year respectively)
and most humid (~84%). **Location, not elevation, is clearly the dominant
driver of variation** — see Sections 6–9.

## 5. Temporal Analysis

Annual mean temperature (`03_annual_temperature_trend.png`,
`task6_annual_temperature_by_location.csv`) shows year-to-year fluctuation
(≈26–28.5°C) with **no strong monotonic 2020–2025 trend** — six years is too
short a window to separate genuine climate trend from natural
inter-annual variability at this precision. The **temperature ranking of
locations is largely stable across years** (`12_temperature_rank_stability.png`,
`task7_temperature_rank_by_year.csv`): Jaffna is ranked hottest or
second-hottest in every year 2020–2025, Galle is ranked coolest or
second-coolest in 5 of 6 years — geography's relative ordering persists even
as absolute yearly temperatures fluctuate.

## 6. Geospatial Analysis

(figures `10`–`12`, table `task7_location_aggregates.csv`)

- **A. Temperature vs geography:** ranges 26.82°C (Galle, southwest) to
  27.84°C (Jaffna, north) — a modest but consistent **north–south gradient**
  (warmer toward Jaffna in the dry north, cooler toward the wet southwest).
- **B. Rainfall vs geography:** strongly differentiates by coast — the
  southwest coast (Galle 2,771mm/yr, Colombo 2,728mm/yr) receives **~1.7–1.8×**
  the annual rainfall of the northeast (Jaffna 1,503mm/yr, Trincomalee
  1,556mm/yr) — Sri Lanka's classic wet-zone/dry-zone contrast, driven by
  monsoon orientation, not visible from a simple lat/lon scatter alone but
  clearly present location-to-location.
- **C. Wind speed vs geography:** the most dramatic geographic effect in the
  whole dataset — Jaffna (5.90 m/s) is **2.4× windier than Batticaloa**
  (2.46 m/s) and roughly double most other sites, consistent with its
  exposed low-relief peninsula with minimal terrain/vegetation wind
  shielding compared to the more sheltered southern coast.
- **D. Consistency across years:** temperature's location ranking is stable
  (Section 5). All 6 locations are shown together with real observed values
  on the interactive map `reports/maps/sri_lanka_weather_map.html` (Folium;
  marker size/color = mean temperature, click for full stats) — no spatial
  interpolation/kriging was applied between the 6 points, since that would
  fabricate structure between sparse, non-adjacent stations.

## 7. Elevation Analysis — Core Research Question

**This is the project's central question, and it comes with a fundamental
data limitation that must be stated plainly before any results: the 6 study
locations span elevation 3m–10m only** (Galle 3m, Matara 6m, Colombo/Jaffna/
Trincomalee 9m, Batticaloa 10m — 3 locations share an *identical* 9.0m ERA5
grid-cell elevation). A 7-metre span across 6 points is **not sufficient to
detect a real orographic/lapse-rate effect**; the standard moist-adiabatic
lapse rate (~5–6°C/km) predicts under 0.05°C of temperature difference
across this entire range — smaller than ERA5's own measurement noise. Per
the task brief's own instruction ("if the six locations do not provide
enough elevation variation to justify grouping, explicitly say so"), **this
section reports the numbers honestly, but they should not be read as
evidence about real elevation effects.**

**Elevation correlations, location-level (n=6)** (`13`–`17`, `task8_elevation_correlations.csv`):

| Variable | Pearson r | p | Spearman ρ | p |
|---|--:|--:|--:|--:|
| Temperature | 0.72 | 0.106 | 0.82 | **0.046** |
| Rainfall | -0.57 | 0.240 | -0.58 | 0.231 |
| Wind speed | 0.22 | 0.679 | -0.15 | 0.774 |
| Humidity | -0.74 | 0.091 | -0.82 | **0.046** |
| Pressure | -0.79 | 0.060 | -0.70 | 0.123 |

**Decisive evidence that this is confounding, not a real elevation effect:**
the elevation–temperature correlation, recomputed **month by month**
(`task8_elevation_temp_corr_by_month.csv`, figure `18`), **flips sign**
across the year — from **r = -0.80 in December** to **r = +0.69 in
July/August**. A genuine physical lapse-rate effect would not reverse
direction seasonally; this pattern is the signature of elevation happening
to correlate, at these 6 specific points, with an unrelated variable
(latitude / monsoon exposure) whose own relationship with temperature
*does* flip seasonally. Section 8's regression makes this explicit: once
latitude and longitude are controlled for, elevation's apparent effect on
temperature **disappears entirely** (coefficient drops from 0.139 to
-0.005, p rises from 0.0003 to 0.57).

Rainfall and pressure show the strongest raw elevation correlations
(r = -0.57 to -0.79) but **none reach conventional significance at n=6**
(all p > 0.05, Pearson); only the Spearman rank correlations for
temperature and humidity cross p<0.05, and with only 6 tied ranks those
should be treated as weak, exploratory-only evidence, not confirmed
findings (Section 9, H3–H5 formalize this with hypothesis tests).

## 8. Elevation Grouping

**No elevation groups (low/medium/high) were created.** Elevation values
present are {3, 6, 9, 9, 9, 10} metres — a 7m band with 4 distinct values,
none of it constituting a real climatological threshold (no boundary-layer
transition, no orographic lifting occurs over single-digit metres). Per the
brief's explicit instruction for this scenario, continuous elevation (and,
far more informatively, latitude/coastal exposure — Section 6) is used
throughout instead of an arbitrary tertile split that would carry no
physical meaning. (`src/elevation_analysis.py` implements a tertile-grouping
path automatically for whenever elevation range exceeds 100m — e.g. if the
optional highland-location extension in Section 17 is run — so this
becomes a real analysis, not just a placeholder, the moment better data
exists.)

## 9. Correlation Analysis

(figure `20`, tables `task10_*`)

**Row-level (n=306,888) vs location-level (n=6) correlations diverge
sharply for geography variables — and the divergence itself is the
finding.** Row-level p-values for elevation/lat/lon are all `p≈0.0`, because
each of the 6 distinct geography values is repeated ~50,000 times — this
inflates statistical "significance" without adding real independent
information about the geography effect. The honest sample size for a
between-location geographic relationship is **6**, not 306,888
(`reports/tables/task10_location_level_correlations.csv` reports both, side
by side, for exactly this reason).

Strongest, most meaningful relationships found:

- **Humidity ↔ Temperature: r = -0.84 (Pearson, row-level)** — by far the
  strongest pairwise relationship in the dataset; physically expected
  (moisture holding capacity rises with temperature; also both are driven
  by the same convective/monsoon cycle).
- **Latitude ↔ Wind speed: r = 0.45 (row-level), r = 0.76 (location-level)**
  — the clearest true geographic signal: Jaffna's northern, low-relief,
  more exposed peninsula setting drives materially higher wind.
- **Latitude ↔ Temperature: r = 0.89 (location-level, p = 0.018)** —
  statistically significant even at n=6, and the strongest single
  geographic predictor of temperature in this dataset (stronger than
  elevation).
- **Pressure MSL ↔ Surface pressure: r = 0.99** — expected near-identity at
  sea level.
- **Elevation ↔ Pressure: r = -0.79 (location-level)** — physically correct
  direction (pressure falls with altitude) but, again, only a 7m/9hPa-scale
  signal, not a robust altitude effect.

## 10. Statistical Testing

(full detail in `src/stat_tests.py` output and `reports/tables/task11_hypothesis_test_results.csv`;
each test states H0/H1, checks assumptions, and reports the test statistic, p-value and practical meaning)

| # | Question | Test (assumption-driven) | Statistic | p-value | Conclusion |
|---|---|---|--:|--:|---|
| H1 | Does mean temperature differ between the 6 locations? | Kruskal-Wallis (daily means; Shapiro-Wilk rejected normality for all 6, Levene rejected equal variances) | 1204.5 | 3.1×10⁻²⁵⁸ | **Reject H0** |
| H2 | Does rainfall differ between locations? | Kruskal-Wallis (rainfall is zero-inflated/right-skewed by nature) | 1506.5 | ≈0 | **Reject H0** |
| H3 | Elevation ↔ temperature relationship? | Pearson (location-level, n=6) | r=0.72 | 0.106 | **Fail to reject H0** |
| H4 | Elevation ↔ rainfall relationship? | Pearson (location-level, n=6) | r=-0.65 | 0.164 | **Fail to reject H0** |
| H5 | Elevation ↔ wind relationship? | Pearson (location-level, n=6) | r=0.22 | 0.679 | **Fail to reject H0** |
| H6 (added) | Latitude ↔ temperature relationship? | Pearson (location-level, n=6) | r=0.89 | 0.018 | **Reject H0** |

**H1/H2** are unambiguous: with hundreds of daily observations per location,
there is overwhelming evidence that both temperature and rainfall
distributions genuinely differ by location — but a significant
Kruskal-Wallis result says only that *some* difference exists, not that
elevation drives it (location differences are consistent with the
latitude/coastal-exposure story in Sections 6–9, not elevation).

**H3–H5** all fail to reject H0 at n=6 — consistent with, and reinforcing,
the "insufficient elevation variation" conclusion from Section 7. H6 was
added because the EDA/correlation work flagged latitude, not elevation, as
the strongest and only n=6-significant geographic predictor of temperature
— a case of letting the data redirect the hypothesis, rather than forcing a
test the data couldn't support.

## 11. Regression Analysis

(`src/regression.py`; OLS with **cluster-robust standard errors by
location_id** — essential here, since elevation/latitude/longitude are
literally constant within a location and repeated across ~51,000 hourly
rows each; ordinary SEs would treat those as independent draws when the real
independent sample size for a geography effect is 6, producing spuriously
tiny p-values. Full output in `reports/tables/task12_*`.)

| Model | R² | Elevation coef. | Elevation p-value (clustered) |
|---|--:|--:|--:|
| 1: Temperature ~ Elevation | 0.025 | **+0.139** °C/m | **0.0003** |
| 2: + Latitude + Longitude | 0.048 | -0.005 °C/m | 0.572 |
| 3: + Month + Year | 0.203 | -0.005 °C/m | 0.600 |

**This is the clearest demonstration of confounding in the whole project.**
Model 1 alone would suggest a strong, "significant" positive elevation
effect (+0.14°C per metre — an absurdly large lapse rate if taken
literally, ~140°C/km against a true ~5.5°C/km). The moment latitude and
longitude are added (Model 2), elevation's coefficient **collapses to
essentially zero and loses all significance** (p: 0.0003 → 0.572), while
latitude (+0.30°C/degree, p<0.001) and longitude (+0.33°C/degree, p<0.001)
become the dominant, robust predictors. Elevation in Model 1 was acting as
a proxy for location identity, not a real physical driver. Model 3 adds
month and year (deliberately excluding contemporaneous weather variables
like humidity/pressure/wind — see script docstring for the reasoning: including
them would test "does weather predict weather," a different and circular
question from the geography question this model answers) and reaches
**R²=0.203** — geography + season jointly explain about a fifth of
hourly temperature variance, with month dummies (Sri Lanka's seasonal
cycle) contributing most of that gain.

## 12. Machine Learning

**Target selection (temperature_2m):** rainfall was rejected as the primary
target because it is ~85% zero-valued at hourly resolution (Section 4) — a
regression model would be dominated by trivially predicting zero rather
than testing the geography question. Wind speed was rejected because ERA5's
coarse grid can't resolve the very local turbulence effects that drive
short-term wind variability. Temperature is continuous, well-behaved
(skew=0.87), and Section 11 already established that geography+season
explain a genuine, non-trivial share of its variance — the most defensible
target for testing whether geography/elevation predict weather.

**Leakage screening:** predictors restricted to **elevation, latitude,
longitude, month (sin/cos encoded), hour (sin/cos encoded), year** —
geography + time only. Excluded as leakage: `apparent_temperature`,
`wet_bulb_temperature_2m`, `dew_point_2m`, `vapour_pressure_deficit` (each
computed from temperature via near-deterministic thermodynamic formulae)
and near-surface `soil_temperature_*` (tightly thermally coupled to air
temperature). All *other* contemporaneous weather variables (humidity,
pressure, wind, cloud cover, precipitation) were also excluded — not
because they leak, but to keep this model answering the same geography
question as the regression in Section 11, rather than a different weather-
nowcasting question.

**Time-based split** (not random): train = 2020–2024 (263,088 rows), test =
2025 (43,800 rows) — testing genuine forward generalization, the
appropriate strategy for 6 years of sequential data. (Note: Matara has no
2025 data, so it is absent from the test set entirely — see Section 17.)

**Model comparison** (`reports/tables/task16_model_comparison.csv`, figure `22`):

| Model | MAE | RMSE | R² |
|---|--:|--:|--:|
| Baseline (mean) | 1.798 | 2.322 | -0.003 |
| Linear Regression | 1.116 | 1.465 | 0.601 |
| Random Forest | 0.860 | 1.122 | 0.766 |
| Gradient Boosting | 0.888 | 1.155 | 0.752 |
| XGBoost | 0.854 | 1.116 | 0.768 |
| **Random Forest (tuned)** | — | **1.095** | — |

XGBoost and tuned Random Forest are the strongest models (RMSE≈1.10–1.12°C,
R²≈0.77) — a substantial, meaningful improvement over both the baseline
(RMSE 2.32) and plain linear regression (RMSE 1.46), showing the true
geography/time → temperature relationship is real but non-linear (tree
models capture interactions and seasonal curvature linear regression
cannot). Error is not uniform across locations
(`task16_error_by_location.csv`): Galle and Jaffna are predicted most
accurately (MAE 0.75–0.77°C), Batticaloa least accurately (MAE 0.98°C).

## 13. Hyperparameter Tuning

Random Forest tuned via `RandomizedSearchCV` (10 iterations) with
**`TimeSeriesSplit` (4 folds)** — not a plain k-fold — since standard random
CV would leak future information into validation folds for sequential
weather data. Search space: `n_estimators` {100,200,300}, `max_depth`
{6,10,14,None}, `min_samples_leaf` {1,5,20}, `max_features`
{sqrt, 0.7, 1.0} (kept intentionally small — not an exhaustive grid).
Best parameters: `n_estimators=100, max_depth=10, min_samples_leaf=5,
max_features='sqrt'`. Test RMSE improved from **1.122 (untuned) to
1.095 (tuned)** — a modest (~2.5%) but consistent gain; the untuned default
was already reasonably well-specified for this feature set, so tuning
mainly reduced overfitting via the shallower `max_depth`/higher
`min_samples_leaf`.

## 14. Model Interpretability

(figure `23`, tables `task18_feature_importance.csv`, `task18_permutation_importance.csv`,
`task18_shap_mean_abs.csv`; SHAP summary `24_shap_summary.png`)

Built-in and permutation importance agree closely: **time-of-day (`hour_sin`/`hour_cos`)
and month dominate** (combined ≈70–90% of importance), with geography
(latitude, longitude, elevation) a distinctly secondary contributor.
**Elevation is consistently the least important feature of the eight**
(built-in importance 0.019, permutation importance 0.021) — the ML model
independently arrives at the same conclusion as the EDA, correlation,
statistical tests and regression: **elevation carries almost no usable
signal for predicting temperature in this 6-location, 3–10m-elevation
dataset**, while latitude is a consistently more useful (if still
secondary-to-time) geographic predictor. This is the clearest possible
agreement between five independent methods.

## 15. Big Data / PySpark Analysis

(`src/big_data_profile.py`, `src/pyspark_demo.py`; table `task5_scale_profile.csv`, `task21_*`)

**Honest volume assessment: this is not big data.** 306,888 rows, 20.3MB raw
Parquet, ~177MB as an in-memory pandas DataFrame — every analysis above ran
in seconds on a single machine. Claiming otherwise would misrepresent the
dataset. What genuinely reflects big-data engineering practice:

1. **Hive-style partitioning** (`location_id=.../year=...`) — enables
   partition pruning (verified in the PySpark demo: filtering to one
   location+year reads only that directory) and safe, idempotent, parallel
   per-partition appends without touching existing files.
2. **Columnar Parquet** (~65.6 bytes/row compressed) — efficient for this
   wide (50-variable), mostly-numeric schema, directly readable by pandas
   *and* Spark with zero conversion.
3. **Scale trajectory:** `study-plan.json` shows the *originally planned*
   ingestion (100 locations × 6yr × hourly = 5.26M rows) is ~17× larger than
   what was collected, and a global multi-country expansion of this exact
   pipeline would cross into a regime where distributed processing is
   genuinely justified.

`src/pyspark_demo.py` runs the same load → filter → group-by-location/year
→ aggregate → join-with-location-metadata pipeline in Spark against the
identical partitioned files (results in `task21_pyspark_*.csv`, matching the
pandas results exactly) — proving the partitioning design choice already
scales without a pipeline rewrite, even though Spark isn't *necessary* at
the current size. (Getting PySpark running required a separate clean
virtualenv — a `setuptools`/`distutils` incompatibility blocked a direct
install in this sandbox; documented in `README.md`.)

**Pandas vs PySpark, concretely for this project:** at 300K rows, pandas
wins on every practical axis (sub-second ops, no JVM startup, direct
compatibility with seaborn/scipy/statsmodels/sklearn/shap). Spark's
advantages — partition pruning, Catalyst query optimization, distributed
shuffle — only pay off past roughly tens of millions of rows or multi-GB, or
under continuous multi-partition ingestion load.

## 16. Research Questions and Answers

1. **How does temperature vary geographically across the 6 locations?**
   Modestly, with a real north–south (latitude) gradient (r=0.89, p=0.018)
   — Jaffna (north, dry zone) is consistently the hottest, Galle/Matara
   (southwest, wet zone) the coolest, a pattern stable across all 6 years.

2. **How does rainfall vary geographically and with elevation?**
   Strongly by coast/monsoon exposure (southwest coast receives ~1.7–1.8×
   the rainfall of the northeast), but its relationship with elevation is
   **not statistically supported** at n=6 (H4: p=0.164).

3. **Do weather conditions differ significantly among the six locations?**
   Yes, decisively for both temperature and rainfall (H1, H2: both
   p≈0 via Kruskal-Wallis) — but Sections 7–9 & 11 show this is driven by
   latitude/coastal exposure, not elevation.

4. **Do elevation, latitude and longitude explain temperature variation?**
   Latitude and longitude do (Model 2/3 R²=0.05–0.20, both highly
   significant); **elevation does not** — its apparent Model-1 effect
   vanishes once latitude/longitude are controlled for (Section 11), and
   this is independently confirmed by the ML feature importances (Section 14).

5. **Can geographical and temporal variables predict temperature?**
   Yes, meaningfully: tuned models reach R²≈0.77 (RMSE≈1.10°C) against a
   test-set baseline RMSE of 2.32°C — but the predictive power comes
   overwhelmingly from **time** (hour-of-day, month), with geography a
   secondary contributor and elevation specifically contributing almost
   nothing (Section 14).

## 17. Limitations

**1. Only 6 locations, all coastal lowland.** This is the project's
central constraint, discussed throughout. n=6 gives very low statistical
power for any location-level test (Sections 9–11); elevation spans only
3–10m, physically too narrow to detect a real lapse-rate effect at any
plausible magnitude. Every elevation finding in this report should be read
as "not detectable in this sample," not "no elevation effect exists in
reality."

**2. Elevation-location confounding is demonstrated, not just possible.**
Section 11's regression is the clearest evidence: elevation's raw
correlation with temperature is an artifact of which locations happen to
share which elevations, not a physical effect — it disappears completely
once latitude/longitude are controlled for.

**3. Geographic generalization is essentially untested.** 6 points spanning
~7,900 km² of one country cannot support claims about weather-elevation
relationships elsewhere; results describe these 6 Sri Lankan coastal cities
only.

**4. Temporal confounds are real and only partially controllable.** Six
years is too short to separate genuine trend from natural inter-annual
variability (Section 5); month/season is controlled for in the regression
and ML models specifically to avoid conflating seasonal weather with
geographic weather.

**5. API/data-collection limitations** (from `_source.json`,
`ingestion-status.json`, `study-plan.json`):
   - Source is **ERA5 reanalysis** (a coarse, ~9–31km-grid physical model
     reanalysis), not ground station observations — "elevation" is model
     grid orography, explaining why 3 of 6 locations share an identical
     9.0m value despite being real, physically distinct towns.
   - The ingestion job was **paused after 35 of 600 planned chunks**
     (5.8%) due to a local API-quota budget, truncating what was designed
     as a 100-location, multi-country regional study down to 6 Sri Lankan
     locations, and leaving **Matara's 2025 partition incomplete/missing**
     entirely (visible in the ML test-set: Matara has no 2025 rows and is
     absent from the location-level test-set error table in Section 12).
   - `boundary_layer_height` / `total_column_integrated_water_vapour` have
     an 8.54% gap concentrated entirely in Jan–Jun 2024 — an upstream
     product gap, not something this project's processing caused or can
     fill.
   - Cluster-robust standard errors (Section 11) are the correct tool for
     n=6 clusters in principle, but are asymptotically justified for
     dozens of clusters, not 6 — treat all regression/correlation p-values
     in this report as indicative, not exact.

**What would fix this:** `src/fetch_additional_locations.py` (written but
not run — this session had no outbound network access to Open-Meteo) would
add 6 more Sri Lankan locations already catalogued in `locations.parquet`,
spanning 90m–2130m, giving the elevation analysis genuine range to work
with. See `README.md`.

## 18. Key Findings

1. **Elevation has no detectable effect on temperature, rainfall, or wind
   in this dataset** — the 3–10m range among the 6 study locations is
   physically too narrow, and the one apparently "significant" raw
   correlation (elevation→temperature, Model 1) is fully explained away by
   latitude/longitude (Model 2), independently confirmed by ML feature
   importance ranking elevation last of 8 features.
2. **Latitude is the strongest geographic predictor found** — location-level
   r=0.89 (p=0.018) with temperature, and the dominant term in every
   regression model that includes it.
3. **Geography is real but secondary to season/time-of-day** — the tuned
   ML model's own feature importances put hour-of-day and month far above
   any geographic variable (≈70–90% vs ≈10–30% of total importance).
4. **Sri Lanka's wet-zone/dry-zone contrast is the strongest spatial
   pattern in the data** — Galle/Colombo receive ~1.7–1.8× the annual
   rainfall of Jaffna/Trincomalee, and this dominates the "location differs
   significantly" result (H1/H2) far more than elevation does.
5. **Jaffna is a genuine wind outlier** (5.90 m/s mean, 2.4× the lowest
   location) — the single largest, most robust location effect found in
   the entire analysis, plausibly tied to its exposed low-relief peninsula
   geography.
6. **The data quality is excellent** — zero invalid values across 15
   plausibility checks, zero duplicates, and the only missingness (8.54% on
   2 of 50 columns) is fully explained and isolated to a known 2024 gap.
7. **Geography + time jointly predict temperature well** (ML R²≈0.77,
   RMSE≈1.10°C vs a 2.32°C baseline) even though elevation specifically
   contributes almost nothing to that predictive power.
8. **The dataset is a truncated 5.8% fragment of a much larger planned
   study** — a provenance fact that materially shapes every limitation
   above and should be disclosed in any downstream use of this data.

## 19. Recommended Visualizations

Selected for actual demonstrated value (not all candidates included):

| # | Visualization | Question answered | Deliverable |
|---|---|---|---|
| 1 | Interactive Folium map (`maps/sri_lanka_weather_map.html`) | Where are the 6 locations, and how do their key stats compare at a glance? | Dashboard, Presentation |
| 2 | Geospatial bubble maps, fig `10` | How do temp/rain/wind vary spatially? (Q A/B/C) | Report, Presentation |
| 3 | Monthly temp × location heatmap, fig `08` | Which locations run hottest, and when? | Report, Dashboard |
| 4 | Location boxplot comparison, fig `07` | Which locations differ, and by how much spread? | Report |
| 5 | Elevation vs Temperature scatter+OLS, fig `13` | The core research question, shown honestly (flat, n=6, caveated) | Report, Presentation |
| 6 | Correlation heatmap, fig `20` | What's related to what, across all variables at once? | Report |
| 7 | Regression comparison (Model 1→2→3 elevation coefficient collapse) | The confounding story, in one number | Presentation (as a table/annotated bar) |
| 8 | Monthly rainfall seasonality by location, fig `05` | When and where does the monsoon hit hardest? | Report, Dashboard |
| 9 | Temperature rank stability across years, fig `12` | Is the geographic pattern consistent over time? (Q D) | Report |
| 10 | Model comparison table + actual-vs-predicted, fig `22` | Can we predict temperature from geography+time, and how well? | Report, Presentation |
| 11 | Feature importance (built-in + permutation), fig `23` | What actually drives the ML model's predictions? | Report, Presentation |
| 12 | SHAP summary, fig `24` | Same question, with direction/magnitude per prediction | Report (technical appendix) |

Not recommended despite being in the original candidate list: a generic
"Sri Lanka location map" alone (superseded by the interactive Folium map,
which carries the same information plus real data) and elevation-group bar
charts (Section 8 — no defensible groups exist for the 6-location dataset).

## 20. Recommended Analytical Story

1. **Problem:** does geography — critically, elevation — shape weather in
   Sri Lanka, and can it help predict weather conditions?
2. **Data:** Open-Meteo/ERA5 historical weather + geocoded
   coordinates/elevation, 6 Sri Lankan coastal cities, 2020–2025, hourly.
3. **Data engineering:** Hive-partitioned Parquet by location/year; verified
   zero-loss, zero-duplicate merge with location metadata.
4. **EDA:** clear seasonal (monsoon) and location patterns; excellent data
   quality; genuine, explained extremes.
5. **Elevation analysis:** the honest headline finding — **no usable
   elevation signal**, because the 6 available locations span only 3–10m.
6. **Statistical evidence:** locations differ significantly overall (H1/H2);
   elevation relationships do not reach significance (H3–H5); latitude
   does (H6).
7. **Regression:** quantifies the confounding directly — elevation's
   apparent effect is fully absorbed by latitude/longitude.
8. **Machine learning:** geography+time predict temperature well
   (R²≈0.77), but elevation is the least useful of 8 features.
9. **Interpretability:** SHAP/importance independently corroborate the
   regression's conclusion — five separate methods (EDA, correlation,
   hypothesis tests, regression, ML) all converge on the same answer.
10. **Key findings:** see Section 18.
11. **Limitations:** 6 coastal-lowland locations, confounding, truncated
    5.8%-of-planned data collection (Section 17).
12. **Practical application:** a weather-elevation dashboard for these 6
    cities should lead with the wet-zone/dry-zone and time-of-day/seasonal
    story (where the real signal is), present elevation honestly as
    "insufficient data to assess" rather than a false pattern, and treat
    `fetch_additional_locations.py` as the clear next step for anyone
    wanting a genuine elevation analysis.
