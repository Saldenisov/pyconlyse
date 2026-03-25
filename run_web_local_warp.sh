#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

# Warp/local defaults. Override any variable before launching if needed.
export PYCONLYSE_CONDA_ENV="${PYCONLYSE_CONDA_ENV:-pyconlyse39}"
export PYCONLYSE_TANGO_HOST="${PYCONLYSE_TANGO_HOST:-10.20.30.202:10000}"
export TANGO_HOST="${TANGO_HOST:-${PYCONLYSE_TANGO_HOST}}"
export PYCONLYSE_WEB_HOST="${PYCONLYSE_WEB_HOST:-127.0.0.1}"
export PYCONLYSE_WEB_PORT="${PYCONLYSE_WEB_PORT:-5000}"
export PYCONLYSE_FRONTEND_PORT="${PYCONLYSE_FRONTEND_PORT:-3000}"
export PYCONLYSE_WEB_DEBUG="${PYCONLYSE_WEB_DEBUG:-true}"
export PYCONLYSE_JWT_COOKIE_SECURE="${PYCONLYSE_JWT_COOKIE_SECURE:-false}"
export PYCONLYSE_ENFORCE_DEVICE_AUTH="${PYCONLYSE_ENFORCE_DEVICE_AUTH:-false}"
export PYCONLYSE_ALLOWED_ROOT="${PYCONLYSE_ALLOWED_ROOT:-$HOME/TreatmentData}"
export BROWSER="${BROWSER:-open}"

echo "Starting PYCONLYSE web stack in local dev mode..."
echo "Conda env: ${PYCONLYSE_CONDA_ENV}"
echo "Backend:   http://${PYCONLYSE_WEB_HOST}:${PYCONLYSE_WEB_PORT}"
echo "Frontend:  http://localhost:${PYCONLYSE_FRONTEND_PORT}"
echo "TANGO_HOST:${TANGO_HOST}"
echo

exec bash "${SCRIPT_DIR}/web/start_local_mac_dev.sh"
