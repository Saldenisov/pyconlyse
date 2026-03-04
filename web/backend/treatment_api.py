import os
from pathlib import Path
from threading import Lock
from typing import Dict, List

from flask import Blueprint, jsonify, request

from folder_api import get_allowed_root
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


def _normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(str(path).strip()))


def _is_within_allowed_root(path: str) -> bool:
    allowed_root = _normalize_path(get_allowed_root())
    candidate = _normalize_path(path)
    try:
        return os.path.commonpath([candidate, allowed_root]) == allowed_root
    except ValueError:
        return False


def _ensure_within_allowed_root(path: str) -> str:
    normalized = _normalize_path(path)
    if not _is_within_allowed_root(normalized):
        raise ValueError("Path is outside the allowed treatment root")
    return normalized


def _default_folder() -> str:
    folder = _normalize_path(get_allowed_root())
    if os.path.isdir(folder):
        return folder
    return ""


def _default_state() -> Dict[str, object]:
    folder = _default_folder()
    return {
        "exp_type": EXP_TYPES[1],
        "selected_data_type": DATA_TYPES[0],
        "calc_mode": CALC_MODES[0],
        "first_map_with_electrons": True,
        "folder_path": folder,
        "save_folder": folder,
        "save_file_name": "",
        "paths": {},
        "status_label": "Treatment session is ready.",
        "noise_ready": False,
        "result_ready": False,
        "result_shape": None,
        "result_source_path": "",
    }


class TreatmentSessionStore:
    def __init__(self):
        self._lock = Lock()
        self._state = _default_state()

    def snapshot(self) -> Dict[str, object]:
        with self._lock:
            state = dict(self._state)
            state["paths"] = dict(self._state["paths"])
        return state

    def reset(self) -> Dict[str, object]:
        with self._lock:
            self._state = _default_state()
        return self.snapshot()

    def update_config(self, payload: Dict[str, object]) -> Dict[str, object]:
        with self._lock:
            if "exp_type" in payload:
                exp_type = str(payload["exp_type"])
                if exp_type not in EXP_TYPES:
                    raise ValueError(f"Unsupported exp_type '{exp_type}'")
                self._state["exp_type"] = exp_type

            if "selected_data_type" in payload:
                selected_data_type = str(payload["selected_data_type"])
                if selected_data_type not in DATA_TYPES:
                    raise ValueError(
                        f"Unsupported selected_data_type '{selected_data_type}'"
                    )
                self._state["selected_data_type"] = selected_data_type

            if "calc_mode" in payload:
                calc_mode = str(payload["calc_mode"])
                if calc_mode not in CALC_MODES:
                    raise ValueError(f"Unsupported calc_mode '{calc_mode}'")
                self._state["calc_mode"] = calc_mode

            if "first_map_with_electrons" in payload:
                self._state["first_map_with_electrons"] = bool(
                    payload["first_map_with_electrons"]
                )

            if "save_folder" in payload:
                save_folder = _ensure_within_allowed_root(str(payload["save_folder"]))
                if not os.path.isdir(save_folder):
                    raise ValueError("save_folder does not exist")
                self._state["save_folder"] = save_folder

            if "save_file_name" in payload:
                save_file_name = os.path.basename(str(payload["save_file_name"]).strip())
                self._state["save_file_name"] = save_file_name

            self._state["status_label"] = "Treatment session updated."

        return self.snapshot()

    def set_folder(self, folder_path: str) -> Dict[str, object]:
        folder = _ensure_within_allowed_root(folder_path)
        if not os.path.isdir(folder):
            raise ValueError("Selected folder does not exist")

        with self._lock:
            self._state["folder_path"] = folder
            if not self._state["save_folder"]:
                self._state["save_folder"] = folder
            self._state["status_label"] = f"Folder selected: {folder}"

        return self.snapshot()

    def set_data_path(self, data_type: str, file_path: str) -> Dict[str, object]:
        if data_type not in DATA_TYPES:
            raise ValueError(f"Unsupported data_type '{data_type}'")

        normalized = _ensure_within_allowed_root(file_path)
        if not os.path.isfile(normalized):
            raise ValueError("Selected file does not exist")

        with self._lock:
            self._state["paths"][data_type] = normalized
            if not self._state["save_file_name"]:
                stem = os.path.splitext(os.path.basename(normalized))[0]
                self._state["save_file_name"] = f"{stem}.dat"
            self._state["status_label"] = f"{data_type} file selected."

        return self.snapshot()


session_store = TreatmentSessionStore()
treatment_service = TreatmentDataService()


def _session_payload() -> Dict[str, object]:
    runtime = treatment_service.runtime_status()
    session = session_store.snapshot()
    session.update(runtime)
    return {
        "session": session,
        "allowed_root": _normalize_path(get_allowed_root()),
        "exp_types": EXP_TYPES,
        "data_types": DATA_TYPES,
        "calc_modes": CALC_MODES,
        "supported_suffixes": list(treatment_service.supported_suffixes),
        "success": True,
    }


def _error(message: str, status_code: int = 400):
    return jsonify({"error": message, "success": False}), status_code


@treatment_api.route("/session", methods=["GET"])
def get_session():
    return jsonify(_session_payload())


@treatment_api.route("/session/reset", methods=["POST"])
def reset_session():
    session_store.reset()
    treatment_service.reset_runtime()
    return jsonify(_session_payload())


@treatment_api.route("/session/config", methods=["POST"])
def update_session_config():
    payload = request.get_json(silent=True) or {}
    try:
        session_store.update_config(payload)
        treatment_service.reset_runtime()
    except ValueError as exc:
        return _error(str(exc))
    return jsonify(_session_payload())


@treatment_api.route("/session/folder", methods=["POST"])
def set_session_folder():
    payload = request.get_json(silent=True) or {}
    folder_path = payload.get("folder_path")
    if not folder_path:
        return _error("folder_path is required")

    try:
        session_store.set_folder(str(folder_path))
        treatment_service.reset_runtime()
    except ValueError as exc:
        return _error(str(exc))

    return jsonify(_session_payload())


@treatment_api.route("/session/path", methods=["POST"])
def set_session_path():
    payload = request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return _error("data_type and file_path are required")

    try:
        session_store.set_data_path(str(data_type), str(file_path))
        treatment_service.reset_runtime()
    except ValueError as exc:
        return _error(str(exc))

    return jsonify(_session_payload())


@treatment_api.route("/files", methods=["GET"])
def list_files():
    folder = request.args.get("folder") or session_store.snapshot().get("folder_path")
    if not folder:
        return jsonify({"folder": "", "folders": [], "files": [], "success": True})

    try:
        normalized = _ensure_within_allowed_root(folder)
    except ValueError as exc:
        return _error(str(exc), 403)

    if not os.path.isdir(normalized):
        return _error("Folder does not exist", 404)

    folders: List[Dict[str, str]] = []
    files: List[Dict[str, object]] = []
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
                        "supported": suffix in treatment_service.supported_suffixes,
                    }
                )

    folders.sort(key=lambda item: item["name"].lower())
    files.sort(key=lambda item: item["name"].lower())

    return jsonify(
        {
            "folder": normalized,
            "folders": folders,
            "files": files,
            "success": True,
        }
    )


@treatment_api.route("/file-info", methods=["GET"])
def get_file_info():
    file_path = request.args.get("file_path")
    data_type = request.args.get("data_type")
    if not file_path and data_type:
        file_path = session_store.snapshot().get("paths", {}).get(data_type)
    if not file_path:
        return _error("file_path or data_type is required")

    try:
        normalized = _ensure_within_allowed_root(file_path)
        file_info = treatment_service.get_file_info(Path(normalized))
    except ValueError as exc:
        return _error(str(exc))

    return jsonify({"file_info": file_info, "success": True})


@treatment_api.route("/preview", methods=["GET"])
def preview_file():
    file_path = request.args.get("file_path")
    data_type = request.args.get("data_type")
    if not file_path and data_type:
        file_path = session_store.snapshot().get("paths", {}).get(data_type)
    if not file_path:
        return _error("file_path or data_type is required")

    try:
        map_index = int(request.args.get("map_index", "0"))
    except ValueError:
        return _error("map_index must be an integer")

    try:
        normalized = _ensure_within_allowed_root(file_path)
        preview = treatment_service.get_preview(Path(normalized), map_index=map_index)
    except ValueError as exc:
        return _error(str(exc))

    return jsonify({"preview": preview, "success": True})


@treatment_api.route("/average-noise", methods=["POST"])
def average_noise():
    try:
        summary = treatment_service.average_noise(session_store.snapshot())
    except ValueError as exc:
        return _error(str(exc))

    return jsonify({"noise": summary, **_session_payload()})


@treatment_api.route("/calc-abs", methods=["POST"])
def calc_abs():
    try:
        result = treatment_service.calc_abs(session_store.snapshot())
    except ValueError as exc:
        return _error(str(exc))

    payload = _session_payload()
    payload["result"] = result
    return jsonify(payload)


@treatment_api.route("/save", methods=["POST"])
def save_result():
    try:
        saved = treatment_service.save_result(session_store.snapshot())
    except ValueError as exc:
        return _error(str(exc))

    payload = _session_payload()
    payload["saved"] = saved
    return jsonify(payload)
