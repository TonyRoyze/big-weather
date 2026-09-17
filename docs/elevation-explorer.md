# 3D elevation explorer

The React/TypeScript application in `explorer/` is a separate dashboard from
Streamlit. It uses deck.gl to render terrain and weather observations and a
read-only FastAPI service to query local Parquet. Its [Ask weather page](ask-weather.md)
adds plain-English analysis using OpenAI and bounded local Spark jobs. Streamlit still runs with
`make dashboard` on port 8501.

## Run

Requires the existing Python environment and Node.js 22.12+ (or a newer supported
Node release).

```bash
make install-explorer
make explorer                 # published release, http://127.0.0.1:8001
```

If no release has been published, explicitly opt into the partial download:

```bash
make explorer-raw             # existing regional download, same URL
```

Raw preview is prominently labelled as unpublished. It does not start ingestion,
consume Open-Meteo quota, or publish anything. Missing days/locations stay missing.
The API detects newly committed downloads and active-release changes. Click
**Load weather** to refresh a raw preview; reload the page to select the newest
available seven days, initially displayed on their last day. Use `REGIONAL_ROOT=...` or
`PLATFORM_ROOT=...` to change the data source.

For frontend development, run the API in one terminal and Vite in another:

```bash
.venv/bin/python -m weather_analysis.explorer --raw-root data/regional-2020-2025
make explorer-dev             # http://127.0.0.1:5173, proxies /api to port 8001
```

## Interactions and meaning

1. Choose an available weather feature, country and a window of up to 93 days.
2. Click **Load weather**. Changes to the request controls do not relabel the
   currently loaded scene; click Load weather again to apply them.
3. Drag to pan, Shift-drag to rotate, and scroll to zoom. Reset camera returns to
   Sri Lanka. A request initially centres the camera on a location with data.
4. Use the date slider or playback button. The browser reuses the loaded window.
5. Click a sampled location, or choose it in Location Detail, to see its elevation,
   current weather and the history for the loaded window.
6. Open **Map settings** in the chart’s top-right corner for elevation exaggeration,
   colour interpolation and opacity, terrain, location labels and camera reset.
   Changes apply immediately and remain after closing the modal. Escape, Done,
   the close button or the backdrop dismiss it. The selected location is labelled
   at overview zoom; zoom in for all labels. Terrain starts enabled so weather colours follow the map surface.

Geographic height represents elevation; marker colour represents weather. Terrain
is a separate digital elevation model, not a surface interpolated from the study
locations. Display exaggeration affects terrain and point heights; it never changes
reported elevation or weather. Markers have a small display offset above their
reported height for visibility. Different terrain and location elevation sources
can disagree, so terrain can be disabled to inspect points.

Each daily value requires 24 non-null hourly observations in UTC. Precipitation
is a daily sum (mm/day); other supported continuous features use daily means with
explicit units. Incomplete days are null. No line is drawn across missing days.
The colour range stays fixed across the loaded window, so playback does not
silently rescale colours. Weather colours are rasterized into the terrain tiles themselves using Delaunay
interpolation between nearby samples. The colour follows the digital elevation model
in 3D; there is no separate floating mesh. Triangles with a missing vertex
or any edge longer than 250 km are omitted; nothing is extrapolated outside the
triangulation. This is a terrain-draped visual estimate, not a measured weather grid. Point readouts and history retain the original daily values.
No causal elevation claim is made. Categorical weather codes and wind directions are not averaged. The feature
menu exposes the curated continuous variables actually present in the source.

## Loading and performance

`GET /api/metadata` returns dataset identity, coverage, location metadata and
available features. `GET /api/window` takes `metric`, ISO `start`/`end`, repeated
`locations`, and an optional `fingerprint` to reject stale requests.

The API projects only timestamp, location and the requested metric. Arrow applies
location/time filters and, where available, year partition filters before pandas
aggregation. Requests are bounded to 100 locations × 93 days, with at most 9,300
daily records returned. The API caches 32 query results; the browser caches 12
windows. A new request cancels the previous request in the browser and cannot be
overwritten by its stale response. Browser cancellation does not interrupt an
already running server-side scan. Playback and camera changes do not query Python.
The displayed query duration covers the server query/cache retrieval, not total
network transfer or rendering. Spark remains the offline processing system.

The API binds to localhost and serves the built frontend itself, so deployment
needs no CORS configuration. It is a local dashboard, not an authenticated public
API. Interactive API documentation is at `/docs`.

## Terrain and network

The default terrain provider is the public Mapzen Terrarium tile collection on AWS:
`https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png`.
Terrain loads on demand as the camera moves; it requires an internet connection.
No weather values are sent to the tile provider. If tiles fail, an explicit notice
is shown and sampled locations remain usable. The point view works without terrain.
Terrain attribution and upstream source information:
https://registry.opendata.aws/terrain-tiles/.

Set `VITE_TERRAIN_URL` at frontend build time to another CORS-enabled **Terrarium**
URL template. Other elevation encodings require updating the decoder. Set
`VITE_STREAMLIT_URL` if Streamlit runs somewhere other than localhost:8501.
The interface uses Google Fonts with system-font fallbacks.

## Checks

```bash
.venv/bin/pytest python/tests/test_explorer.py python/tests/test_dashboard.py python/tests/test_charts.py
npm test --prefix explorer
npm run build --prefix explorer
```

Library references: [deck.gl terrain](https://deck.gl/docs/api-reference/geo-layers/terrain-layer),
[React integration](https://deck.gl/docs/get-started/using-with-react),
[performance guidance](https://deck.gl/docs/developer-guide/performance).

## Weather analytics

After **Load weather**, the charts below the map follow the loaded country and
UTC date range. The timeline follows the selected weather feature, with its own
Daily / Weekly average / Monthly average control. Classes divide the selected
locations' elevation range into four equal-width intervals, or five when the
highest location is at least 3,000 m. Colours and boundaries are shared by the
scatter plots and remain fixed over the loaded dates; empty classes stay empty.

Weekly and monthly points average available complete location-days. Hover, tap,
or keyboard-focus a date to reveal mean ± one population standard deviation and
read the variance in squared units. These are descriptive spread bars, not
confidence intervals. Missing days are excluded, never treated as zero; periods
with no observations break the line. Partial periods use only the selected dates.

Wind speed, relative humidity and surface pressure each have an average card
with minimum, maximum, median, population variance and observation count, an
individual-location mean versus elevation scatter plot, and a 16-bin histogram
of complete daily values. These summaries use the full loaded date range and are
independent of map playback and its min/max/total aggregation. Unavailable
features and empty selections are labelled explicitly.

`GET /api/analytics` accepts metric, start, end, locations and fingerprint, with
bounds of 100 locations and 3,660 days. It projects only the needed features,
reduces hourly data in 31-day chunks, caches eight summaries, and returns daily,
calendar-week (Monday start), and calendar-month summaries. Every daily value
requires 24 non-null hours. Client requests are cancelled on selection changes;
server scans already in progress may finish.

### Elevation-band boxplot

After **Load weather**, the analytics section shows the selected feature by fixed
elevation bands: below 500 m, 500–<1,500 m, and at least 1,500 m. The boxplot uses
the loaded date range and location/country selection. Each dot is one location's
mean over available complete daily values (mean daily total for precipitation),
independent of map playback and map aggregation. Hover, tap, or keyboard-focus
a box for its median, quartiles and 1.5-IQR whiskers, or a dot for the location's
value, elevation and contributing day count. Empty bands remain visible.
