# Instructions for models and contributors

Read this file before changing code, notebooks or documentation.

## Repository workflow

1. Inspect the README, project plan and relevant source before making changes.
2. Keep all exploratory notebooks under `notebooks/exploratory/`.
3. Keep reusable Streamlit code under `dashboard/`.
4. Keep explanations, decisions, findings and implementation notes under `docs/`.
5. Do not put notebooks, generated datasets or exploratory scripts in the root.
6. Do not modify raw data to improve a result. Record filters and assumptions.
7. Do not fabricate results. Run the work against available data or mark it as
   unverified.
8. Finish by updating documentation and checking `git status`.

## Exploratory analysis

Use this structure:

```text
notebooks/
└── exploratory/
    ├── README.md
    ├── 01_data_quality.ipynb
    ├── 02_elevation_temperature.ipynb
    ├── 03_seasonal_patterns.ipynb
    ├── 04_geographic_variation.ipynb
    └── 05_extreme_conditions.ipynb
```

Before creating a notebook, read `docs/project-plan.md` and
`docs/exploratory-analysis.md`. Inspect the available data under `data/` and
reuse the existing schemas. Prefer processed Parquet datasets and never commit
generated data or caches by default.

Every notebook must include its question, dataset/version, date coverage,
imports, data-quality checks, reproducible transformations, useful tables or
visualizations, findings and limitations. Use deterministic filters and avoid
collecting large datasets to the driver.

For every completed notebook, create or update:

```text
docs/analysis/<notebook-name>.md
```

That note must record the question, data, method, key findings, visuals,
limitations and notebook path. Update `docs/exploratory-analysis.md` when a new
team question is introduced.

## Streamlit dashboard

Read `docs/streamlit-dashboard.md` before implementing the dashboard. Use:

```text
dashboard/
├── README.md
├── app.py
├── pages/
├── components/
├── services/
└── tests/
```

The dashboard must read processed data and job metadata through helper/service
functions. Keep ingestion and Spark internals out of page code. Support overview,
exploratory analysis, custom jobs and job history. Display units, date coverage,
source attribution, dataset version and cache status. Never execute arbitrary
Python submitted by a user.

Use validated job specifications with filters, grouping fields and approved
aggregations. Do not accept raw Python code from the dashboard.

After dashboard work, update `dashboard/README.md` and
`docs/dashboard-implementation.md` with implemented pages, data contracts,
run instructions, verification steps and known limitations. Update
`docs/streamlit-dashboard.md` if the planned interface changes.

## Documentation requirement

Documentation must be updated in the same change as code or notebooks. At a
minimum, report files changed, how to run the work, what was verified, results
or screenshots where applicable, and known limitations. Use relative Markdown
links so the documentation remains useful after pulling the repository.
