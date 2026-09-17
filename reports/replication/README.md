# Replication on the expanded local weather data

This analysis adapts the methods in
[KaumindiHerath/Big_Data_Geospatial_Project/src](https://github.com/KaumindiHerath/Big_Data_Geospatial_Project/tree/75aa5b3b00cbe3630833ad49902026171a054332/src)
at commit `75aa5b3b00cbe3630833ad49902026171a054332`.
Three unmodified reference modules are retained under `scripts/replication/`.
The runner directly reuses their feature preparation, evaluation metrics,
clustered-regression implementation and original quality-screen definitions.
Other aggregation and plotting steps are adapted to the expanded coverage.

## Reproduce

From the project root, use a separate analysis environment:

```bash
python3 -m venv .venv-analysis
.venv-analysis/bin/python -m pip install -r reports/replication/requirements-lock.txt
.venv-analysis/bin/python -u scripts/replicate_findings.py > reports/replication/run.log 2>&1
```

The data root defaults to `data/regional-2020-2025`; override with `--data-root`.
No source downloads are triggered and no ingestion files are modified.
`--resume-ml` reruns modelling from the saved panel if a model stage is interrupted.
The panel files are generated intermediates, excluded from git.

## Evidence and scope

- `manifest.json` records the reference commit, input fingerprint, source coverage,
  quality checks, reference file hashes and package versions.
- `tables/source_files.csv` lists every committed source file and its SHA-256 hash.
  Matching `_source*.json` commits are required. Uncommitted downloads are ignored.
- `tables/coverage.csv` records actual per-location date bounds and row counts.
- `panel.parquet` and `daily_panel.parquet` freeze the analysis window.
- `tables/` contains full-precision results; `figures/` contains regenerated plots.
- `ml_manifest.json` records training/test dates, sizes, features and tuning choices.
- `run.log` includes the fitted clustered regression summaries and execution progress.

The primary comparison uses the latest contiguous set of complete UTC days shared
by **all** locations. This avoids comparing six years at some locations with only
a few months at others. Temperature, rainfall, wind, humidity and MSL pressure
must have 24 valid hourly observations for a day to qualify. Duplicate hourly keys
stop the run. The code verifies source hashes again after reading and summarising.
Newly committed files after enumeration belong to a later snapshot.

## Changes from the reference

1. Both legacy annual and new weekly committed files are read. The original loader
   found only files literally called `weather.parquet`.
2. Results distinguish all 100 regional sites, the 30 Sri Lankan sites and the
   original six coastal sites. Country averages describe sampled locations only.
3. Temperature/dew-point and surface-pressure screening bounds allow high mountain
   conditions. Screening does not remove observations. Coast-only bounds would
   falsely flag valid Himalayan pressures. Original scope-specific assertions
   (e.g. snow must always be zero, years must end in 2025) are not reused.
4. Rainfall comparisons over the common window use daily totals and observed-period
   totals. They are never annualised. Historical annual comparisons require complete
   calendar years and are kept separate from the 2026 window.
5. Regressions retain the reference geographic covariates and location-clustered
   errors; constant year is omitted in the 2026-only panel. A country-fixed-effects
   sensitivity model is added. These are associations, not causal lapse rates.
6. August 2026 is held out; training uses earlier hours in the common window.
   Models use the reference eight geographic/time features and initial parameters.
   Year is constant here and cannot provide predictive variation.
7. Tuning retains the reference ten random parameter candidates and four expanding
   temporal folds, but uses 400 evenly spaced training timestamps (all 100 sites
   at each timestamp, 40,000 rows) to bound computation. Equal timestamps cannot
   straddle train/validation. The selected model is refitted on all training rows.
   Test results are not used to choose tuning parameters.
8. Permutation importance uses five repeats with a fixed 5,000-row test subsample;
   SHAP uses a fixed 2,000-row test subsample. Neither is causal evidence.
9. Kruskal–Wallis tests use daily site values. Their nominal p-values do not account
   for serial or spatial dependence; effect sizes and matched coverage take priority.
10. The old report's six-site conclusions, annual rainfall denominators and model
    metrics are not carried forward as results for the new sample. The new test
    assesses later dates at known sites, not unseen-location generalisation.

The supplied `docs/REPORT.md` remains the historical reference. The Findings
chapter in `docs/report/content.typ` and its figures are updated from this run.

## Verify the saved evidence

```bash
# Uses the project's existing PySpark environment and Java installation:
SPARK_LOCAL_IP=127.0.0.1 .venv/bin/python scripts/verify_replication_spark.py
# Checks input hashes, panel balance, correlations, regressions, split boundaries,
# model baseline, constant-feature importance, and the Spark reconciliation:
.venv-analysis/bin/python scripts/verify_replication.py
make report
```

The independent Spark check used PySpark 4.0.1. It creates a microsecond-timestamp
Parquet projection for Spark compatibility, then compares temperature/wind daily
means and precipitation totals against all 11,900 pandas location-day records.
`validation.json` and `spark_validation.json` record the checks and tolerances.

For the geographic scatterplots, each subplot has its own labelled latitude colour
scale. For permutation importance, baseline and permuted R² use the identical
fixed subsample; this ensures constant month/year features have exactly zero
importance in an August-only test set. SHAP values and permutation changes are not
causal effects, nor are permutation R² changes normalised percentages.

## Elevation relationships and feature importance

Run the supplementary analysis against the saved common-window panel:

```bash
.venv-analysis/bin/python scripts/analyze_elevation_relationships.py
```

This uses one observation per location (100 sites), with seven period-mean weather
features. Precipitation is expressed as mean daily total. Elevation is the target;
coordinates and country are not predictors. Five GroupKFold splits hold out whole
countries. A fixed random forest (300 trees, depth 6, minimum leaf size 2, seed 42)
is evaluated with and without surface pressure. There is no parameter search.
Held-out permutation importance uses 20 repeats per fold and the increase in MAE
in metres, weighted by test-site count. Error bars are weighted between-fold
standard deviations, not confidence intervals. These values are not percentages
or causal effects; downscaling and correlated features constrain interpretation.

`elevation_analysis.json` records the panel and script hashes, parameters and
checks. `tables/elevation_*` contains site summaries, correlations, country folds,
held-out predictions, scores and importance. `figures/elevation_*` contains the
six additional scatterplots and the two-panel importance comparison. The older
temperature-target model outputs are separate and are not used for these results.

## Monthly elevation tests

Run `python scripts/analyze_elevation_time_slices.py` in the analysis environment.
The frozen panel yields 400 balanced site-month summaries. Seven responses are
regressed on elevation (km), latitude, longitude, and country in each month, with
HC3 t-tests and Holm adjustment across 28 tests. The plotted 95% intervals are
pointwise, not multiplicity-adjusted. Precipitation is mean daily total.

Paired within-site changes from May are regressed on separate monthly elevation,
country, latitude and longitude terms. Joint Wald F-tests use site-clustered
covariance with finite-sample correction. The complete-month sensitivity uses
June as baseline. Holm adjustment covers all 14 interaction tests. Both analyses
also save country-clustered sensitivity p-values (13 clusters; exploratory).
No recurring seasonal cycle can be identified from this four-month window.

Outputs: `tables/elevation_monthly_sites.csv`, `elevation_monthly_tests.csv`,
`elevation_month_interactions.csv`, `figures/elevation_monthly_slopes.png`, and
`elevation_time_tests.json` (input/script hashes and method settings). The tests
check associations, not causation. Unequal geographic coverage, spatial dependence,
source downscaling and the partial May window constrain interpretation.

## Historical seasonality (2020–2025)

Run `python scripts/analyze_historical_seasonality.py` in the analysis environment.
It reads hash-verified frozen source files for the original six sites and checks
all 432 site-year-months for complete hourly coverage. No new ingestion is started.
For seven weather features at each site, monthly ranks are compared across six
years. Friedman Q and Kendall W describe calendar alignment; p-values come from
all 12^5 relative circular rotations of the annual rank sequences, fixing the
first year. This avoids the six-block asymptotic Friedman approximation and
preserves cyclic within-year order. It assumes independent years and uniform
cyclic phase under the null; actual cross-year dependence is not preserved.
Holm adjustment covers 42 tests. This establishes historical weather seasonality
under those assumptions, not seasonal elevation effects over a 3–10 m range.

Outputs: `historical_seasonality.json`, `tables/historical_monthly_sites.csv`,
`tables/historical_seasonality_tests.csv`, `tables/historical_monthly_climatology.csv`,
and `figures/historical_seasonal_cycles.png`.

## Same-month comparisons across years (revised question)

The requested comparison holds site and calendar month fixed while comparing
2020–2025, including within-month daily spread. It is separate from the earlier
calendar-phase seasonality test, which does not answer this question.

```bash
python scripts/compare_same_month_years.py
python scripts/check_matara_january.py
python scripts/plot_same_month_examples.py
```

The first script verifies frozen source hashes, produces complete daily means
(daily precipitation totals), excludes February 29, and compares six years within
each location/month/feature. ANOVA level and median-centred Brown–Forsythe spread
statistics use 4,999 matched-calendar-block permutations (seven-day blocks plus
a short tail). Spread permutations use median-centred residuals. Holm correction
is across the 24 tests per location-feature, not globally across the exploratory
scan. Blocks assume exchangeability under the null and do not preserve dependence
across boundaries. The second script tests Matara January 2020 versus 2021 by
exact block exchanges and adds three-day-block sensitivity for Matara temperature.
A failure to reject is not evidence of equality, and an omnibus result does not
identify specific year pairs. Daily spread does not measure within-day variation.

Outputs: `tables/same_month_*`, `same_month_years.json`, `tables/matara_january_2020_2021.csv`,
`tables/matara_temperature_block3.csv`, `matara_january_example.json`,
`figures/same_month/` (distribution plots for detected differences, plus all Matara
temperature months), and `figures/same_month_examples.png`.

Run `python scripts/report_all_same_month_results.py` to regenerate the all-location report tables and distribution panels from the saved tests and daily values. It checks that every detected location–variable–month combination appears exactly once in the graphs; the tables also retain variables with no detected differences.

## Nonparametric revision (current report)

```bash
python scripts/snapshot_2026_elevation.py
python scripts/nonparametric_weather_tests.py
python scripts/report_nonparametric_same_month.py
python scripts/report_nonparametric_elevation.py
make report
```

Historical comparisons now use Kruskal–Wallis ranks and Fligner–Killeen normal
scores of median-centred absolute deviations. Every observed statistic is checked
against SciPy. Their p-values use 9,999 matched seven-day-block permutations of
scores, a conditional approximation (estimated median uncertainty and dependence
across blocks remain). Holm covers 24 tests per site/feature. Daily summaries are
reused from the hash-verified frozen sources. Old ANOVA and Brown–Forsythe outputs
remain as historical artifacts, but are no longer included in the report.

The updated 2026 analysis uses 800 complete site-month observations in January–August, including all of May (583,200 hourly records). `snapshot_2026_elevation.py` freezes the current committed source list, verifies hashes, hourly uniqueness, seven-feature completeness and expected monthly hours at all 100 sites.
Kruskal–Wallis compares fixed elevation bands <500, 500–<1500, and >=1500 m
(48/26/26 sites). Permutations shuffle band labels within countries, using identical
permutations across months/features; Holm covers all 56 tests. Monthly boxplots
show distributions of site summaries, not distributions of individual hours or days.
This does not test month-by-elevation interaction or recurring seasonality.

Results: `tables/nonparametric_same_month_tests.csv`,
`tables/nonparametric_elevation_months.csv`,
`tables/nonparametric_elevation_band_summaries.csv`, and
`nonparametric_tests.json` with script/input hashes and settings.

The expanded 2026 snapshot is recorded in `elevation_2026_snapshot.json`, with source hashes in `tables/elevation_2026_source_files.csv` and summaries in `tables/elevation_2026_jan_aug_sites.csv`. To update only the elevation tests, use `python scripts/nonparametric_weather_tests.py --elevation-only`. Historical 2020–2025 tests retain their original frozen data.
