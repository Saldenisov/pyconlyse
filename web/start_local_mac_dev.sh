#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

CONDA_ENV="${PYCONLYSE_CONDA_ENV:-pyconlyse}"
export PYCONLYSE_TANGO_HOST="${PYCONLYSE_TANGO_HOST:-10.20.30.202:10000}"
export TANGO_HOST="${TANGO_HOST:-${PYCONLYSE_TANGO_HOST}}"
export PYCONLYSE_WEB_HOST="${PYCONLYSE_WEB_HOST:-127.0.0.1}"
export PYCONLYSE_WEB_PORT="${PYCONLYSE_WEB_PORT:-5000}"
export PYCONLYSE_FRONTEND_PORT="${PYCONLYSE_FRONTEND_PORT:-3000}"
export PYCONLYSE_WEB_DEBUG="${PYCONLYSE_WEB_DEBUG:-true}"
export PYCONLYSE_JWT_COOKIE_SECURE="${PYCONLYSE_JWT_COOKIE_SECURE:-false}"
export PYCONLYSE_ENFORCE_DEVICE_AUTH="${PYCONLYSE_ENFORCE_DEVICE_AUTH:-false}"
export PYCONLYSE_ALLOWED_ROOT="${PYCONLYSE_ALLOWED_ROOT:-$HOME/TreatmentData}"
export BROWSER="${BROWSER:-none}"
export PORT="${PORT:-${PYCONLYSE_FRONTEND_PORT}}"

mkdir -p "${PYCONLYSE_ALLOWED_ROOT}"

backend_pid=""
frontend_pid=""

ensure_port_available() {
    local port="$1"
    local pids=""

    if ! command -v lsof >/dev/null 2>&1; then
        echo "[warn] lsof is not available; cannot preflight port ${port}."
        return 0
    fi

    pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN || true)"
    if [[ -z "${pids}" ]]; then
        return 0
    fi

    echo "[port] Stopping process(es) using port ${port}: ${pids}"
    kill ${pids} 2>/dev/null || true

    for _ in 1 2 3 4 5; do
        sleep 1
        if ! lsof -tiTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
    done

    pids="$(lsof -tiTCP:"${port}" -sTCP:LISTEN || true)"
    if [[ -n "${pids}" ]]; then
        echo "[port] Force stopping process(es) still using port ${port}: ${pids}"
        kill -9 ${pids} 2>/dev/null || true
    fi

    sleep 1
    if lsof -tiTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1; then
        echo "[error] Port ${port} is still busy after stop attempt."
        exit 1
    fi
}

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

ensure_port_available "${PYCONLYSE_WEB_PORT}"
ensure_port_available "${PORT}"

echo "============================================================"
echo "PYCONLYSE Local Mac Web Dev"
echo "============================================================"
echo "Conda env:   ${CONDA_ENV}"
echo "TANGO_HOST:  ${TANGO_HOST}"
echo "Data Root:   ${PYCONLYSE_ALLOWED_ROOT}"
echo "Backend:     http://${PYCONLYSE_WEB_HOST}:${PYCONLYSE_WEB_PORT}"
echo "Frontend:    http://localhost:${PORT}"
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
