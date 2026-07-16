#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 2.8cm, right: 2.8cm),
  footer: context {
    set text(size: 9pt, fill: luma(140))
    align(center)[#counter(page).display("1 of 1", both: true)]
  },
)

// Times New Roman, 12pt, 1.15 line spacing
#set text(font: "Times New Roman", size: 12pt, lang: "en")
#set par(justify: true, leading: 0.75em, spacing: 1.15em)

// Headings: bold, same font, no extra numbering
#show heading: it => {
  v(0.8em)
  text(weight: "bold", size: 12pt)[#it.body]
  v(0.3em)
}

// ── Header block ────────────────────────────────────────────────────────────
#align(center)[
  #text(weight: "bold", size: 12pt)[DS 4004 Big Data Analytics Group Project 2026]
  #linebreak()
  #text(size: 12pt)[Project Proposal: Geospatial Weather and Elevation Analysis (Option 5)]
  #linebreak()
  // #text(size: 12pt)[Date: 16th June 2026]
]

// #v(0.5em)
// #line(length: 100%, stroke: 0.8pt)
// #v(0.2em)

// #grid(
//   columns: (auto, 1fr),
//   column-gutter: 1em,
//   row-gutter: 0.35em,
//   [*Team Members:*], [Vidura · Kaumindi · Thishakya],
//   [*Course:*], [DS 4004 Big Data Analytics],
//   [*Option:*], [Geospatial Weather and Elevation Analysis],
// )

// #v(0.2em)
// #line(length: 100%, stroke: 0.8pt)
// #v(0.5em)

// ── 1. Introduction ─────────────────────────────────────────────────────────
= 1. Introduction

The goal is to investigate how geographical location and altitude influence weather conditions, specifically temperature, rainfall, and wind across locations spanning a wide range of elevations. Data will be collected through the Open-Meteo API suite, processed using Apache Spark with Scala, and presented via an interactive web dashboard.

// ── 2. Data Sources ──────────────────────────────────────────────────────────
= 2. Data Sources

All data will be sourced from the *Open-Meteo API*, which is free and open to use. We will use four endpoints:

*Geocoding API* Resolves location names to latitude and longitude coordinates. This is the first step in the pipeline, allowing us to work with named places rather than raw coordinates.

*Elevation API* Returns the altitude in metres for any coordinate. This is the key variable in our analysis, used to classify all locations into elevation bands.

*Historical Weather API* Provides hourly weather records going back up to several decades. We will retrieve temperature (2 m), precipitation, wind speed (10 m), and relative humidity for approximately 30–40 locations over a five-year window (2019–2024), yielding roughly 1.5–2 million rows of data sufficient to justify Spark-based processing.

*Forecast API* Provides short-range forecasts used to populate the real-time components of the dashboard.

Locations will be chosen deliberately to span four elevation bands: lowland (0–200 m), midland (200–1 000 m), highland (1 000–3 000 m), and alpine (above 3 000 m).

The Open-Meteo rate limit of approximately 600 requests per minute will be managed through client-side throttling and response caching using the Python `requests-cache` library.

// ── 3. Methodology ───────────────────────────────────────────────────────────
= 3. Methodology

*Data Ingestion (Python).* A set of Python scripts will call the Geocoding, Elevation, and Historical Weather APIs for each location. Responses will be saved as Parquet files. Raw files will be organised by location and year on the local file system.

*Big Data Processing (Scala + Apache Spark).* The project is a Spark application written in Scala, built using sbt. Spark will run in local mode (`local[*]`), which is sufficient for our data volume and requires no cluster setup. The Spark jobs will:
1. Read and validate raw Parquet data
2. Join weather records with elevation metadata on a shared location identifier
3. Assign each location an elevation band using conditional column logic
4. Aggregate average temperature, precipitation, and wind speed grouped by elevation band, region, and season
5. Apply window functions to compute 30-day rolling averages and year-over-year temperature changes per location
6. Run a Spark MLlib linear regression of temperature against elevation, per season, to empirically measure the environmental lapse rate
7. Processed outputs will be written back to Parquet, partitioned by elevation band, and a summary will be loaded into a local PostgreSQL database for the dashboard to query

*Analysis.* Beyond the lapse rate regression, we will analyse precipitation gradients across elevation bands, wind amplification at higher altitudes, and seasonal variation across regions. All statistics will be derived from Spark aggregations, with results exported for visualisation.

*Web Application (Python Streamlit).* An interactive Streamlit dashboard will be the front end. It will include:
- An interactive map (using Folium or Plotly) where locations are colour-coded by elevation band or selected weather metric;
- Scatter plots of elevation versus temperature and precipitation with the regression line overlaid;
- A time-series panel allowing multi-location comparison filtered by date range and elevation band;
- And a location search input returning current forecast data from the Forecast API.
The dashboard will query PostgreSQL for aggregated data and read Parquet files for raw drill-down views.

// ── 4. Project Plan ──────────────────────────────────────────────────────────
= 4. Project Plan

- *Week 1 Setup.* 
- *Weeks 2–3 Data Ingestion.*
- *Weeks 3–4 Spark Development.* 
- *Week 5 Dashboard.* 
- *Week 6 Integration and Testing.* 
