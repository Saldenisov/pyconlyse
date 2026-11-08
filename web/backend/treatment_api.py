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
CALC_MODES = ["individual", "averaged"]
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

from treatment_parallel import (
    _cpu_executor,
    _cpu_progress_callback,
    _run_parallel_cpu_jobs,
)
from treatment_path_policy import (
    _is_within_local_path,
    _infer_time_scale_from_path,
    _is_within_allowed_root,
    _ensure_within_allowed_root,
    _ensure_readable_treatment_file,
    _ensure_writable_output_folder,
    _mapped_smb_local_file,
    _mapped_smb_local_dir,
    _default_folder,
    _folder_exists,
    _root_exists,
    _clear_root_exists_cache,
    _default_state,
    _file_data_type_candidate,
    _candidate_rank,
    _default_save_target_for_folder,
    _dated_save_file_name_for_folder,
    _folder_contains,
    _save_folder_for_measurement,
    _path_name,
    _path_suffix,
    _candidate_sort_key,
    _folder_input_candidates,
    _convert_sort_key,
    _folder_required_input_types,
)
from treatment_stitch_routes import (
    _stitch_od_roots,
    _is_within_stitch_od_root,
    _ensure_readable_od_dat,
    _stitch_time_regions,
    _stitch_coefficients,
    _default_stitched_output_name,
    _stitch_manifest_path,
    _write_stitch_manifest,
    _run_with_local_stitch_inputs,
    stitch_od_dat_files,
    preview_stitch_od_dat_files,
)
from treatment_conversion_jobs import (
    _compressed_h5_reuse_summary,
    _convert_source_to_h5,
    _convert_folder_source_worker,
    _convert_staged_h5_worker,
    _convert_smb_sources_to_h5_pipeline,
    _convert_source_to_h5_legacy,
    _smb_size_bytes,
    _compression_job_snapshot,
    _folder_set_job_snapshot,
    _update_compression_job,
    _update_folder_set_job,
    _validate_canonical_h5,
    _compression_progress_summary,
    _run_compression_job,
)
from treatment_cleaning_routes import (
    _delete_source_his_after_cleaning,
    analyze_sam_cleaning,
    get_sam_cleaning_view,
    reset_sam_cleaning,
    restore_sam_cleaning,
    save_sam_cleaning,
    save_sam_cleaning_for_file,
)
from treatment_file_routes import (
    _cache_assignable_source,
    compress_file_path,
    start_compress_file_path,
    get_compress_file_status,
    list_files,
    get_file_info,
    get_file_summary,
    preview_file,
    average_noise,
    open_dat_preview,
    get_selection,
    export_selection_average,
)
from treatment_session_store import (
    TreatmentSessionStore,
)
from treatment_session_routes import (
    _current_session_id,
    _session_payload,
    _active_assignable_data_type,
    _auto_calc_od_if_ready,
    _json_response,
    _error,
    get_session,
    reset_session,
    _saved_session_profile,
    _saved_session_browser,
    saved_treatment_sessions,
    copy_treatment_session,
    restore_session_from_browser,
    update_session_config,
    update_session_root,
    set_session_folder,
    set_session_path,
    cache_and_set_session_path,
    compress_and_set_session_path,
    auto_assign_session_paths,
    update_session_selection,
    calc_abs,
    save_result,
)
from treatment_queue_planning import (
    _map_selection_status,
    _queue_required_paths,
    _queue_input_fingerprint,
    _queue_output_path,
    _configured_result_output_path,
    _result_output_exists,
    _renamed_queue_output_path,
    _rename_result_output,
    _save_queued_result,
    _queue_preflight,
    _queue_convert_plan,
    _queue_cleaning_plan,
    _queue_recipe,
    _queue_standard_folder_recipe,
)
from treatment_queue_execution import (
    _queue_assign_job_path,
    _queue_cleaning_output_name,
    _tree_cleaning_sources,
    _tree_cleaning_for_calculation,
    _queue_artifact_path,
    _queue_convert_to_job_h5,
    _queue_convert_worker,
    _queue_clean_worker,
    _execute_standard_folder_queue_job,
    _execute_treatment_queue_job,
)
from treatment_folder_routes import (
    _set_inputs_from_folder_job_payload,
    _run_folder_set_job,
    set_inputs_from_folder,
    start_folder_set,
    get_folder_set_status,
)
from treatment_queue_routes import (
    _vd2_manifest_plan,
    preview_vd2_manifest,
    queue_vd2_manifest,
    get_treatment_queue,
    enqueue_treatment_queue_job,
    enqueue_standard_folder_queue_job,
    run_treatment_queue,
    remove_treatment_queue_job,
)


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
session_store = TreatmentSessionStore(_state_repository)
treatment_service = TreatmentDataService()
treatment_queue_store = TreatmentQueueStore(_state_repository)


treatment_api.route("/session", methods=["GET"])(get_session)
treatment_api.route("/session/reset", methods=["POST"])(reset_session)
treatment_api.get("/session/saved")(saved_treatment_sessions)
treatment_api.post("/session/copy")(copy_treatment_session)
treatment_api.route("/session/restore", methods=["POST"])(restore_session_from_browser)
treatment_api.route("/session/config", methods=["POST"])(update_session_config)
treatment_api.route("/session/root", methods=["POST"])(update_session_root)
treatment_api.route("/session/folder", methods=["POST"])(set_session_folder)
treatment_api.route("/session/folder-set", methods=["POST"])(set_inputs_from_folder)
treatment_api.route("/session/folder-set/start", methods=["POST"])(start_folder_set)
treatment_api.route("/session/folder-set/status/<job_id>", methods=["GET"])(get_folder_set_status)
treatment_api.route("/session/path", methods=["POST"])(set_session_path)
treatment_api.route("/session/cache-path", methods=["POST"])(cache_and_set_session_path)
treatment_api.route("/session/compress-path", methods=["POST"])(compress_and_set_session_path)
treatment_api.route("/session/compress-file", methods=["POST"])(compress_file_path)
treatment_api.route("/session/compress-file/start", methods=["POST"])(start_compress_file_path)
treatment_api.route("/session/compress-file/status/<job_id>", methods=["GET"])(get_compress_file_status)
treatment_api.route("/session/auto-assign", methods=["POST"])(auto_assign_session_paths)
treatment_api.route("/session/selection", methods=["POST"])(update_session_selection)
treatment_api.route("/files", methods=["GET"])(list_files)
treatment_api.route("/file-info", methods=["GET"])(get_file_info)
treatment_api.route("/file-summary", methods=["GET"])(get_file_summary)
treatment_api.route("/preview", methods=["GET"])(preview_file)
treatment_api.route("/average-noise", methods=["POST"])(average_noise)
treatment_api.route("/preview/dat", methods=["POST"])(open_dat_preview)
treatment_api.route("/selection", methods=["GET"])(get_selection)
treatment_api.route("/selection/export", methods=["POST"])(export_selection_average)
treatment_api.route("/cleaning/sam", methods=["POST"])(analyze_sam_cleaning)
treatment_api.route("/cleaning/view", methods=["GET"])(get_sam_cleaning_view)
treatment_api.route("/cleaning/reset", methods=["POST"])(reset_sam_cleaning)
treatment_api.route("/cleaning/restore", methods=["POST"])(restore_sam_cleaning)
treatment_api.route("/cleaning/save", methods=["POST"])(save_sam_cleaning)
treatment_api.route("/cleaning/file/save", methods=["POST"])(save_sam_cleaning_for_file)
treatment_api.route("/manifest/vd2", methods=["POST"])(preview_vd2_manifest)
treatment_api.route("/manifest/vd2/queue", methods=["POST"])(queue_vd2_manifest)
treatment_api.route("/queue", methods=["GET"])(get_treatment_queue)
treatment_api.route("/queue", methods=["POST"])(enqueue_treatment_queue_job)
treatment_api.route("/queue/folder-set", methods=["POST"])(enqueue_standard_folder_queue_job)
treatment_api.route("/queue/run", methods=["POST"])(run_treatment_queue)
treatment_api.route("/queue/<job_id>", methods=["DELETE"])(remove_treatment_queue_job)
treatment_api.route("/stitch/od", methods=["POST"])(stitch_od_dat_files)
treatment_api.route("/stitch/od/preview", methods=["POST"])(preview_stitch_od_dat_files)
treatment_api.route("/calc-abs", methods=["POST"])(calc_abs)
treatment_api.route("/save", methods=["POST"])(save_result)
