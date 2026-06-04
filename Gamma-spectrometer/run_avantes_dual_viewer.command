#!/bin/zsh
set -e
cd "$(dirname "$0")"
conda run -n pyconlyse39 python avantes_dual_viewer.py
