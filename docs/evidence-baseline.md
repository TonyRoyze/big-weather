# Verified PySpark handoff baseline — pending team interpretation

Dataset: `historical-2019-2024-pyspark-v1`. Fingerprint: `a8662d8e39b537950b6013ae4d16ccc7f3bcdd890bb6d18cfe9f8932c7177898`.

Coverage: {"start": "2019-01-01T00:00:00+00:00", "end": "2024-12-31T23:00:00+00:00"}. Open-Meteo; ERA5 (Copernicus/ECMWF); elevation: Copernicus DEM GLO-90 (2021).

Generated with `weather-analysis evidence`. Tables are newly exported from the published PySpark outputs, not custom-job cache results. See metadata.json for full provenance.

## Elevation Comparison

Equal-weight location means, not pooled precipitation totals.

| elevation_band | mean_location_temperature_c | mean_location_daily_precipitation_mm | locations |
| --- | --- | --- | --- |
| alpine | 7.9993 | 2.3747 | 12 |
| highland | 16.7992 | 3.7373 | 9 |
| lowland | 20.0950 | 3.6953 | 11 |
| midland | 16.0899 | 2.7888 | 4 |

## Seasonal Lapse Rates

Existing pooled daily OLS: temperature ~ elevation, by local season. Not causal.

| season | slope_c_per_m | lapse_rate_c_per_km | intercept_c | r2 | rmse_c | sample_size |
| --- | --- | --- | --- | --- | --- | --- |
| autumn | -0.0031 | -3.0878 | 20.7842 | 0.4261 | 5.7584 | 19752 |
| spring | -0.0027 | -2.7394 | 19.7617 | 0.3267 | 6.3171 | 19776 |
| summer | -0.0035 | -3.5061 | 25.1320 | 0.7169 | 3.5385 | 19712 |
| winter | -0.0028 | -2.8180 | 15.7201 | 0.2292 | 8.3057 | 19672 |

## Wettest Location Days

Top 20 observed daily precipitation totals; not hourly extremes.

| location_id | name | date | daily_precipitation_mm |
| --- | --- | --- | --- |
| addis_ababa | Addis Ababa | 2020-05-23 | 134.3000 |
| tokyo | Tokyo | 2023-06-02 | 125.5000 |
| kandy | Kandy | 2019-02-09 | 122.2000 |
| miami | Miami | 2023-11-16 | 120.3000 |
| male | Malé | 2020-11-17 | 117.2000 |
| colombo | Colombo | 2024-08-12 | 113.1000 |
| colombo | Colombo | 2024-11-26 | 108.4000 |
| kandy | Kandy | 2024-05-14 | 106.5000 |
| venice | Venice | 2024-09-05 | 106.3000 |
| venice | Venice | 2024-05-16 | 103.6000 |
| addis_ababa | Addis Ababa | 2021-09-26 | 103.3000 |
| colombo | Colombo | 2019-10-15 | 103.0000 |
| kandy | Kandy | 2023-11-18 | 101.6000 |
| buenos_aires | Buenos Aires | 2019-10-12 | 100.8000 |
| buenos_aires | Buenos Aires | 2024-03-13 | 100.3000 |
| singapore | Singapore | 2024-11-28 | 99.0000 |
| colombo | Colombo | 2024-11-19 | 97.1000 |
| namche_bazaar | Nanche Bazar | 2019-07-12 | 93.6000 |
| addis_ababa | Addis Ababa | 2024-08-31 | 90.2000 |
| addis_ababa | Addis Ababa | 2022-08-28 | 88.2000 |

## Interpretation limits

Locations are selected, not a random global sample. Latitude, region and season confound elevation associations. Repeated days per location are not independent regression samples. The short study window does not establish a long-term climate trend. Spark removes rows missing any required weather variable or failing range checks and drops duplicate hourly keys; daily metrics therefore describe retained hours. Review pipeline counts and coverage before comparing totals. The lapse-rate output is a signed slope (°C/km), not a positive cooling magnitude.

## Team findings to complete

For each claim, record owner, question, evidence file/job ID, filters, denominator, effect size, visualization and limitations. Do not treat this generated table as a causal finding.

## PySpark verification

All 20 Python tests passed, including transformation tests, real Spark custom-job integration and Streamlit AppTest. The full pipeline was run with `make process`, then published using `make publish`.

- Input and enriched rows: 1,893,888.
- Daily rows: 78,912.
- Rejected/duplicate rows: 0; unmatched location rows: 0.
- Missing hourly observations across the study window: 0.
- Pipeline: pyspark, pipeline-v1, local[4].
- Full processing time: 46.852s (single local run; not a performance guarantee).

All five output tables were independently compared with the previous published release (`historical-2019-2024-v2`) after sorting by their keys. Schemas, row counts and values matched within 1e-8 numeric tolerance, including all 1,893,888 enriched hourly rows.

## Environment

Python 3.11.15; macOS-26.6.2-arm64-arm-64bit; Java 21.0.11.

- pandas: 2.3.3
- pyarrow: 21.0.0
- pyspark: 4.0.1
- streamlit: 1.63.0
- plotly: 6.9.0

The processing implementation is entirely Python/PySpark. Run `scripts/benchmark.py` using the current commands in the team handoff to collect repeated performance evidence; old timings must not be presented as measurements of this implementation.

Regenerate the complete tables and provenance with `make evidence`; files are under `data/platform/evidence/historical-2019-2024-pyspark-v1/`. Final team findings and interpretation remain to be completed.
