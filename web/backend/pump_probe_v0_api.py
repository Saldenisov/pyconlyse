"""V0 experiment API and shared controller state."""

import sys as _sys
from pump_probe_v0_api_hardware import bind as _bind_hardware
from pump_probe_v0_api_files import bind as _bind_files
from pump_probe_v0_api_controller import bind as _bind_controller
from pump_probe_v0_api_routes import bind as _bind_routes

import ast
import math
import os
import random
import json
import shutil
import threading
import time
import zlib
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from flask import Blueprint, jsonify, request

from mutation_auth import install_mutation_auth
from hardware_authorization import authorization_required, require_http_hardware
from pump_probe_v0_config import (
    ACCELERATOR_HZ,
    BACKGROUND_RANDOM_COUNTS,
    DARK_DRIFT_COUNTS,
    DEFAULT_DATA_ROOT,
    DEFAULT_DG645_RECALL_CONFIG,
    DEFAULT_HARDWARE_CONFIG,
    LAMP_DRIFT_FRACTION,
    MM_PER_PS,
    OD_COMMON_OSCILLATION,
    OD_NOISE_SCALE,
    PIXELS,
    READ_NOISE_COUNTS,
    REFERENCE_RANDOM_COUNTS,
    REQUIRED_NETIO_OUTPUTS,
    SIGNAL_RANDOM_COUNTS,
    SPECTROMETER_BURST,
    SPECTROMETER_HZ,
    STAGE_MAX_MM,
    STAGE_MIN_MM,
    STAGE_SPEED_MM_PER_SEC,
)
from pump_probe_v0_data import parse_dat_payload, parse_h5_payload, parse_zip_payload
from pump_probe_v0_storage import RAW_GROUPS, V0EmulatorRunWriter

from treatment_network_path import (
    is_smb_path,
    normalize_smb_path,
    smb_is_within,
    smb_join,
    smb_listdir,
    smb_parent,
    smb_to_unc,
    split_smb_path,
)


pump_probe_v0_api = Blueprint("pump_probe_v0_api", __name__, url_prefix="/api/pump-probe-v0")
install_mutation_auth(pump_probe_v0_api)


# Feature modules share this module's runtime and compatibility exports.
_api = _sys.modules[__name__]
_bind_hardware(_api)


def _linspace(start, stop, count):
    if count <= 1:
        return [float(start)]
    step = (stop - start) / (count - 1)
    return [float(start + index * step) for index in range(count)]


def _gaussian(x_value, center, width):
    scaled = (x_value - center) / width
    return math.exp(-0.5 * scaled * scaled)


_bind_files(_api)


_bind_controller(_api)


_emulator = _api.PumpProbeV0Controller()


_bind_routes(_api)
pump_probe_v0_api.route("/state", methods=["GET"])(_api.pump_probe_state)
pump_probe_v0_api.route("/config", methods=["POST"])(_api.pump_probe_configure)
pump_probe_v0_api.route("/hardware-config", methods=["GET", "POST"])(_api.pump_probe_hardware_config)
pump_probe_v0_api.route("/hardware/preflight", methods=["GET", "POST"])(_api.pump_probe_hardware_preflight)
pump_probe_v0_api.route("/hardware/initialize", methods=["POST"])(_api.pump_probe_hardware_initialize)
pump_probe_v0_api.route("/run", methods=["POST"])(_api.pump_probe_run)
pump_probe_v0_api.route("/realtime", methods=["POST"])(_api.pump_probe_realtime)
pump_probe_v0_api.route("/faraday", methods=["POST"])(_api.pump_probe_faraday)
pump_probe_v0_api.route("/stage/move", methods=["POST"])(_api.pump_probe_stage_move)
pump_probe_v0_api.route("/stage/stop", methods=["POST"])(_api.pump_probe_stage_stop)
pump_probe_v0_api.route("/sample-stage/move", methods=["POST"])(_api.pump_probe_sample_stage_move)
pump_probe_v0_api.route("/sample-stage/stop", methods=["POST"])(_api.pump_probe_sample_stage_stop)
pump_probe_v0_api.route("/crystal/move", methods=["POST"])(_api.pump_probe_crystal_move)
pump_probe_v0_api.route("/reset", methods=["POST"])(_api.pump_probe_reset)
pump_probe_v0_api.route("/data/list", methods=["GET"])(_api.pump_probe_data_list)
pump_probe_v0_api.route("/data/folder", methods=["POST"])(_api.pump_probe_data_create_folder)
pump_probe_v0_api.route("/data/load", methods=["POST"])(_api.pump_probe_data_load)
