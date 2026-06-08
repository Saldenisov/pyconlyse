#!/bin/zsh
set -e
cd "$(dirname "$0")"
export AVANTES_EMULATOR=1
export AVANTES_DEMO_KINETICS=1
export AVANTES_DEMO_DURATION_S=40
export AVANTES_DEMO_MAX_OD=0.95
conda run -n pyconlyse39 python avantes_dual_viewer.py
