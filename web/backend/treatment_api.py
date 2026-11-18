"""Treatment API, shared session state and Windows spawn entry points."""

import sys as _sys
from treatment_api_parallel import bind as _bind_parallel
from treatment_api_paths import bind as _bind_paths
from treatment_api_stitching import bind as _bind_stitching
from treatment_api_inputs import bind as _bind_inputs
from treatment_api_conversion import bind as _bind_conversion
from treatment_api_smb_conversion import bind as _bind_smb_conversion
from treatment_api_sessions import bind as _bind_sessions
from treatment_api_compression_jobs import bind as _bind_compression_jobs
from treatment_api_queue_recipes import bind as _bind_queue_recipes
from treatment_api_queue_execution import bind as _bind_queue_execution
from treatment_api_folder_jobs import bind as _bind_folder_jobs
from treatment_api_file_routes import bind as _bind_file_routes
from treatment_api_cleaning_routes import bind as _bind_cleaning_routes
from treatment_api_queue_routes import bind as _bind_queue_routes

import json
import math
import os
import re
import tempfile
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, ThreadPoolExecutor, wait
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
from threading import Lock, Thread
from time import monotonic
from typing import Dict, List, Optional
from uuid import uuid4

from flask import Blueprint, jsonify, request
from folder_api import (
    get_allowed_root,
    get_treatment_root_base,
    get_treatment_root_bases,
    set_allowed_root,
)
from mutation_auth import install_mutation_auth
from treatment_file_cache import (
    cache_external_file,
    cache_file,
    get_cache_limit_bytes,
    get_cache_root,
    is_within_cache,
)
from treatment_manifest import record_treatment_manifest
from vd2_project_manifest import inspect_project, fingerprint as vd2_fingerprint, record_project_treatment
from treatment_network_path import (
    copy_local_file_to_smb_atomic,
    copy_smb_file_to_local,
    is_mapped_smb_path,
    is_smb_path,
    normalize_smb_path,
    normalize_treatment_path as _normalize_path,
    smb_is_within,
    smb_isdir,
    smb_isfile,
    smb_join,
    smb_listdir,
    smb_name,
    smb_parent,
    smb_rename,
    smb_remove,
    smb_suffix,
    smb_to_local_path,
)
from treatment_queue_store import (
    TreatmentQueueStore,
    _treatment_thread_context,
    _treatment_worker_count,
)
from treatment_service import TreatmentDataService, h5py
from treatment_spectral_od import SPECTRAL_MODES, SPECTRAL_SUM, reference_window
from treatment_state_repository import TreatmentStateRepository
from browser_workspace_state import workspace_identity

treatment_api = Blueprint("treatment_api", __name__, url_prefix="/api/treatment")
install_mutation_auth(treatment_api)

EXP_TYPES = ["HIS", "HIS+NOISE", "ABS+BASE+NOISE"]
DATA_TYPES = [
    "ABS",
    "BASE",
    "NOISE",
    "ABS+BASE",
    "ABS+BASE+NOISE",
]
CALC_MODES = ["individual", "averaged", *SPECTRAL_MODES]
QUEUE_CLEANING_STATES = {"not_requested", "applied", "pending"}
REQUIRED_DATA_TYPES = {
    "HIS": ["ABS+BASE+NOISE"],
    "HIS+NOISE": ["ABS+BASE", "NOISE"],
    "ABS+BASE+NOISE": ["ABS", "BASE", "NOISE"],
}
TREATMENT_SESSION_COOKIE = "pyconlyse_treatment_sid"
ROOT_EXISTS_CACHE_TTL_SECONDS = 15.0
_root_exists_cache: Dict[str, tuple] = {}
_root_exists_cache_lock = Lock()
_compression_jobs: Dict[str, Dict[str, object]] = {}
_compression_jobs_lock = Lock()
_folder_set_jobs: Dict[str, Dict[str, object]] = {}
_folder_set_jobs_lock = Lock()
_folder_set_session_jobs: Dict[str, str] = {}
TIME_SCALE_PATH_RE = re.compile(
    r"(?<![A-Za-z])(?:\d+(?:\.\d+)?)\s*(fs|ps|ns|us|µs|ms|s)(?![A-Za-z])",
    re.IGNORECASE,
)
DEFAULT_STITCH_OD_ROOTS = (
    "smb://10.20.30.202/f/DATA_VD2",
    "smb://10.20.30.202/F/DATA_VD2",
)


# Feature modules share this module's runtime and compatibility exports.
_api = _sys.modules[__name__]
_bind_parallel(_api)


_bind_paths(_api)


_bind_stitching(_api)


_bind_sessions(_api)


_bind_inputs(_api)


_bind_conversion(_api)


def _convert_folder_source_worker(data_type: str, source_path: str, progress_queue):
    def report(*args):
        if progress_queue is not None:
            progress_queue.put((data_type, *args))

    return _api._convert_source_to_h5(
        source_path,
        progress_callback=report if progress_queue is not None else None,
    )


def _convert_staged_h5_worker(data_type: str, source_path: str, output_path: str, progress_queue):
    summary = treatment_service.convert_file_to_h5(
        Path(source_path),
        Path(output_path),
        progress_callback=_api._cpu_progress_callback(data_type, progress_queue),
    )
    output = Path(output_path)
    if not output.is_file():
        raise ValueError(f"Compressed H5 was not created: {output}")
    summary["output_size_bytes"] = int(output.stat().st_size)
    return summary


_bind_smb_conversion(_api)


_bind_compression_jobs(_api)


_state_database_path = os.environ.get("PYCONLYSE_TREATMENT_STATE_DB", "").strip()
_state_repository = (
    TreatmentStateRepository(_state_database_path) if _state_database_path else None
)
_root_restore_error = ""
if _state_repository:
    _persisted_root = _state_repository.get_setting("allowed_root")
    if _persisted_root:
        try:
            set_allowed_root(_persisted_root)
        except ValueError as exc:
            _root_restore_error = str(exc)
session_store = _api.TreatmentSessionStore(_state_repository)
treatment_service = TreatmentDataService()
treatment_queue_store = TreatmentQueueStore(_state_repository)


_bind_queue_recipes(_api)


_bind_queue_execution(_api)


def _queue_convert_worker(data_type: str, job_state: Dict[str, object], job_id: str, _progress_queue):
    return _api._queue_convert_to_job_h5(job_state, data_type, job_id)


def _queue_clean_worker(
    data_type: str,
    session_state: Dict[str, object],
    angle_threshold: float,
    surface_threshold: float,
    output_file_name: str,
    _progress_queue,
):
    """Clean one independent role in its own process and service runtime."""
    role_state = deepcopy(session_state)
    role_state["active_data_type"] = data_type
    return TreatmentDataService().save_sam_cleaned_h5(
        f"clean:{uuid4()}",
        role_state,
        angle_threshold,
        surface_threshold,
        output_file_name=output_file_name,
    )


treatment_api.route("/session", methods=["GET"])(_api.get_session)
treatment_api.route("/session/reset", methods=["POST"])(_api.reset_session)
treatment_api.get("/session/saved")(_api.saved_treatment_sessions)
treatment_api.post("/session/copy")(_api.copy_treatment_session)
treatment_api.route("/session/restore", methods=["POST"])(_api.restore_session_from_browser)
treatment_api.route("/session/config", methods=["POST"])(_api.update_session_config)
treatment_api.route("/session/root", methods=["POST"])(_api.update_session_root)
treatment_api.route("/session/folder", methods=["POST"])(_api.set_session_folder)


_bind_folder_jobs(_api)


treatment_api.route("/session/folder-set", methods=["POST"])(_api.set_inputs_from_folder)
treatment_api.route("/session/folder-set/start", methods=["POST"])(_api.start_folder_set)
treatment_api.route("/session/folder-set/status/<job_id>", methods=["GET"])(_api.get_folder_set_status)


_bind_file_routes(_api)
treatment_api.route("/session/path", methods=["POST"])(_api.set_session_path)
treatment_api.route("/session/cache-path", methods=["POST"])(_api.cache_and_set_session_path)
treatment_api.route("/session/compress-path", methods=["POST"])(_api.compress_and_set_session_path)
treatment_api.route("/session/compress-file", methods=["POST"])(_api.compress_file_path)
treatment_api.route("/session/compress-file/start", methods=["POST"])(_api.start_compress_file_path)
treatment_api.route("/session/compress-file/status/<job_id>", methods=["GET"])(_api.get_compress_file_status)
treatment_api.route("/session/auto-assign", methods=["POST"])(_api.auto_assign_session_paths)
treatment_api.route("/session/selection", methods=["POST"])(_api.update_session_selection)
treatment_api.route("/files", methods=["GET"])(_api.list_files)
treatment_api.route("/file-info", methods=["GET"])(_api.get_file_info)
treatment_api.route("/file-summary", methods=["GET"])(_api.get_file_summary)
treatment_api.route("/preview", methods=["GET"])(_api.preview_file)
treatment_api.route("/average-noise", methods=["POST"])(_api.average_noise)
treatment_api.route("/preview/dat", methods=["POST"])(_api.open_dat_preview)
treatment_api.route("/selection", methods=["GET"])(_api.get_selection)
treatment_api.route("/selection/export", methods=["POST"])(_api.export_selection_average)


_bind_cleaning_routes(_api)
treatment_api.route("/cleaning/sam", methods=["POST"])(_api.analyze_sam_cleaning)
treatment_api.route("/cleaning/view", methods=["GET"])(_api.get_sam_cleaning_view)
treatment_api.route("/cleaning/reset", methods=["POST"])(_api.reset_sam_cleaning)
treatment_api.route("/cleaning/restore", methods=["POST"])(_api.restore_sam_cleaning)
treatment_api.route("/cleaning/save", methods=["POST"])(_api.save_sam_cleaning)
treatment_api.route("/cleaning/file/save", methods=["POST"])(_api.save_sam_cleaning_for_file)


_bind_queue_routes(_api)


treatment_api.route("/manifest/vd2", methods=["POST"])(_api.preview_vd2_manifest)
treatment_api.route("/manifest/vd2/abs-preview", methods=["POST"])(_api.preview_vd2_manifest_abs)
treatment_api.route("/manifest/vd2/queue", methods=["POST"])(_api.queue_vd2_manifest)
treatment_api.route("/queue", methods=["GET"])(_api.get_treatment_queue)
treatment_api.route("/queue", methods=["POST"])(_api.enqueue_treatment_queue_job)
treatment_api.route("/queue/folder-set", methods=["POST"])(_api.enqueue_standard_folder_queue_job)
treatment_api.route("/queue/run", methods=["POST"])(_api.run_treatment_queue)
treatment_api.route("/queue/<job_id>", methods=["DELETE"])(_api.remove_treatment_queue_job)
treatment_api.route("/stitch/od", methods=["POST"])(_api.stitch_od_dat_files)
treatment_api.route("/stitch/od/preview", methods=["POST"])(_api.preview_stitch_od_dat_files)


@treatment_api.route("/calc-abs", methods=["POST"])
def calc_abs():
    session_id = _api._current_session_id()
    try:
        if treatment_service.runtime_status(session_id).get("cleaning_ready"):
            raise ValueError(
                "Cleaning preview is not applied; apply mask to H5 or reset preview."
            )
        result = treatment_service.calc_abs(session_id, session_store.snapshot(session_id))
        session_store.mark_result_ready(session_id, True)
        session_store.update_selection(session_id, {"active_data_type": "OD", "map_index": 0})
    except ValueError as exc:
        return _api._error(str(exc), session_id)

    payload = _api._session_payload(session_id)
    payload["result"] = result
    return _api._json_response(payload, session_id)


@treatment_api.route("/save", methods=["POST"])
def save_result():
    session_id = _api._current_session_id()
    session_state = session_store.snapshot(session_id)
    output_path = _api._configured_result_output_path(session_state)
    reservation_owner = None
    try:
        reservation_owner = treatment_queue_store.reserve_immediate_output(output_path)
        saved = treatment_service.save_result(session_id, session_state)
        record_treatment_manifest(
            saved,
            session_state=session_state,
            workflow={"kind": "immediate"},
        )
    except (ValueError, OSError) as exc:
        return _api._error(str(exc), session_id)
    finally:
        treatment_queue_store.release_immediate_output(output_path, reservation_owner)

    payload = _api._session_payload(session_id)
    payload["saved"] = saved
    return _api._json_response(payload, session_id)
