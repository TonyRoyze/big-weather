# Big Weather

DS 4004 Option 5: geospatial analysis of temperature, precipitation and wind across elevation bands. The week-4 implementation includes cached Open-Meteo ingestion and a Scala/Apache Spark processing application.

## Quick start

Prerequisites: Python 3.11+, Java 17/21, sbt 1.11+, and Typst 0.14+.

```bash
make install
make test-python
make ingest-sample
sbt test
sbt 'runMain lk.ac.ds4004.weather.WeatherJob'
make interim
```

The sample command ingests two locations for seven days. For the proposal's full 2019–2024 range across all 36 locations, run `make ingest-all`; the verified full run contains exactly 1,893,888 hourly observations.

## Data layout

```text
data/raw/locations/locations.parquet
data/raw/weather/location_id=<id>/year=<yyyy>/weather.parquet
data/processed/enriched_weather/elevation_band=<band>/...
data/processed/{summaries,daily_metrics,yearly_metrics,lapse_rates}/...
```

The API cache and generated datasets are ignored by Git. Raw weather uses UTC, °C, mm, m/s and percent. Historical requests fix `models=era5` so model changes do not create artificial trends while all four proposed weather variables remain available.

## Reproducibility and scope

- `config/locations.csv` provides 36 globally distributed targets across the four proposed elevation bands. Coordinates and elevation are resolved at ingestion time through the Geocoding and Elevation APIs.
- API responses are cached indefinitely and transient failures retry with exponential backoff.
- Spark validates ranges, joins location metadata, assigns hemisphere-aware seasons and elevation bands, produces regional/seasonal summaries, 30-day rolling daily temperature, annual year-over-year changes, and seasonal linear lapse-rate models.
- PostgreSQL and Streamlit belong to weeks 5–6 and are not implemented in the week-4 milestone.

Open-Meteo data must be attributed to Open-Meteo and its upstream providers. Elevation data is Copernicus DEM GLO-90 (2021).
