#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this script with sudo." >&2
    exit 1
fi

readonly TANGO_HOST_VALUE="${TANGO_HOST_VALUE:-10.20.30.202:10000}"
readonly DB_HOST="${HDBPP_DB_HOST:-10.20.30.202}"
readonly DB_PORT="${HDBPP_DB_PORT:-3307}"
readonly DB_USER="${HDBPP_DB_USER:-hdbpp_writer}"
readonly ENV_FILE="/etc/hdbpp/hdbpp.env"

read -r -s -p "Password for ${DB_USER}: " db_password
echo
if [[ ! "${db_password}" =~ ^[A-Za-z0-9._~!@%+=:,?-]{16,128}$ ]]; then
    echo "Password format does not match the database provisioning policy." >&2
    exit 1
fi

install -o root -g hdbpp -m 0640 /dev/null "${ENV_FILE}"
{
    printf 'TANGO_HOST=%s\n' "${TANGO_HOST_VALUE}"
    printf 'HDBPP_MYSQL_USER=%s\n' "${DB_USER}"
    printf 'HDBPP_MYSQL_PWD=%s\n' "${db_password}"
    printf 'LD_LIBRARY_PATH=/opt/hdbpp/lib:/opt/hdbpp/lib/x86_64-linux-gnu\n'
} >"${ENV_FILE}"
unset db_password

IFS=: read -r tango_host tango_port <<<"${TANGO_HOST_VALUE}"
timeout 3 bash -c "</dev/tcp/${tango_host}/${tango_port}"
timeout 3 bash -c "</dev/tcp/${DB_HOST}/${DB_PORT}"

systemctl enable --now elyse-tango-starter.service

systemctl --no-pager --full status elyse-tango-starter.service

vm_hostname=$(hostname -s)
for device in "tango/admin/${vm_hostname}" archiving/hdbpp/es01 archiving/hdbpp/cm; do
    ready=false
    for _ in $(seq 1 30); do
        if tango_admin --ping-device "${device}" >/dev/null 2>&1; then
            ready=true
            break
        fi
        sleep 1
    done
    if [[ "${ready}" != true ]]; then
        echo "Tango device did not become reachable: ${device}" >&2
        exit 1
    fi
done

echo "Starter and both HDB++ devices are reachable. No attributes are archived until explicitly added."
