import os
import tempfile
from pathlib import Path
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
from treatment_file_cache import (
    cache_file,
    cache_external_file,
    get_cache_limit_bytes,
    get_cache_root,
    is_within_cache,
)
from treatment_network_path import (
    copy_smb_file_to_local,
    copy_local_file_to_smb_atomic,
    is_smb_path,
    normalize_smb_path,
    smb_is_within,
    smb_isdir,
    smb_isfile,
    smb_join,
    smb_listdir,
    smb_name,
    smb_parent,
    smb_remove,
    smb_suffix,
)
from treatment_service import TreatmentDataService

treatment_api = Blueprint("treatment_api", __name__, url_prefix="/api/treatment")

EXP_TYPES = ["HIS", "HIS+NOISE", "ABS+BASE+NOISE"]
DATA_TYPES = [
    "ABS",
    "BASE",
    "NOISE",
    "ABS+BASE",
    "ABS+BASE+NOISE",
]
CALC_MODES = ["individual", "averaged"]
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


def _normalize_path(path: str) -> str:
    if is_smb_path(path):
        return normalize_smb_path(path)
    return os.path.abspath(os.path.expanduser(str(path).strip()))


def _is_within_allowed_root(path: str) -> bool:
    allowed_root = _normalize_path(get_allowed_root())
    candidate = _normalize_path(path)
    if is_smb_path(candidate) or is_smb_path(allowed_root):
        if not is_smb_path(candidate) or not is_smb_path(allowed_root):
            return False
        try:
            return smb_is_within(candidate, allowed_root)
        except ValueError:
            return False

    try:
        return os.path.commonpath([candidate, allowed_root]) == allowed_root
    except ValueError:
        return False


def _ensure_within_allowed_root(path: str) -> str:
    normalized = _normalize_path(path)
    if not _is_within_allowed_root(normalized):
        raise ValueError("Path is outside the allowed treatment root")
    return normalized


def _ensure_readable_treatment_file(path: str) -> str:
    normalized = _normalize_path(path)
    if is_smb_path(normalized):
        raise ValueError("Network files must be cached before treatment can read them")
    if not (_is_within_allowed_root(normalized) or is_within_cache(normalized)):
        raise ValueError("Path is outside the allowed treatment root and treatment cache")
    if not os.path.isfile(normalized):
        raise ValueError("Selected file does not exist")
    return normalized


def _default_folder() -> str:
    folder = _normalize_path(get_allowed_root())
    if is_smb_path(folder):
        return folder
    if os.path.isdir(folder):
        return folder
    return ""


def _folder_exists(folder: str) -> bool:
    if is_smb_path(folder):
        return smb_isdir(folder)
    return os.path.isdir(folder)


def _root_exists(root: str) -> bool:
    now = monotonic()
    with _root_exists_cache_lock:
        cached = _root_exists_cache.get(root)
        if cached and now - cached[1] <= ROOT_EXISTS_CACHE_TTL_SECONDS:
            return bool(cached[0])

    if is_smb_path(root):
        exists = True
    else:
        exists = os.path.isdir(root)

    with _root_exists_cache_lock:
        _root_exists_cache[root] = (bool(exists), now)
    return bool(exists)


def _clear_root_exists_cache(root: Optional[str] = None) -> None:
    with _root_exists_cache_lock:
        if root is None:
            _root_exists_cache.clear()
        else:
            _root_exists_cache.pop(root, None)


def _default_state() -> Dict[str, object]:
    folder = _default_folder()
    default_exp_type = EXP_TYPES[1]
    default_required = REQUIRED_DATA_TYPES[default_exp_type]
    return {
        "exp_type": default_exp_type,
        "selected_data_type": default_required[0],
        "active_data_type": "",
        "map_index": 0,
        "selection": {},
        "calc_mode": CALC_MODES[0],
        "first_map_with_electrons": True,
        "folder_path": folder,
        "save_folder": folder,
        "save_file_name": "",
        "paths": {},
        "path_sources": {},
        "status_label": "Treatment session is ready.",
        "noise_ready": False,
        "result_ready": False,
        "result_shape": None,
        "result_source_path": "",
    }


def _file_data_type_candidate(file_name: str, exp_type: str) -> Optional[str]:
    stem = Path(file_name).stem.upper()
    if stem.startswith("NOISE") or stem.startswith("BRUIT"):
        return "NOISE"
    if exp_type == "ABS+BASE+NOISE":
        if stem.startswith("BASE"):
            return "BASE"
        if stem.startswith("ABS"):
            return "ABS"
    elif exp_type == "HIS+NOISE":
        if stem.startswith("ABS"):
            return "ABS+BASE"
    elif exp_type == "HIS":
        if stem.startswith("ABS"):
            return "ABS+BASE+NOISE"
    return None


def _candidate_rank(file_path: Path) -> tuple:
    suffix = file_path.suffix.lower()
    suffix_rank = {
        ".his": 0,
        ".img": 2,
        ".dat": 3,
        ".h5": 4,
        ".raw": 4,
    }.get(suffix, 99)
    return (suffix_rank, file_path.name.lower())


def _default_save_target_for_folder(folder: str):
    folder_name = _path_name(folder)
    save_file_name = f"{folder_name}_test.dat" if folder_name else "test.dat"
    if is_smb_path(folder):
        parent = smb_parent(folder)
        return parent or folder, save_file_name
    parent = str(Path(folder).expanduser().resolve().parent)
    return parent, save_file_name


def _path_name(path: str) -> str:
    if is_smb_path(path):
        return smb_name(path)
    return Path(path).name


def _path_suffix(path: str) -> str:
    if is_smb_path(path):
        return smb_suffix(path)
    return Path(path).suffix.lower()


def _candidate_sort_key(path: str) -> tuple:
    suffix = _path_suffix(path)
    suffix_rank = {
        ".his": 0,
        ".img": 2,
        ".dat": 3,
        ".h5": 4,
        ".raw": 4,
    }.get(suffix, 99)
    return (suffix_rank, _path_name(path).lower())


def _folder_input_candidates(folder: str, exp_type: str, convert: bool = False) -> Dict[str, List[str]]:
    required_data_types = REQUIRED_DATA_TYPES.get(exp_type, [])
    candidates: Dict[str, List[str]] = {data_type: [] for data_type in required_data_types}
    accepted_suffixes = {".his", ".h5"} if convert else set(treatment_service.supported_suffixes)

    if is_smb_path(folder):
        entries = smb_listdir(folder)
        for entry in entries:
            if not entry["is_file"]:
                continue
            file_path = str(entry["path"])
            if _path_suffix(file_path) not in accepted_suffixes:
                continue
            data_type = _file_data_type_candidate(str(entry["name"]), exp_type)
            if data_type in candidates:
                candidates[data_type].append(file_path)
    else:
        with os.scandir(folder) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                file_path = entry.path
                if _path_suffix(file_path) not in accepted_suffixes:
                    continue
                data_type = _file_data_type_candidate(entry.name, exp_type)
                if data_type in candidates:
                    candidates[data_type].append(file_path)

    return candidates


def _convert_sort_key(path: str) -> tuple:
    suffix = _path_suffix(path)
    suffix_rank = {".his": 0, ".h5": 1}.get(suffix, 99)
    return (suffix_rank, _path_name(path).lower())


def _convert_source_to_h5(source_path: str) -> Dict[str, object]:
    source_suffix = _path_suffix(source_path)
    if source_suffix == ".h5":
        if is_smb_path(source_path):
            cached_source = _cache_assignable_source(source_path)
            source_size_bytes = int(cached_source.get("size_bytes") or 0)
            with tempfile.TemporaryDirectory(prefix="pyconlyse_recompress_h5_") as tmp_dir:
                local_output = Path(tmp_dir) / _path_name(source_path)
                summary = treatment_service.convert_file_to_h5(
                    Path(str(cached_source["cached_path"])),
                    local_output,
                )
                output_size_bytes = int(local_output.stat().st_size)
                copy_local_file_to_smb_atomic(local_output, source_path)
            if not smb_isfile(source_path):
                raise ValueError(f"Compressed H5 was not created: {source_path}")
        else:
            source = Path(source_path).expanduser()
            source_size_bytes = int(source.stat().st_size)
            summary = treatment_service.convert_file_to_h5(source, source)
            if not source.is_file():
                raise ValueError(f"Compressed H5 was not created: {source}")
            output_size_bytes = int(source.stat().st_size)

        space_change_bytes = output_size_bytes - source_size_bytes
        summary.update({
            "source_path": source_path,
            "output_path": source_path,
            "converted": True,
            "overwritten": True,
            "deleted_source": False,
            "source_size_bytes": source_size_bytes,
            "output_size_bytes": output_size_bytes,
            "space_change_bytes": space_change_bytes,
            "space_change_percent": (
                round((space_change_bytes / source_size_bytes) * 100, 2)
                if source_size_bytes
                else 0.0
            ),
        })
        return summary
    if source_suffix != ".his":
        raise ValueError("Set/Convert supports only HIS to H5 conversion or existing H5 files")

    output_name = f"{Path(_path_name(source_path)).stem}.h5"
    if is_smb_path(source_path):
        output_path = smb_join(smb_parent(source_path), output_name)
        cached_source = _cache_assignable_source(source_path)
        source_size_bytes = int(cached_source.get("size_bytes") or 0)
        with tempfile.TemporaryDirectory(prefix="pyconlyse_convert_h5_") as tmp_dir:
            local_output = Path(tmp_dir) / output_name
            summary = treatment_service.convert_file_to_h5(
                Path(str(cached_source["cached_path"])),
                local_output,
            )
            output_size_bytes = int(local_output.stat().st_size)
            copy_local_file_to_smb_atomic(local_output, output_path)
        if not smb_isfile(output_path):
            raise ValueError(f"Converted H5 was not created: {output_path}")
        smb_remove(source_path)
        space_change_bytes = output_size_bytes - source_size_bytes
        summary.update({
            "source_path": source_path,
            "output_path": output_path,
            "converted": True,
            "deleted_source": True,
            "source_size_bytes": source_size_bytes,
            "output_size_bytes": output_size_bytes,
            "space_change_bytes": space_change_bytes,
            "space_change_percent": (
                round((space_change_bytes / source_size_bytes) * 100, 2)
                if source_size_bytes
                else 0.0
            ),
        })
        return summary

    source = Path(source_path).expanduser()
    source_size_bytes = int(source.stat().st_size)
    output_path = source.with_suffix(".h5")
    summary = treatment_service.convert_file_to_h5(source, output_path)
    if not output_path.is_file():
        raise ValueError(f"Converted H5 was not created: {output_path}")
    output_size_bytes = int(output_path.stat().st_size)
    source.unlink()
    space_change_bytes = output_size_bytes - source_size_bytes
    summary.update({
        "source_path": str(source),
        "output_path": str(output_path),
        "converted": True,
        "deleted_source": True,
        "source_size_bytes": source_size_bytes,
        "output_size_bytes": output_size_bytes,
        "space_change_bytes": space_change_bytes,
        "space_change_percent": (
            round((space_change_bytes / source_size_bytes) * 100, 2)
            if source_size_bytes
            else 0.0
        ),
    })
    return summary


def _smb_size_bytes(path: str) -> int:
    parent = smb_parent(path)
    for entry in smb_listdir(parent):
        if str(entry.get("path")) == path:
            return int(entry.get("size_bytes") or 0)
    return 0


def _compression_job_snapshot(job_id: str) -> Dict[str, object]:
    with _compression_jobs_lock:
        return dict(_compression_jobs.get(job_id) or {})


def _update_compression_job(job_id: str, **updates) -> None:
    with _compression_jobs_lock:
        job = _compression_jobs.setdefault(job_id, {})
        job.update(updates)
        job["updated_at"] = monotonic()


def _compression_progress_summary(source_path: str, progress_callback=None) -> Dict[str, object]:
    source_suffix = _path_suffix(source_path)
    if source_suffix not in {".his", ".h5"}:
        raise ValueError("Convert/Compress supports only HIS or H5 files")

    output_name = f"{Path(_path_name(source_path)).stem}.h5"
    output_path = source_path if source_suffix == ".h5" else (
        smb_join(smb_parent(source_path), output_name)
        if is_smb_path(source_path)
        else str(Path(source_path).expanduser().with_suffix(".h5"))
    )

    if is_smb_path(source_path):
        source_size_bytes = _smb_size_bytes(source_path)
        with tempfile.TemporaryDirectory(prefix="pyconlyse_compress_job_") as tmp_dir:
            local_source = Path(tmp_dir) / _path_name(source_path)
            local_output = Path(tmp_dir) / output_name
            if progress_callback:
                progress_callback("download", 0, source_size_bytes, "Reading source file from SMB")
            copy_smb_file_to_local(
                source_path,
                local_source,
                progress_callback=(
                    lambda current: progress_callback(
                        "download",
                        current,
                        source_size_bytes,
                        "Reading source file from SMB",
                    )
                    if progress_callback
                    else None
                ),
            )

            if progress_callback:
                progress_callback("convert", 0, 0, "Compressing local H5 with gzip level 9")
            summary = treatment_service.convert_file_to_h5(local_source, local_output)
            output_size_bytes = int(local_output.stat().st_size)

            if progress_callback:
                progress_callback("upload", 0, output_size_bytes, "Writing compressed H5 to SMB")
            copy_local_file_to_smb_atomic(
                local_output,
                output_path,
                progress_callback=(
                    lambda current: progress_callback(
                        "upload",
                        current,
                        output_size_bytes,
                        "Writing compressed H5 to SMB",
                    )
                    if progress_callback
                    else None
                ),
            )

        if not smb_isfile(output_path):
            raise ValueError(f"Compressed H5 was not created: {output_path}")
        if source_suffix == ".his":
            if progress_callback:
                progress_callback("delete", 0, 0, "Removing source HIS")
            smb_remove(source_path)
    else:
        source = Path(source_path).expanduser()
        source_size_bytes = int(source.stat().st_size)
        output = Path(output_path).expanduser()
        if progress_callback:
            progress_callback("convert", 0, source_size_bytes, "Compressing local H5 with gzip level 9")
        summary = treatment_service.convert_file_to_h5(source, output)
        if not output.is_file():
            raise ValueError(f"Compressed H5 was not created: {output}")
        output_size_bytes = int(output.stat().st_size)
        if source_suffix == ".his":
            if progress_callback:
                progress_callback("delete", 0, 0, "Removing source HIS")
            source.unlink()

    space_change_bytes = output_size_bytes - source_size_bytes
    summary.update({
        "source_path": source_path,
        "output_path": output_path,
        "converted": True,
        "overwritten": source_suffix == ".h5",
        "deleted_source": source_suffix == ".his",
        "source_size_bytes": source_size_bytes,
        "output_size_bytes": output_size_bytes,
        "space_change_bytes": space_change_bytes,
        "space_change_percent": (
            round((space_change_bytes / source_size_bytes) * 100, 2)
            if source_size_bytes
            else 0.0
        ),
    })
    return summary


def _run_compression_job(job_id: str, session_id: str, source_path: str) -> None:
    def progress(phase: str, current: int, total: int, message: str) -> None:
        _update_compression_job(
            job_id,
            phase=phase,
            current_bytes=int(current or 0),
            total_bytes=int(total or 0),
            message=message,
        )

    try:
        progress("start", 0, 0, "Starting Convert/Compress")
        conversion = _compression_progress_summary(source_path, progress_callback=progress)
        _update_compression_job(
            job_id,
            status="complete",
            phase="complete",
            current_bytes=int(conversion.get("output_size_bytes") or 0),
            total_bytes=int(conversion.get("output_size_bytes") or 0),
            message="Convert/Compress complete",
            conversion=conversion,
            payload={**_session_payload(session_id), "conversion": conversion},
        )
    except ValueError as exc:
        _update_compression_job(
            job_id,
            status="error",
            phase="error",
            message=str(exc),
            error=str(exc),
        )


def _delete_source_his_after_cleaning(saved: Dict[str, object]) -> Optional[str]:
    source_path = str(saved.get("source_file_path") or saved.get("file_path") or "")
    output_path = str(saved.get("output_path") or "")
    if not source_path or not output_path or _path_suffix(source_path) != ".his":
        return None
    if is_within_cache(source_path):
        return None

    if is_smb_path(source_path):
        if not is_smb_path(output_path) or not smb_isfile(output_path):
            raise ValueError("Cleaned H5 was not created; HIS was not deleted")
        smb_remove(source_path)
        return source_path

    normalized_source = _ensure_within_allowed_root(source_path)
    source = Path(normalized_source).expanduser()
    output = Path(output_path).expanduser()
    if not output.is_file():
        raise ValueError("Cleaned H5 was not created; HIS was not deleted")
    source.unlink()
    return str(source)


def _cache_assignable_source(source_path: str) -> Dict[str, object]:
    if is_smb_path(source_path):
        if not smb_isfile(source_path):
            raise ValueError("Selected file does not exist")
        return cache_external_file(
            source_path,
            smb_name(source_path),
            lambda target_path: copy_smb_file_to_local(source_path, target_path),
        )

    if not os.path.isfile(source_path):
        raise ValueError("Selected file does not exist")
    return cache_file(source_path)


class TreatmentSessionStore:
    def __init__(self):
        self._lock = Lock()
        self._sessions: Dict[str, Dict[str, object]] = {}

    @staticmethod
    def _clone_state(state: Dict[str, object]) -> Dict[str, object]:
        snapshot = dict(state)
        snapshot["paths"] = dict(state["paths"])
        snapshot["path_sources"] = dict(state.get("path_sources") or {})
        snapshot["selection"] = dict(state["selection"])
        return snapshot

    def _get_or_create_state(self, session_id: str) -> Dict[str, object]:
        state = self._sessions.get(session_id)
        if state is None:
            state = _default_state()
            self._sessions[session_id] = state
        return state

    def snapshot(self, session_id: str) -> Dict[str, object]:
        with self._lock:
            state = self._get_or_create_state(session_id)
            return self._clone_state(state)

    def reset(self, session_id: Optional[str] = None) -> Dict[str, object]:
        with self._lock:
            if session_id is None:
                self._sessions.clear()
                return self._clone_state(_default_state())
            self._sessions[session_id] = _default_state()
            return self._clone_state(self._sessions[session_id])

    def update_config(self, session_id: str, payload: Dict[str, object]) -> Dict[str, object]:
        with self._lock:
            state = self._get_or_create_state(session_id)
            requested_exp_type = str(state["exp_type"])
            if "exp_type" in payload:
                exp_type = str(payload["exp_type"])
                if exp_type not in EXP_TYPES:
                    raise ValueError(f"Unsupported exp_type '{exp_type}'")
                state["exp_type"] = exp_type
                requested_exp_type = exp_type

            if "selected_data_type" in payload:
                selected_data_type = str(payload["selected_data_type"])
                if selected_data_type not in DATA_TYPES:
                    raise ValueError(
                        f"Unsupported selected_data_type '{selected_data_type}'"
                    )
                if selected_data_type not in REQUIRED_DATA_TYPES[requested_exp_type]:
                    raise ValueError(
                        f"selected_data_type '{selected_data_type}' is not valid for exp_type '{requested_exp_type}'"
                    )
                state["selected_data_type"] = selected_data_type
            else:
                required_data_types = REQUIRED_DATA_TYPES[requested_exp_type]
                if state["selected_data_type"] not in required_data_types:
                    state["selected_data_type"] = required_data_types[0]

            if "calc_mode" in payload:
                calc_mode = str(payload["calc_mode"])
                if calc_mode not in CALC_MODES:
                    raise ValueError(f"Unsupported calc_mode '{calc_mode}'")
                state["calc_mode"] = calc_mode

            if requested_exp_type == "ABS+BASE+NOISE":
                state["calc_mode"] = "averaged"

            if "first_map_with_electrons" in payload:
                state["first_map_with_electrons"] = bool(
                    payload["first_map_with_electrons"]
                )

            if "save_folder" in payload:
                save_folder = _ensure_within_allowed_root(str(payload["save_folder"]))
                if not _folder_exists(save_folder):
                    raise ValueError("save_folder does not exist")
                state["save_folder"] = save_folder

            if "save_file_name" in payload:
                save_file_name = os.path.basename(str(payload["save_file_name"]).strip())
                if save_file_name and not save_file_name.lower().endswith(".dat"):
                    save_file_name = f"{Path(save_file_name).stem}.dat"
                state["save_file_name"] = save_file_name

            state["status_label"] = "Treatment session updated."

        return self.snapshot(session_id)

    def set_folder(self, session_id: str, folder_path: str) -> Dict[str, object]:
        folder = _ensure_within_allowed_root(folder_path)
        if not _folder_exists(folder):
            raise ValueError("Selected folder does not exist")

        with self._lock:
            state = self._get_or_create_state(session_id)
            state["folder_path"] = folder
            save_folder, save_file_name = _default_save_target_for_folder(folder)
            state["save_folder"] = save_folder
            state["save_file_name"] = save_file_name
            state["status_label"] = f"Folder selected: {folder}"

        return self.snapshot(session_id)

    def set_data_path(
        self,
        session_id: str,
        data_type: str,
        file_path: str,
        source_path: Optional[str] = None,
    ) -> Dict[str, object]:
        if data_type not in DATA_TYPES:
            raise ValueError(f"Unsupported data_type '{data_type}'")

        normalized = _ensure_readable_treatment_file(file_path)
        normalized_source = _normalize_path(source_path) if source_path else normalized

        with self._lock:
            state = self._get_or_create_state(session_id)
            state["paths"][data_type] = normalized
            state.setdefault("path_sources", {})[data_type] = normalized_source
            state["active_data_type"] = data_type
            state["map_index"] = 0
            state["selection"] = {}
            if not state["save_file_name"]:
                stem = os.path.splitext(os.path.basename(normalized))[0]
                state["save_file_name"] = f"{stem}.dat"
            state["status_label"] = f"{data_type} file selected."

        return self.snapshot(session_id)

    def update_selection(self, session_id: str, payload: Dict[str, object]) -> Dict[str, object]:
        with self._lock:
            state = self._get_or_create_state(session_id)

            if "active_data_type" in payload:
                active_data_type = str(payload["active_data_type"])
                if active_data_type and active_data_type != "OD" and active_data_type not in DATA_TYPES:
                    raise ValueError(f"Unsupported active_data_type '{active_data_type}'")
                state["active_data_type"] = active_data_type

            if "map_index" in payload:
                try:
                    map_index = int(payload["map_index"])
                except (TypeError, ValueError):
                    raise ValueError("map_index must be an integer")
                if map_index < 0:
                    raise ValueError("map_index must be zero or positive")
                state["map_index"] = map_index

            if "selection" in payload:
                raw_selection = payload["selection"] or {}
                if not isinstance(raw_selection, dict):
                    raise ValueError("selection must be an object")

                selection = dict(state["selection"])
                for key in ("x1", "x2", "y1", "y2"):
                    if key in raw_selection and raw_selection[key] is not None:
                        try:
                            selection[key] = int(raw_selection[key])
                        except (TypeError, ValueError):
                            raise ValueError(f"{key} must be an integer")
                state["selection"] = selection

            state["status_label"] = "Selection updated."

        return self.snapshot(session_id)


session_store = TreatmentSessionStore()
treatment_service = TreatmentDataService()


def _current_session_id() -> str:
    session_id = (
        request.headers.get("X-Treatment-Session-Id")
        or request.cookies.get(TREATMENT_SESSION_COOKIE)
        or ""
    ).strip()
    if session_id:
        return session_id
    return uuid4().hex


def _session_payload(session_id: str) -> Dict[str, object]:
    runtime = treatment_service.runtime_status(session_id)
    session = session_store.snapshot(session_id)
    session.update(runtime)
    required_data_types = REQUIRED_DATA_TYPES.get(str(session.get("exp_type")), DATA_TYPES)
    paths = session.get("paths") or {}
    missing_data_types = [
        data_type for data_type in required_data_types if not paths.get(data_type)
    ]
    session["required_data_types"] = list(required_data_types)
    session["missing_data_types"] = missing_data_types
    session["ready_for_calc"] = len(missing_data_types) == 0
    allowed_root = _normalize_path(get_allowed_root())
    return {
        "session_id": session_id,
        "session": session,
        "allowed_root": allowed_root,
        "allowed_root_exists": _root_exists(allowed_root),
        "treatment_root_base": _normalize_path(get_treatment_root_base()),
        "treatment_root_bases": [_normalize_path(root_base) for root_base in get_treatment_root_bases()],
        "cache_root": str(get_cache_root()),
        "cache_limit_bytes": get_cache_limit_bytes(),
        "exp_types": EXP_TYPES,
        "data_types": DATA_TYPES,
        "calc_modes": CALC_MODES,
        "supported_suffixes": list(treatment_service.supported_suffixes),
        "success": True,
    }


def _active_assignable_data_type(session: Dict[str, object]) -> str:
    paths = session.get("paths") or {}
    active_data_type = str(session.get("active_data_type") or "").strip()
    if active_data_type in DATA_TYPES and paths.get(active_data_type):
        return active_data_type
    for data_type in DATA_TYPES:
        if paths.get(data_type):
            return data_type
    return ""


def _json_response(payload: Dict[str, object], session_id: str, status_code: int = 200):
    response = jsonify(payload)
    response.status_code = status_code
    response.set_cookie(
        TREATMENT_SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="Lax",
    )
    return response


def _error(message: str, session_id: str, status_code: int = 400):
    return _json_response({"error": message, "success": False}, session_id, status_code)


@treatment_api.route("/session", methods=["GET"])
def get_session():
    session_id = _current_session_id()
    return _json_response(_session_payload(session_id), session_id)


@treatment_api.route("/session/reset", methods=["POST"])
def reset_session():
    session_id = _current_session_id()
    session_store.reset(session_id)
    treatment_service.reset_runtime(session_id)
    return _json_response(_session_payload(session_id), session_id)


@treatment_api.route("/session/config", methods=["POST"])
def update_session_config():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    try:
        session_store.update_config(session_id, payload)
        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)
    return _json_response(_session_payload(session_id), session_id)


@treatment_api.route("/session/root", methods=["POST"])
def update_session_root():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    root_path = payload.get("allowed_root") or payload.get("root_path")
    if not root_path:
        return _error("allowed_root is required", session_id)

    try:
        previous_root = _normalize_path(get_allowed_root())
        set_allowed_root(str(root_path))
        _clear_root_exists_cache(previous_root)
        _clear_root_exists_cache(_normalize_path(str(root_path)))
        session_store.reset()
        treatment_service.reset_runtime()
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response(_session_payload(session_id), session_id)


@treatment_api.route("/session/folder", methods=["POST"])
def set_session_folder():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    folder_path = payload.get("folder_path")
    if not folder_path:
        return _error("folder_path is required", session_id)

    try:
        session_store.set_folder(session_id, str(folder_path))
        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response(_session_payload(session_id), session_id)


@treatment_api.route("/session/folder-set", methods=["POST"])
def set_inputs_from_folder():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    folder_path = payload.get("folder_path")
    convert = bool(payload.get("convert", False))
    clean = bool(payload.get("clean", False))
    if clean:
        convert = True
    if not folder_path:
        return _error("folder_path is required", session_id)

    try:
        angle_threshold = float(payload.get("angle_threshold", 1.0))
        surface_threshold = float(payload.get("surface_threshold", 1.0))
    except (TypeError, ValueError):
        return _error("angle_threshold and surface_threshold must be numeric", session_id)

    try:
        folder = _ensure_within_allowed_root(str(folder_path))
        if not _folder_exists(folder):
            return _error("Folder does not exist", session_id, 404)

        session = session_store.snapshot(session_id)
        exp_type = str(session.get("exp_type"))
        candidates = _folder_input_candidates(folder, exp_type, convert=convert)
        found = {
            data_type: sorted(paths, key=_convert_sort_key if convert else _candidate_sort_key)
            for data_type, paths in candidates.items()
            if paths
        }
        if len(found) < 2:
            names = ", ".join(sorted(found.keys())) or "none"
            return _error(
                f"Folder must contain at least two assignable inputs for {exp_type}; found {names}.",
                session_id,
            )

        prepared: Dict[str, Dict[str, object]] = {}
        for data_type, paths in found.items():
            selected_path = paths[0]
            if convert:
                conversion = _convert_source_to_h5(selected_path)
                source_path = str(conversion["output_path"])
                prepared[data_type] = {
                    "source_path": source_path,
                    "conversion": conversion,
                }
            else:
                prepared[data_type] = {
                    "source_path": selected_path,
                    "conversion": None,
                }

        session_store.set_folder(session_id, folder)
        assigned: Dict[str, str] = {}
        cached_files: Dict[str, Dict[str, object]] = {}
        conversions: Dict[str, Dict[str, object]] = {}
        cleaned: Dict[str, Dict[str, object]] = {}
        for data_type, prepared_item in prepared.items():
            source_path = str(prepared_item["source_path"])
            cached = _cache_assignable_source(source_path)
            session_store.set_data_path(
                session_id,
                data_type,
                str(cached["cached_path"]),
                source_path=str(cached["source_path"]),
            )
            assigned[data_type] = str(cached["cached_path"])
            cached_files[data_type] = cached
            if prepared_item["conversion"]:
                conversions[data_type] = prepared_item["conversion"]
            if clean:
                treatment_service.reset_runtime(session_id)
                saved = treatment_service.save_sam_cleaned_h5(
                    session_id,
                    session_store.snapshot(session_id),
                    angle_threshold,
                    surface_threshold,
                )
                deleted_source_file = _delete_source_his_after_cleaning(saved)
                if deleted_source_file:
                    saved["deleted_source_file"] = deleted_source_file
                output_path = str(saved.get("output_path") or "")
                if output_path:
                    if is_smb_path(output_path):
                        cleaned_cache = _cache_assignable_source(output_path)
                        assigned_path = str(cleaned_cache["cached_path"])
                        source_path = str(cleaned_cache["source_path"])
                        saved["cached_file"] = cleaned_cache
                        cached_files[data_type] = cleaned_cache
                    else:
                        assigned_path = output_path
                        source_path = output_path
                    session_store.set_data_path(
                        session_id,
                        data_type,
                        assigned_path,
                        source_path=source_path,
                    )
                    assigned[data_type] = assigned_path
                    saved["assigned_data_type"] = data_type
                    saved["assigned_path"] = assigned_path
                cleaned[data_type] = saved

        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)
    except OSError as exc:
        return _error(str(exc), session_id)

    response_payload = _session_payload(session_id)
    response_payload["folder_set"] = {
        "folder": folder,
        "convert": convert,
        "clean": clean,
        "assigned": assigned,
        "cached_files": cached_files,
        "conversions": conversions,
        "cleaned": cleaned,
    }
    return _json_response(response_payload, session_id)


@treatment_api.route("/session/path", methods=["POST"])
def set_session_path():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return _error("data_type and file_path are required", session_id)

    try:
        session_store.set_data_path(
            session_id,
            str(data_type),
            str(file_path),
            source_path=str(file_path),
        )
        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response(_session_payload(session_id), session_id)


@treatment_api.route("/session/cache-path", methods=["POST"])
def cache_and_set_session_path():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return _error("data_type and file_path are required", session_id)

    try:
        source_path = _ensure_within_allowed_root(str(file_path))
        cached = _cache_assignable_source(source_path)
        session_store.set_data_path(
            session_id,
            str(data_type),
            str(cached["cached_path"]),
            source_path=str(cached["source_path"]),
        )
        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)

    response_payload = _session_payload(session_id)
    response_payload["cached_file"] = cached
    return _json_response(response_payload, session_id)


@treatment_api.route("/session/compress-path", methods=["POST"])
def compress_and_set_session_path():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return _error("data_type and file_path are required", session_id)

    try:
        source_path = _ensure_within_allowed_root(str(file_path))
        conversion = _convert_source_to_h5(source_path)
        output_path = str(conversion["output_path"])
        cached = _cache_assignable_source(output_path)
        session_store.set_data_path(
            session_id,
            str(data_type),
            str(cached["cached_path"]),
            source_path=str(cached["source_path"]),
        )
        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)

    response_payload = _session_payload(session_id)
    response_payload["cached_file"] = cached
    response_payload["conversion"] = conversion
    return _json_response(response_payload, session_id)


@treatment_api.route("/session/compress-file", methods=["POST"])
def compress_file_path():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    file_path = payload.get("file_path")
    if not file_path:
        return _error("file_path is required", session_id)

    try:
        source_path = _ensure_within_allowed_root(str(file_path))
        conversion = _convert_source_to_h5(source_path)
    except ValueError as exc:
        return _error(str(exc), session_id)

    response_payload = _session_payload(session_id)
    response_payload["conversion"] = conversion
    return _json_response(response_payload, session_id)


@treatment_api.route("/session/compress-file/start", methods=["POST"])
def start_compress_file_path():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    file_path = payload.get("file_path")
    if not file_path:
        return _error("file_path is required", session_id)

    try:
        source_path = _ensure_within_allowed_root(str(file_path))
    except ValueError as exc:
        return _error(str(exc), session_id)

    job_id = uuid4().hex
    with _compression_jobs_lock:
        _compression_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "phase": "queued",
            "message": "Queued Convert/Compress",
            "source_path": source_path,
            "current_bytes": 0,
            "total_bytes": 0,
            "created_at": monotonic(),
            "updated_at": monotonic(),
        }

    thread = Thread(
        target=_run_compression_job,
        args=(job_id, session_id, source_path),
        daemon=True,
    )
    thread.start()
    return _json_response({"compression_job": _compression_job_snapshot(job_id), "success": True}, session_id)


@treatment_api.route("/session/compress-file/status/<job_id>", methods=["GET"])
def get_compress_file_status(job_id: str):
    session_id = _current_session_id()
    job = _compression_job_snapshot(str(job_id))
    if not job:
        return _error("compression job not found", session_id, 404)
    return _json_response({"compression_job": job, "success": True}, session_id)


@treatment_api.route("/session/auto-assign", methods=["POST"])
def auto_assign_session_paths():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    folder = payload.get("folder_path") or session_store.snapshot(session_id).get("folder_path")
    if not folder:
        return _error("folder_path is required", session_id)

    try:
        normalized_folder = _ensure_within_allowed_root(str(folder))
    except ValueError as exc:
        return _error(str(exc), session_id, 403)

    try:
        folder_exists = _folder_exists(normalized_folder)
    except ValueError as exc:
        return _error(str(exc), session_id)
    if not folder_exists:
        return _error("Folder does not exist", session_id, 404)

    session = session_store.snapshot(session_id)
    exp_type = str(session.get("exp_type"))
    required_data_types = REQUIRED_DATA_TYPES.get(exp_type, [])
    supported_suffixes = set(treatment_service.supported_suffixes)
    candidates: Dict[str, List[str]] = {data_type: [] for data_type in required_data_types}

    if is_smb_path(normalized_folder):
        entries = smb_listdir(normalized_folder)
        for entry in entries:
            if not entry["is_file"]:
                continue
            file_path = str(entry["path"])
            if _path_suffix(file_path) not in supported_suffixes:
                continue
            data_type = _file_data_type_candidate(str(entry["name"]), exp_type)
            if data_type in candidates:
                candidates[data_type].append(file_path)
    else:
        with os.scandir(normalized_folder) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                file_path = entry.path
                if _path_suffix(file_path) not in supported_suffixes:
                    continue
                data_type = _file_data_type_candidate(entry.name, exp_type)
                if data_type in candidates:
                    candidates[data_type].append(file_path)

    assigned: Dict[str, str] = {}
    cached_files: Dict[str, Dict[str, object]] = {}
    try:
        session_store.set_folder(session_id, normalized_folder)
        for data_type in required_data_types:
            matches = sorted(candidates.get(data_type, []), key=_candidate_sort_key)
            if not matches:
                continue
            selected_path = matches[0]
            source_path = selected_path
            if is_smb_path(selected_path):
                cached = _cache_assignable_source(selected_path)
                assigned_path = str(cached["cached_path"])
                source_path = str(cached["source_path"])
                cached_files[data_type] = cached
            else:
                assigned_path = str(selected_path)
            session_store.set_data_path(
                session_id,
                data_type,
                assigned_path,
                source_path=source_path,
            )
            assigned[data_type] = assigned_path
        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)

    response_payload = _session_payload(session_id)
    response_payload["auto_assigned"] = assigned
    response_payload["auto_assigned_cached_files"] = cached_files
    response_payload["auto_assign_missing"] = [
        data_type for data_type in required_data_types if data_type not in assigned
    ]
    return _json_response(response_payload, session_id)


@treatment_api.route("/session/selection", methods=["POST"])
def update_session_selection():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}

    try:
        session_store.update_selection(session_id, payload)
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response(_session_payload(session_id), session_id)


@treatment_api.route("/files", methods=["GET"])
def list_files():
    session_id = _current_session_id()
    folder = request.args.get("folder") or session_store.snapshot(session_id).get("folder_path")
    if not folder:
        return _json_response(
            {"folder": "", "folders": [], "files": [], "success": True},
            session_id,
        )

    try:
        normalized = _ensure_within_allowed_root(folder)
    except ValueError as exc:
        return _error(str(exc), session_id, 403)

    try:
        folder_exists = _folder_exists(normalized)
    except ValueError as exc:
        return _error(str(exc), session_id)
    if not folder_exists:
        return _error("Folder does not exist", session_id, 404)

    folders: List[Dict[str, str]] = []
    files: List[Dict[str, object]] = []
    try:
        if is_smb_path(normalized):
            entries = smb_listdir(normalized)
            for entry in entries:
                if entry["is_dir"]:
                    folders.append({"name": entry["name"], "path": entry["path"]})
                elif entry["is_file"]:
                    suffix = smb_suffix(str(entry["path"]))
                    files.append(
                        {
                            "name": entry["name"],
                            "path": entry["path"],
                            "suffix": suffix,
                            "size_bytes": int(entry.get("size_bytes") or 0),
                            "supported": suffix in treatment_service.supported_suffixes,
                        }
                    )
        else:
            with os.scandir(normalized) as entries:
                for entry in entries:
                    if entry.is_dir():
                        folders.append({"name": entry.name, "path": entry.path})
                    elif entry.is_file():
                        suffix = os.path.splitext(entry.name)[1].lower()
                        files.append(
                            {
                                "name": entry.name,
                                "path": entry.path,
                                "suffix": suffix,
                                "size_bytes": int(entry.stat().st_size),
                                "supported": suffix in treatment_service.supported_suffixes,
                            }
                        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    folders.sort(key=lambda item: item["name"].lower())
    files.sort(key=lambda item: item["name"].lower())

    return _json_response(
        {
            "folder": normalized,
            "folders": folders,
            "files": files,
            "success": True,
        },
        session_id,
    )


@treatment_api.route("/file-info", methods=["GET"])
def get_file_info():
    session_id = _current_session_id()
    file_path = request.args.get("file_path")
    data_type = request.args.get("data_type")
    if not file_path and data_type:
        file_path = session_store.snapshot(session_id).get("paths", {}).get(data_type)
    if not file_path:
        return _error("file_path or data_type is required", session_id)

    try:
        normalized = _ensure_readable_treatment_file(file_path)
        file_info = treatment_service.get_file_info(Path(normalized))
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"file_info": file_info, "success": True}, session_id)


@treatment_api.route("/file-summary", methods=["GET"])
def get_file_summary():
    session_id = _current_session_id()
    file_path = request.args.get("file_path")
    if not file_path:
        return _error("file_path is required", session_id)

    try:
        source_path = _ensure_within_allowed_root(file_path)
        suffix = _path_suffix(source_path)
        if suffix not in {".his", ".h5"}:
            return _json_response({"file_summary": {}, "success": True}, session_id)

        if is_smb_path(source_path):
            cached = _cache_assignable_source(source_path)
            readable_path = str(cached["cached_path"])
        else:
            readable_path = _ensure_readable_treatment_file(source_path)

        file_info = treatment_service.get_file_info(Path(readable_path))
        file_summary = {
            "file_path": source_path,
            "number_maps": file_info.get("number_maps"),
            "time_scale": file_info.get("time_scale"),
            "wavelength_min": file_info.get("wavelength_min"),
            "wavelength_max": file_info.get("wavelength_max"),
        }
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"file_summary": file_summary, "success": True}, session_id)


@treatment_api.route("/preview", methods=["GET"])
def preview_file():
    session_id = _current_session_id()
    file_path = request.args.get("file_path")
    data_type = request.args.get("data_type")
    if not file_path and data_type:
        file_path = session_store.snapshot(session_id).get("paths", {}).get(data_type)
    if not file_path:
        return _error("file_path or data_type is required", session_id)

    try:
        map_index = int(request.args.get("map_index", "0"))
    except ValueError:
        return _error("map_index must be an integer", session_id)

    try:
        normalized = _ensure_readable_treatment_file(file_path)
        preview = treatment_service.get_preview(Path(normalized), map_index=map_index)
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"preview": preview, "success": True}, session_id)


@treatment_api.route("/average-noise", methods=["POST"])
def average_noise():
    session_id = _current_session_id()
    try:
        summary = treatment_service.average_noise(session_id, session_store.snapshot(session_id))
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"noise": summary, **_session_payload(session_id)}, session_id)


@treatment_api.route("/selection", methods=["GET"])
def get_selection():
    session_id = _current_session_id()
    try:
        selection = treatment_service.get_selection_view(
            session_store.snapshot(session_id),
            session_id=session_id,
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"selection": selection, "success": True}, session_id)


@treatment_api.route("/selection/export", methods=["POST"])
def export_selection_average():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    user_type = str(payload.get("user_type") or "").strip().lower()
    ranges_text = str(payload.get("ranges") or "")

    if not user_type:
        return _error("user_type is required", session_id)

    try:
        exported = treatment_service.export_selection_average(
            session_store.snapshot(session_id),
            user_type,
            ranges_text,
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    response_payload = _session_payload(session_id)
    response_payload["exported"] = exported
    return _json_response(response_payload, session_id)


@treatment_api.route("/cleaning/sam", methods=["POST"])
def analyze_sam_cleaning():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}

    try:
        angle_threshold = float(payload.get("angle_threshold", 1.0))
        surface_threshold = float(payload.get("surface_threshold", 1.0))
    except (TypeError, ValueError):
        return _error("angle_threshold and surface_threshold must be numeric", session_id)

    try:
        summary = treatment_service.analyze_sam_cleaning(
            session_id,
            session_store.snapshot(session_id),
            angle_threshold,
            surface_threshold,
        )
        cleaning_view = treatment_service.get_cleaning_view(
            session_id,
            session_store.snapshot(session_id),
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response(
        {"cleaning": summary, "cleaning_view": cleaning_view, "success": True},
        session_id,
    )


@treatment_api.route("/cleaning/view", methods=["GET"])
def get_sam_cleaning_view():
    session_id = _current_session_id()

    try:
        cleaning_view = treatment_service.get_cleaning_view(
            session_id,
            session_store.snapshot(session_id),
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"cleaning_view": cleaning_view, "success": True}, session_id)


@treatment_api.route("/cleaning/reset", methods=["POST"])
def reset_sam_cleaning():
    session_id = _current_session_id()

    try:
        summary = treatment_service.reset_sam_cleaning(
            session_id,
            session_store.snapshot(session_id),
        )
        cleaning_view = treatment_service.get_cleaning_view(
            session_id,
            session_store.snapshot(session_id),
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response(
        {"cleaning": summary, "cleaning_view": cleaning_view, "success": True},
        session_id,
    )


@treatment_api.route("/cleaning/save", methods=["POST"])
def save_sam_cleaning():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}

    try:
        angle_threshold = float(payload.get("angle_threshold", 1.0))
        surface_threshold = float(payload.get("surface_threshold", 1.0))
    except (TypeError, ValueError):
        return _error("angle_threshold and surface_threshold must be numeric", session_id)

    output_file_name = str(payload.get("output_file_name") or "")

    try:
        before_save_state = session_store.snapshot(session_id)
        active_data_type = _active_assignable_data_type(before_save_state)
        saved = treatment_service.save_sam_cleaned_h5(
            session_id,
            before_save_state,
            angle_threshold,
            surface_threshold,
            output_file_name=output_file_name,
        )
        deleted_source_file = _delete_source_his_after_cleaning(saved)
        if deleted_source_file:
            saved["deleted_source_file"] = deleted_source_file
        output_path = str(saved.get("output_path") or "")
        if output_path and active_data_type:
            if is_smb_path(output_path):
                cached = _cache_assignable_source(output_path)
                assigned_path = str(cached["cached_path"])
                source_path = str(cached["source_path"])
                saved["cached_file"] = cached
            else:
                assigned_path = output_path
                source_path = output_path
            session_store.set_data_path(
                session_id,
                active_data_type,
                assigned_path,
                source_path=source_path,
            )
            treatment_service.reset_runtime(session_id)
            saved["assigned_data_type"] = active_data_type
            saved["assigned_path"] = assigned_path
    except ValueError as exc:
        return _error(str(exc), session_id)

    payload = _session_payload(session_id)
    payload["cleaning"] = saved
    return _json_response(payload, session_id)


@treatment_api.route("/cleaning/file/save", methods=["POST"])
def save_sam_cleaning_for_file():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    raw_file_path = payload.get("file_path")
    if not raw_file_path:
        return _error("file_path is required", session_id)

    try:
        angle_threshold = float(payload.get("angle_threshold", 1.0))
        surface_threshold = float(payload.get("surface_threshold", 1.0))
    except (TypeError, ValueError):
        return _error("angle_threshold and surface_threshold must be numeric", session_id)

    output_file_name = str(payload.get("output_file_name") or "")

    try:
        normalized = _ensure_readable_treatment_file(str(raw_file_path))
        saved = treatment_service.save_file_sam_cleaned_h5(
            Path(normalized),
            angle_threshold,
            surface_threshold,
            output_file_name=output_file_name,
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"cleaning": saved, "success": True}, session_id)


@treatment_api.route("/calc-abs", methods=["POST"])
def calc_abs():
    session_id = _current_session_id()
    try:
        result = treatment_service.calc_abs(session_id, session_store.snapshot(session_id))
        session_store.update_selection(session_id, {"active_data_type": "OD", "map_index": 0})
    except ValueError as exc:
        return _error(str(exc), session_id)

    payload = _session_payload(session_id)
    payload["result"] = result
    return _json_response(payload, session_id)


@treatment_api.route("/save", methods=["POST"])
def save_result():
    session_id = _current_session_id()
    try:
        saved = treatment_service.save_result(session_id, session_store.snapshot(session_id))
    except ValueError as exc:
        return _error(str(exc), session_id)

    payload = _session_payload(session_id)
    payload["saved"] = saved
    return _json_response(payload, session_id)
