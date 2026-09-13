#!/usr/bin/env bash
# Invoked by the Windows bootstrapper as root inside Ubuntu 24.04.
set -euo pipefail
package_dir=$1
payload_id=$2
[[ "$payload_id" =~ ^[a-f0-9]{12}$ ]] || { echo 'Invalid package identifier'; exit 1; }
[[ $(id -u) == 0 ]] || { echo 'Setup must run as root inside WSL'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates python3 python3-venv openjdk-21-jdk-headless make git
if ! id bigweather >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash bigweather
fi
project_dir="/home/bigweather/projects/big-weather-$payload_id"
install -d -o bigweather -g "$(id -gn bigweather)" /home/bigweather/projects
# Re-running setup preserves the teammate's code edits and downloaded/generated data.
if [[ ! -e "$project_dir/.setup-extracted" ]]; then
    if [[ -e "$project_dir" ]]; then
        echo "An unfinished/existing project exists at $project_dir. Move it aside before retrying; setup will not overwrite it."
        exit 1
    fi
    staging_dir=$(mktemp -d /home/bigweather/projects/.setup-XXXXXXXX)
    trap 'rm -rf -- "$staging_dir"' EXIT
    tar --extract --gzip --file "$package_dir/payload.tar.gz" --directory "$staging_dir" --no-same-owner
    touch "$staging_dir/.setup-extracted"
    chown -R bigweather:"$(id -gn bigweather)" "$staging_dir"
    mv "$staging_dir" "$project_dir"
    trap - EXIT
fi
# Dependencies and application code run as an ordinary Linux user.
runuser -u bigweather -- bash -s -- "$project_dir" <<'USER_SETUP'
set -euo pipefail
cd "$1"
export JAVA_HOME
JAVA_HOME=$(dirname "$(dirname "$(readlink -f "$(command -v java)")")")
export SPARK_LOCAL_IP=127.0.0.1
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
export PYSPARK_PYTHON="$PWD/.venv/bin/python"
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev,dashboard,analysis]'
.venv/bin/python scripts/check_setup.py
USER_SETUP
