#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

CONDA_ENV="${PYCONLYSE_CONDA_ENV:-pyconlyse39}"
export PYCONLYSE_TANGO_HOST="${PYCONLYSE_TANGO_HOST:-10.20.30.202:10000}"
export TANGO_HOST="${TANGO_HOST:-${PYCONLYSE_TANGO_HOST}}"
export PYCONLYSE_WEB_HOST="${PYCONLYSE_WEB_HOST:-127.0.0.1}"
export PYCONLYSE_WEB_PORT="${PYCONLYSE_WEB_PORT:-5000}"
export PYCONLYSE_WEB_DEBUG="${PYCONLYSE_WEB_DEBUG:-true}"
export PYCONLYSE_JWT_COOKIE_SECURE="${PYCONLYSE_JWT_COOKIE_SECURE:-false}"
export BROWSER="${BROWSER:-none}"

backend_pid=""
frontend_pid=""

cleanup() {
    local exit_code=$?

    if [[ -n "${frontend_pid}" ]] && kill -0 "${frontend_pid}" 2>/dev/null; then
        kill "${frontend_pid}" 2>/dev/null || true
    fi

    if [[ -n "${backend_pid}" ]] && kill -0 "${backend_pid}" 2>/dev/null; then
        kill "${backend_pid}" 2>/dev/null || true
    fi

    if [[ -n "${frontend_pid}" ]]; then
        wait "${frontend_pid}" 2>/dev/null || true
    fi

    if [[ -n "${backend_pid}" ]]; then
        wait "${backend_pid}" 2>/dev/null || true
    fi

    exit "${exit_code}"
}

trap cleanup EXIT INT TERM

if [[ ! -d "${PROJECT_ROOT}/web/frontend/node_modules" ]]; then
    echo "[setup] Installing frontend dependencies..."
    npm --prefix web/frontend install
fi

echo "============================================================"
echo "PYCONLYSE Local Mac Web Dev"
echo "============================================================"
echo "Conda env:   ${CONDA_ENV}"
echo "TANGO_HOST:  ${TANGO_HOST}"
echo "Backend:     http://${PYCONLYSE_WEB_HOST}:${PYCONLYSE_WEB_PORT}"
echo "Frontend:    http://localhost:3000"
echo "Stop:        Ctrl+C"
echo "============================================================"

conda run -n "${CONDA_ENV}" python web/start_local_mac_dev.py &
backend_pid=$!

sleep 2

npm --prefix web/frontend start &
frontend_pid=$!

while true; do
    if ! kill -0 "${backend_pid}" 2>/dev/null; then
        wait "${backend_pid}" || true
        break
    fi

    if ! kill -0 "${frontend_pid}" 2>/dev/null; then
        wait "${frontend_pid}" || true
        break
    fi

    sleep 1
done
