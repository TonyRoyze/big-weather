#!/usr/bin/env bash
# Shared WSL/Linux launcher, independent of the current working directory.
set -euo pipefail
cd "$(dirname "$0")/.."
export JAVA_HOME
JAVA_HOME=$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")
export SPARK_LOCAL_IP=127.0.0.1
export PYSPARK_PYTHON="$PWD/.venv/bin/python"
export PATH="$PWD/.venv/bin:$PATH"
case "${1:-dashboard}" in
    dashboard) exec .venv/bin/python -m streamlit run dashboard/app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true --browser.gatherUsageStats false ;;
    terminal) exec bash --noprofile --norc ;;
    *) echo 'Usage: team-launch.sh [dashboard|terminal]' >&2; exit 2 ;;
esac
