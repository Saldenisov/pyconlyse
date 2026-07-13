#!/bin/zsh
set -e
cd "$(dirname "$0")"
conda run -n pyconlyse311 python avantes_dual_viewer.py
