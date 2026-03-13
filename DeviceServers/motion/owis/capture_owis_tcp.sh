#!/usr/bin/env bash
set -euo pipefail

HOST="10.20.30.134"
PORT="8777"
IFACE=""
OUTFILE=""
OUTDIR="$PWD/captures"

usage() {
  cat <<'EOF'
Usage:
  ./capture_owis_tcp.sh [-i interface] [-H host] [-p port] [-o output.pcapng]

Options:
  -i  Network interface (example: en0). If omitted, auto-detected by route to host.
  -H  OWIS controller IP (default: 10.20.30.134)
  -p  OWIS TCP port (default: 8777)
  -o  Output pcapng file path (default: ./captures/owis_tcp_<timestamp>.pcapng)
  -h  Show help

Examples:
  ./capture_owis_tcp.sh
  ./capture_owis_tcp.sh -i en0
  ./capture_owis_tcp.sh -H 10.20.30.134 -p 8777 -o /tmp/owis_axis2_ok.pcapng
EOF
}

while getopts ":i:H:p:o:h" opt; do
  case "$opt" in
    i) IFACE="$OPTARG" ;;
    H) HOST="$OPTARG" ;;
    p) PORT="$OPTARG" ;;
    o) OUTFILE="$OPTARG" ;;
    h)
      usage
      exit 0
      ;;
    :)
      echo "ERROR: Option -$OPTARG requires an argument." >&2
      usage
      exit 1
      ;;
    \?)
      echo "ERROR: Unknown option: -$OPTARG" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v tshark >/dev/null 2>&1; then
  cat <<'EOF' >&2
ERROR: tshark is not installed.

Install on macOS:
  brew update
  brew install wireshark
  sudo dseditgroup -o edit -a "$USER" -t user access_bpf

Then restart terminal/login and run this script again.
EOF
  exit 1
fi

if [[ -z "$IFACE" ]]; then
  IFACE="$(route -n get "$HOST" 2>/dev/null | awk '/interface:/{print $2; exit}')"
fi

if [[ -z "$IFACE" ]]; then
  echo "ERROR: Could not auto-detect network interface for host $HOST." >&2
  echo "Available interfaces:" >&2
  tshark -D >&2 || true
  echo "Run with -i <interface>." >&2
  exit 1
fi

if [[ -z "$OUTFILE" ]]; then
  mkdir -p "$OUTDIR"
  ts="$(date +"%Y%m%d_%H%M%S")"
  OUTFILE="$OUTDIR/owis_tcp_${HOST}_${PORT}_${ts}.pcapng"
fi

FILTER="host ${HOST} and tcp port ${PORT}"

cat <<EOF
Starting OWIS capture
  interface : $IFACE
  host      : $HOST
  port      : $PORT
  filter    : $FILTER
  output    : $OUTFILE

Press Ctrl+C to stop capture.
EOF

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Note: if capture permission fails, run with sudo or configure access_bpf group."
fi

tshark -n -i "$IFACE" -f "$FILTER" -w "$OUTFILE"
