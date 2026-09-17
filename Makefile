PYTHON ?= python3
REGIONAL_ROOT ?= data/regional-2020-2025
REGIONAL_REQUESTS ?= 100
PLATFORM_ROOT ?= data/platform
VERSION ?= regional-100-2020-2025-v1

.PHONY: install install-team install-notebook plan ingest ingest-all process publish test lint dashboard evidence report notebook notebook-altair notebook-relationships notebook-export start-local stop-local windows-setup clean regional-plan regional-ingest regional-ingest-all regional-process regional-publish

install install-team install-notebook:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev,dashboard,analysis,notebook]'

plan regional-plan:
	.venv/bin/python -m weather_ingest.study --data-root $(REGIONAL_ROOT) --plan

ingest regional-ingest:
	.venv/bin/python -m weather_ingest.study --data-root $(REGIONAL_ROOT) --max-requests $(REGIONAL_REQUESTS)

ingest-all regional-ingest-all:
	.venv/bin/python -m weather_ingest.study --data-root $(REGIONAL_ROOT) --max-requests $(REGIONAL_REQUESTS) --watch

process regional-process:
	.venv/bin/weather-analysis process --input $(REGIONAL_ROOT)/raw --output $(REGIONAL_ROOT)/processed

publish regional-publish:
	.venv/bin/weather-analysis --root $(PLATFORM_ROOT) publish --data-root $(REGIONAL_ROOT) --version $(VERSION)

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check python dashboard scripts notebooks

dashboard:
	WEATHER_REGIONAL_ROOT=$(abspath $(REGIONAL_ROOT)) WEATHER_PLATFORM_ROOT=$(abspath $(PLATFORM_ROOT)) .venv/bin/streamlit run dashboard/app.py

report:
	typst compile docs/report/main.typ docs/report/main.pdf

start-local:
	bash scripts/start-local.sh

stop-local:
	bash scripts/stop-local.sh

.PHONY: install-explorer explorer explorer-raw explorer-dev explorer-build
install-explorer:
	.venv/bin/python -m pip install -e '.[explorer]'
	npm ci --prefix explorer

explorer-build:
	npm run build --prefix explorer

explorer: explorer-build
	.venv/bin/python -m weather_analysis.explorer --root $(PLATFORM_ROOT)

explorer-raw: explorer-build
	.venv/bin/python -m weather_analysis.explorer --raw-root $(REGIONAL_ROOT)

explorer-dev:
	npm run dev --prefix explorer

evidence:
	.venv/bin/weather-analysis --root $(PLATFORM_ROOT) evidence

notebook:
	WEATHER_PLATFORM_ROOT=$(abspath $(PLATFORM_ROOT)) .venv/bin/marimo edit notebooks/explore_weather.py

notebook-altair:
	WEATHER_PLATFORM_ROOT=$(abspath $(PLATFORM_ROOT)) .venv/bin/marimo edit notebooks/spark_altair_explorer.py

RELATIONSHIP ?= thermal
notebook-relationships:
	WEATHER_PLATFORM_ROOT=$(abspath $(PLATFORM_ROOT)) .venv/bin/marimo edit --watch notebooks/relationships/$(RELATIONSHIP).py

notebook-export:
	mkdir -p data/notebook-exports
	WEATHER_PLATFORM_ROOT=$(abspath $(PLATFORM_ROOT)) .venv/bin/marimo export html notebooks/explore_weather.py -o data/notebook-exports/explore_weather.html --force

windows-setup:
	.venv/bin/python scripts/build_windows_setup.py

clean:
	rm -rf .pytest_cache .ruff_cache
