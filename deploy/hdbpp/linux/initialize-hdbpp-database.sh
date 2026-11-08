#!/usr/bin/env bash
set -Eeuo pipefail

readonly DB_HOST="${HDBPP_DB_HOST:-10.20.30.202}"
readonly DB_PORT="${HDBPP_DB_PORT:-3307}"
readonly DB_NAME="${HDBPP_DB_NAME:-hdbpp}"
readonly DB_USER="${HDBPP_DB_USER:-hdbpp_writer}"
readonly SCHEMA_FILE="${HDBPP_SCHEMA_FILE:-/usr/local/src/hdbpp/libhdbpp-mysql/etc/create_hdb++_mysql_innodb_json.sql}"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <Ubuntu-VM-IPv4-address>" >&2
    exit 2
fi
readonly VM_IP="$1"
if [[ ! "${VM_IP}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Invalid VM IPv4 address: ${VM_IP}" >&2
    exit 2
fi
if [[ ! -r "${SCHEMA_FILE}" ]]; then
    echo "HDB++ schema is missing: ${SCHEMA_FILE}" >&2
    exit 1
fi

read -r -s -p "Existing password for ${DB_USER}@${VM_IP}: " db_password
echo
if [[ ! "${db_password}" =~ ^[A-Za-z0-9._~!@%+=:,?-]{16,128}$ ]]; then
    echo "Password format does not match the Windows provisioning policy." >&2
    exit 1
fi

echo "Importing the official HDB++ InnoDB/JSON schema."
MYSQL_PWD="${db_password}" mariadb --protocol=tcp \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --user="${DB_USER}" \
    "${DB_NAME}" <"${SCHEMA_FILE}"
unset db_password

echo "Database initialized. The services are still disabled."
