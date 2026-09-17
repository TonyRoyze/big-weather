# Ask weather

Open the separate explorer and choose **Ask weather**, or visit
`http://127.0.0.1:8001/?page=ask`. Streamlit remains a separate dashboard.

The page accepts a plain-English question and returns a chart, plain-text summary,
result table, coverage counts, and the exact generated Spark SQL. It supports one
weather feature per request, daily trends, location/country comparisons, elevation
scatter plots, and precipitation totals by location, within 366 days and 100 locations.
Unsupported or ambiguous requests receive a clarification instead of invented results.

## Setup

The default local demo uses your Codex subscription without an API key. Install the
[official Codex CLI](https://learn.chatgpt.com/docs/cli), then run:

```bash
codex login
codex login status
make explorer-raw
```

Choose ChatGPT sign-in. The explorer displays the connection status. Subscription
usage limits apply. Codex runs locally through `codex exec`, receives only the supplied
catalog and aggregates, and returns schema-validated plans. Runs are ephemeral, use
an empty working directory and read-only sandbox, disable shell/web tools, and ignore
user configuration. Managed authentication remains with Codex. No credentials enter
the browser. `WEATHER_CODEX_MODEL` optionally chooses a model supported by your account.

For the separately billed OpenAI API instead:

```bash
export WEATHER_AI_PROVIDER=openai
export OPENAI_API_KEY='your-key'
export OPENAI_MODEL=gpt-5
make explorer-raw
```

Dependencies: `.venv/bin/python -m pip install -e '.[explorer,analysis]'` and Java 17+.
Set environment variables in the terminal launching the server; restart it after changes.
Do not start a second server on the same port. Never put secrets in `VITE_` variables.

## How it works

The selected provider receives the question and current dataset catalog: supported
features and units, locations and elevations, date coverage, and snapshot identity.
Structured output produces a restricted analysis plan. The server validates it and
compiles Spark SQL from an allowlisted template. Model-written Python or arbitrary SQL
is never executed. This is catalog-grounded analysis rather than a document vector index.

A local Spark subprocess reads the snapshot's committed Parquet files and joins location
metadata. Jobs run with two local threads, one at a time, with a three-minute timeout.
No ingestion, publication, external paths or data-changing statements are exposed.
Each request currently recomputes its result; it does not share the map's Arrow cache.

Daily values require 24 non-null hourly observations. Precipitation is summed within
a day; other supported fields are averaged. Requested means/minima/maxima operate on
those daily values. Country/date aggregations pool the available location-days; missing
coverage can change comparisons. Raw previews are labelled unpublished.

The summary call receives the computed aggregates, units, plan and coverage; at most
400 result rows are sent, with explicit truncation information. The browser retains the
full result (up to 10,000 rows). If summary generation fails, the chart and data remain
available. Questions/catalog/aggregate results are sent to OpenAI (the API mode uses `store=False`);
raw hourly files and credentials are not sent as prompt content. No conversation history
is persisted, and each question is independent.

Reference: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
