#!/usr/bin/env bash
# Start the Big Weather local services.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"
STATE_DIR="$ROOT/.local-services"
mkdir -p "$STATE_DIR"
PLATFORM_ROOT="${PLATFORM_ROOT:-data/platform}"
REGIONAL_ROOT="${REGIONAL_ROOT:-data/regional-2020-2025}"
PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
    echo "Missing .venv. Run: make install-team" >&2
    exit 1
fi

start_service() {
    local name="$1" port="$2"
    shift 2
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "$name is already listening on port $port; leaving it unchanged."
        return 0
    fi
    echo "Starting $name on http://127.0.0.1:$port"
    nohup "$@" >"$STATE_DIR/$name.log" 2>&1 < /dev/null &
    echo "$!" >"$STATE_DIR/$name.pid"
}

start_service dashboard 8501 env \
    WEATHER_REGIONAL_ROOT="$REGIONAL_ROOT" WEATHER_PLATFORM_ROOT="$PLATFORM_ROOT" \
    "$PYTHON" -m streamlit run dashboard/app.py \
    --server.address 127.0.0.1 --server.port 8501 \
    --server.headless true --browser.gatherUsageStats false

if [[ -d "$ROOT/explorer" && -d "$ROOT/explorer/node_modules" ]]; then
    npm run build --prefix explorer >/dev/null
    start_service explorer 8001 env \
        WEATHER_REGIONAL_ROOT="$REGIONAL_ROOT" WEATHER_PLATFORM_ROOT="$PLATFORM_ROOT" \
        "$PYTHON" -m weather_analysis.explorer --root "$PLATFORM_ROOT" --port 8001
elif [[ -d "$ROOT/explorer" ]]; then
    echo "Skipping explorer: run make install-explorer first."
fi

if [[ -f "$ROOT/notebooks/explore_weather.py" ]]; then
    start_service notebook 2718 env WEATHER_PLATFORM_ROOT="$ROOT/$PLATFORM_ROOT" \
        "$ROOT/.venv/bin/marimo" edit notebooks/explore_weather.py \
        --host 127.0.0.1 --port 2718 --headless --no-token
fi

echo "Logs: $STATE_DIR/*.log"
echo "Streamlit: http://127.0.0.1:8501"
[[ -f "$STATE_DIR/explorer.pid" ]] && echo "Explorer:  http://127.0.0.1:8001"
[[ -f "$STATE_DIR/notebook.pid" ]] && echo "Notebook:  http://127.0.0.1:2718"
echo "Stop with: make stop-local"
