.PHONY: install ingest-sample ingest-all test-python test-scala test interim clean

PYTHON ?= python3

install:
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -e '.[dev]'

ingest-sample:
	.venv/bin/big-weather ingest --limit 2 --start-date 2024-01-01 --end-date 2024-01-07

ingest-all:
	.venv/bin/big-weather ingest --start-date 2019-01-01 --end-date 2024-12-31

test-python:
	.venv/bin/pytest

test-scala:
	sbt test

test: test-python test-scala

interim:
	typst compile docs/interim.typ docs/interim.pdf

clean:
	rm -rf target project/target .pytest_cache

