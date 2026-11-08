#!/usr/bin/env bash
set -Eeuo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "Run this script with sudo." >&2
    exit 1
fi

readonly INSTALL_PREFIX="${INSTALL_PREFIX:-/opt/hdbpp}"
readonly SOURCE_ROOT="${SOURCE_ROOT:-/usr/local/src/hdbpp}"
readonly BUILD_JOBS="${BUILD_JOBS:-$(nproc)}"

# Revisions inspected against the ELYSE Tango deployment on 2026-09-01.
readonly LIBHDBPP_REF="08a2ac5a4a191572ff520eeea8eec6b7b80739f7"
readonly MYSQL_REF="f0a78829c3e76b06073655e547e7c73a16764c81"
readonly ES_REF="c2ed5aa18fcf8ba21a2568526d65e2b478fea2ef"
readonly CM_REF="f8a4cccdc6f202e7680b4234c6b0e27c4b60f25b"

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

clone_at() {
    local url="$1"
    local destination="$2"
    local revision="$3"

    if [[ -d "${destination}/.git" ]]; then
        git -C "${destination}" fetch --tags origin
    elif [[ -e "${destination}" ]]; then
        echo "Refusing to replace non-Git path ${destination}" >&2
        exit 1
    else
        git clone --filter=blob:none "${url}" "${destination}"
    fi
    git -C "${destination}" checkout --detach "${revision}"
}

apply_source_patch() {
    local source="$1"
    local patch_file="$2"

    if git -C "${source}" apply --reverse --check "${patch_file}" 2>/dev/null; then
        return
    fi
    git -C "${source}" apply --check "${patch_file}"
    git -C "${source}" apply "${patch_file}"
}

build_and_install() {
    local source="$1"
    shift
    cmake -S "${source}" -B "${source}/build-elyse" -G Ninja \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="${INSTALL_PREFIX}" \
        -DCMAKE_PREFIX_PATH="${INSTALL_PREFIX};/usr" \
        "$@"
    cmake --build "${source}/build-elyse" --parallel "${BUILD_JOBS}"
    cmake --install "${source}/build-elyse"
}

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y software-properties-common
add-apt-repository -y universe
apt-get update
apt-get install -y \
    build-essential \
    ca-certificates \
    cmake \
    git \
    libmariadb-dev \
    libomniorb4-dev \
    libtango-dev \
    libtango-tools \
    libzmq3-dev \
    mariadb-client \
    ninja-build \
    pkg-config \
    python3-tango \
    tango-starter

# Ubuntu enables its generic Starter unit during package installation. This VM
# uses the external ELYSE Tango database and a separately gated unit below, so
# keep the distribution unit disabled to preserve passive startup.
systemctl disable --now tango-starter.service 2>/dev/null || true

install -d -m 0755 "${SOURCE_ROOT}" "${INSTALL_PREFIX}"

clone_at \
    https://gitlab.com/tango-controls/hdbpp/libhdbpp.git \
    "${SOURCE_ROOT}/libhdbpp" \
    "${LIBHDBPP_REF}"
clone_at \
    https://gitlab.com/tango-controls/hdbpp/libhdbpp-mysql.git \
    "${SOURCE_ROOT}/libhdbpp-mysql" \
    "${MYSQL_REF}"
clone_at \
    https://gitlab.com/tango-controls/hdbpp/hdbpp-es.git \
    "${SOURCE_ROOT}/hdbpp-es" \
    "${ES_REF}"
clone_at \
    https://gitlab.com/tango-controls/hdbpp/hdbpp-cm.git \
    "${SOURCE_ROOT}/hdbpp-cm" \
    "${CM_REF}"

apply_source_patch \
    "${SOURCE_ROOT}/libhdbpp-mysql" \
    "${SCRIPT_DIR}/patches/libhdbpp-mysql-mariadb-and-read-scalar.patch"

build_and_install "${SOURCE_ROOT}/libhdbpp"
build_and_install "${SOURCE_ROOT}/libhdbpp-mysql"
build_and_install "${SOURCE_ROOT}/hdbpp-es" -DLIBHDBPP_BACKEND=mysql
build_and_install "${SOURCE_ROOT}/hdbpp-cm"

if ! getent group hdbpp >/dev/null; then
    groupadd --system hdbpp
fi
if ! id hdbpp >/dev/null 2>&1; then
    useradd --system --gid hdbpp --home-dir /var/lib/hdbpp --create-home --shell /usr/sbin/nologin hdbpp
fi

install -d -o root -g hdbpp -m 0750 /etc/hdbpp
install -d -o hdbpp -g hdbpp -m 0750 /var/lib/hdbpp
install -m 0644 "${SCRIPT_DIR}/systemd/elyse-tango-starter.service" /etc/systemd/system/

printf '%s\n' "${INSTALL_PREFIX}/lib" "${INSTALL_PREFIX}/lib/x86_64-linux-gnu" \
    >/etc/ld.so.conf.d/hdbpp.conf
ldconfig
systemctl daemon-reload

echo "HDB++ binaries installed at ${INSTALL_PREFIX}."
echo "The Tango Starter remains disabled until database initialization and Tango registration are complete."
