.PHONY: install ingest-sample ingest-all test-python test interim clean

PYTHON ?= python3

install:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev,analysis]'

ingest-sample:
	.venv/bin/big-weather ingest --data-root data/sample --limit 2 --start-date 2024-01-01 --end-date 2024-01-07

ingest-all:
	.venv/bin/big-weather ingest --start-date 2019-01-01 --end-date 2024-12-31

test-python:
	.venv/bin/pytest

test: test-python

interim:
	typst compile docs/interim.typ docs/interim.pdf

clean:
	rm -rf .pytest_cache .ruff_cache

.PHONY: install-team process process-sample publish dashboard evidence lint
VERSION ?= historical-2019-2024-pyspark-v1
PLATFORM_ROOT ?= data/platform

install-team:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev,dashboard,analysis]'

process:
	.venv/bin/weather-analysis process

process-sample:
	.venv/bin/weather-analysis process --input data/sample/raw --output data/sample/processed

publish:
	.venv/bin/weather-analysis --root $(PLATFORM_ROOT) publish --data-root data --version $(VERSION)

dashboard:
	WEATHER_PLATFORM_ROOT=$(PLATFORM_ROOT) .venv/bin/streamlit run dashboard/app.py

evidence:
	.venv/bin/weather-analysis --root $(PLATFORM_ROOT) evidence

lint:
	.venv/bin/ruff check python dashboard scripts

.PHONY: windows-setup
windows-setup:
	.venv/bin/python scripts/build_windows_setup.py
