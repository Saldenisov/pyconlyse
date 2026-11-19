import sys as _sys
from pump_probe_v0_api_hardware import bind as _bind_hardware
from pump_probe_v0_api_files import bind as _bind_files
from pump_probe_v0_api_controller import bind as _bind_controller
from pump_probe_v0_api_lifecycle import bind as _bind_lifecycle
from pump_probe_v0_api_routes import bind as _bind_routes

import ast
import math
import os
import random
import json
import hashlib
import shutil
import threading
import time
import zlib
import uuid
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import unquote

import numpy as np

from flask import Blueprint, Response, jsonify, request

from mutation_auth import install_mutation_auth
from hardware_authorization import authorization_required, require_http_hardware
from experiment_readiness import EXPERIMENT_MUTATION_LOCK, recover_device, start_managed_server
from experiment_lifecycle import ExperimentLifecycle
from v0_experiment_shutdown import (
    CAMERA as V0_SHUTDOWN_CAMERA, OUTPUT_PLAN as V0_SHUTDOWN_OUTPUT_PLAN,
    STAGE as V0_SHUTDOWN_STAGE, STAGE_BACKEND as V0_SHUTDOWN_STAGE_BACKEND,
    STAGE_AXIS as V0_SHUTDOWN_STAGE_AXIS, STAGE_TOLERANCE_MM as V0_SHUTDOWN_STAGE_TOLERANCE,
    STAGE_TIMEOUT_S as V0_SHUTDOWN_STAGE_TIMEOUT, execute_shutdown as execute_v0_shutdown,
)
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
    REQUIRED_NETIO_OUTPUTS as REQUIRED_NETIO_OUTPUTS,
    SIGNAL_RANDOM_COUNTS,
    SPECTROMETER_BURST,
    SPECTROMETER_HZ,
    STAGE_MAX_MM,
    STAGE_MIN_MM,
    STAGE_SPEED_MM_PER_SEC,
    V0_CAMERA_DEVICES,
    V0_LASER_POINTING_DEVICES,
    V0_PDU_DEVICES,
    V0_STANDA_DEVICES,
    V0_STARTER_DEVICE,
    V0_STANDA_STARTER_DEVICE,
    V0_PREPARATION_NETIO_OUTPUTS,
    V0_PREPARATION_PDU_DEVICES,
    V0_PREPARATION_READ_ONLY,
)
from pump_probe_v0_dataset import (
    derive_dataset, export_dat, load_payload, treat_dataset, treat_derived_dataset,
)
from pump_probe_v0_delays import preview_kinetics, resolve_scan_settings
from pump_probe_v0_storage import RAW_GROUPS, V0EmulatorRunWriter, V0TangoRunWriter
from pump_probe_v0_scanplan import build_scan_plan
from pump_probe_v0_processing import TRANCON_GROUPS, TRANCON_FLOAT_LAYOUT as TRANCON_FLOAT_LAYOUT
from pump_probe_v0_tango import AcquisitionCancelled, RejectedCycle as RejectedCycle, TangoPacketError, TangoRawAdapter
from pump_probe_v0_tango_plan import build_tango_plan, load_profile
from pump_probe_v0_detector_filters import apply_detector_filters

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


class TangoProfileNotCommissioned(ValueError):
    pass


_bind_hardware(_sys.modules[__name__])


def _linspace(start, stop, count):
    if count <= 1:
        return [float(start)]
    step = (stop - start) / (count - 1)
    return [float(start + index * step) for index in range(count)]


def _gaussian(x_value, center, width):
    scaled = (x_value - center) / width
    return math.exp(-0.5 * scaled * scaled)


_bind_files(_sys.modules[__name__])


_bind_controller(_sys.modules[__name__])


_emulator = PumpProbeV0Controller()
_v0_lifecycle_instance = None
_v0_lifecycle_factory_lock = threading.Lock()


def _v0_lifecycle():
    global _v0_lifecycle_instance
    with _v0_lifecycle_factory_lock:
        if _v0_lifecycle_instance is None:
            path = os.environ.get("PYCONLYSE_V0_EXPERIMENT_STATE_DB") or str(Path.home() / ".pyconlyse" / "experiment_preparation_v0.sqlite3")
            _v0_lifecycle_instance = ExperimentLifecycle(path, experiment="V0")
        return _v0_lifecycle_instance


_bind_lifecycle(_sys.modules[__name__])


_bind_routes(_sys.modules[__name__])
pump_probe_state = (pump_probe_v0_api.route("/state", methods=["GET"]))(pump_probe_state)


pump_probe_configure = (pump_probe_v0_api.route("/config", methods=["POST"]))(pump_probe_configure)


pump_probe_hardware_config = (pump_probe_v0_api.route("/hardware-config", methods=["GET", "POST"]))(pump_probe_hardware_config)


pump_probe_hardware_preflight = (pump_probe_v0_api.route("/hardware/preflight", methods=["GET", "POST"]))(pump_probe_hardware_preflight)


pump_probe_hardware_initialize = (pump_probe_v0_api.route("/hardware/initialize", methods=["POST"]))(pump_probe_hardware_initialize)


v0_lifecycle_state = (pump_probe_v0_api.route("/lifecycle", methods=["GET"]))(v0_lifecycle_state)


v0_lifecycle_log = (pump_probe_v0_api.route("/lifecycle/log", methods=["GET"]))(v0_lifecycle_log)


v0_deinitialize = (pump_probe_v0_api.route("/deinitialize", methods=["POST"]))(v0_deinitialize)


pump_probe_tango_plan = (pump_probe_v0_api.route("/run/plan", methods=["POST"]))(pump_probe_tango_plan)


pump_probe_andor_snapshot = (pump_probe_v0_api.route("/commissioning/andor-snapshot", methods=["POST"]))((_serialized_v0_mutation)(pump_probe_andor_snapshot))


pump_probe_run = (pump_probe_v0_api.route("/run", methods=["POST"]))((_serialized_v0_mutation)(pump_probe_run))


pump_probe_realtime = (pump_probe_v0_api.route("/realtime", methods=["POST"]))((_serialized_v0_mutation)(pump_probe_realtime))


pump_probe_faraday = (pump_probe_v0_api.route("/faraday", methods=["POST"]))(pump_probe_faraday)


pump_probe_stage_move = (pump_probe_v0_api.route("/stage/move", methods=["POST"]))((_serialized_v0_mutation)(pump_probe_stage_move))


pump_probe_stage_stop = (pump_probe_v0_api.route("/stage/stop", methods=["POST"]))((_serialized_v0_mutation)(pump_probe_stage_stop))


pump_probe_sample_stage_move = (pump_probe_v0_api.route("/sample-stage/move", methods=["POST"]))((_serialized_v0_mutation)(pump_probe_sample_stage_move))


pump_probe_sample_stage_stop = (pump_probe_v0_api.route("/sample-stage/stop", methods=["POST"]))((_serialized_v0_mutation)(pump_probe_sample_stage_stop))


pump_probe_crystal_move = (pump_probe_v0_api.route("/crystal/move", methods=["POST"]))(pump_probe_crystal_move)


pump_probe_reset = (pump_probe_v0_api.route("/reset", methods=["POST"]))(pump_probe_reset)


pump_probe_data_list = (pump_probe_v0_api.route("/data/list", methods=["GET"]))(pump_probe_data_list)


pump_probe_data_create_folder = (pump_probe_v0_api.route("/data/folder", methods=["POST"]))(pump_probe_data_create_folder)


pump_probe_data_load = (pump_probe_v0_api.route("/data/load", methods=["POST"]))(pump_probe_data_load)


pump_probe_data_treat = (pump_probe_v0_api.route("/data/treat", methods=["POST"]))(pump_probe_data_treat)


pump_probe_data_derive = (pump_probe_v0_api.route("/data/derive", methods=["POST"]))(pump_probe_data_derive)
