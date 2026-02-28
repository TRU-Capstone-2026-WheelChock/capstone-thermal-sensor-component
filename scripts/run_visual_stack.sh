#!/usr/bin/env bash
set -euo pipefail

RECEIVER_MODULE="${RECEIVER_MODULE:-capstone_thermal_sensor.receiver}"
VIS_APP="${VIS_APP:-capstone_thermal_sensor.visualize:app}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PYTHONPATH="${PROJECT_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"
cd "${PROJECT_ROOT}"

python -m "${RECEIVER_MODULE}" &
receiver_pid=$!

cleanup() {
  kill "${receiver_pid}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

exec uvicorn "${VIS_APP}" --host "${HOST}" --port "${PORT}" --workers 1
