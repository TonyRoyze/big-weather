#!/usr/bin/env bash
# Stop only Big Weather's known local development ports.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
STATE_DIR="$ROOT/.local-services"

stop_pid_file() {
    local name="$1" pid_file="$STATE_DIR/$name.pid"
    [[ -f "$pid_file" ]] || return 0
    local pid
    pid=$(<"$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping $name (PID $pid)"
        kill "$pid" 2>/dev/null || true
        for _ in {1..20}; do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.1
        done
        kill -KILL "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
}

stop_pid_file dashboard
stop_pid_file explorer
stop_pid_file notebook

# Catch services started manually on the project's explicit development ports.
for port in 8501 8001 2718; do
    pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
        echo "Stopping listener(s) on project port $port"
        kill $pids 2>/dev/null || true
    fi
done

echo "Big Weather local services stopped."
