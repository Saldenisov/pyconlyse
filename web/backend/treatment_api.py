import os
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
from uuid import uuid4

from flask import Blueprint, jsonify, request

from folder_api import get_allowed_root, get_treatment_root_base, set_allowed_root
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
        "status_label": "Treatment session is ready.",
        "noise_ready": False,
        "result_ready": False,
        "result_shape": None,
        "result_source_path": "",
    }


class TreatmentSessionStore:
    def __init__(self):
        self._lock = Lock()
        self._sessions: Dict[str, Dict[str, object]] = {}

    @staticmethod
    def _clone_state(state: Dict[str, object]) -> Dict[str, object]:
        snapshot = dict(state)
        snapshot["paths"] = dict(state["paths"])
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
                if not os.path.isdir(save_folder):
                    raise ValueError("save_folder does not exist")
                state["save_folder"] = save_folder

            if "save_file_name" in payload:
                save_file_name = os.path.basename(str(payload["save_file_name"]).strip())
                state["save_file_name"] = save_file_name

            state["status_label"] = "Treatment session updated."

        return self.snapshot(session_id)

    def set_folder(self, session_id: str, folder_path: str) -> Dict[str, object]:
        folder = _ensure_within_allowed_root(folder_path)
        if not os.path.isdir(folder):
            raise ValueError("Selected folder does not exist")

        with self._lock:
            state = self._get_or_create_state(session_id)
            state["folder_path"] = folder
            if not state["save_folder"]:
                state["save_folder"] = folder
            state["status_label"] = f"Folder selected: {folder}"

        return self.snapshot(session_id)

    def set_data_path(self, session_id: str, data_type: str, file_path: str) -> Dict[str, object]:
        if data_type not in DATA_TYPES:
            raise ValueError(f"Unsupported data_type '{data_type}'")

        normalized = _ensure_within_allowed_root(file_path)
        if not os.path.isfile(normalized):
            raise ValueError("Selected file does not exist")

        with self._lock:
            state = self._get_or_create_state(session_id)
            state["paths"][data_type] = normalized
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
                if active_data_type and active_data_type not in DATA_TYPES:
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
        "allowed_root_exists": os.path.isdir(allowed_root),
        "treatment_root_base": _normalize_path(get_treatment_root_base()),
        "exp_types": EXP_TYPES,
        "data_types": DATA_TYPES,
        "calc_modes": CALC_MODES,
        "supported_suffixes": list(treatment_service.supported_suffixes),
        "success": True,
    }


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
        set_allowed_root(str(root_path))
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


@treatment_api.route("/session/path", methods=["POST"])
def set_session_path():
    session_id = _current_session_id()
    payload = request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return _error("data_type and file_path are required", session_id)

    try:
        session_store.set_data_path(session_id, str(data_type), str(file_path))
        treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response(_session_payload(session_id), session_id)


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

    if not os.path.isdir(normalized):
        return _error("Folder does not exist", session_id, 404)

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
        normalized = _ensure_within_allowed_root(file_path)
        file_info = treatment_service.get_file_info(Path(normalized))
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"file_info": file_info, "success": True}, session_id)


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
        normalized = _ensure_within_allowed_root(file_path)
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
        selection = treatment_service.get_selection_view(session_store.snapshot(session_id))
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
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"cleaning": summary, "success": True}, session_id)


@treatment_api.route("/cleaning/reset", methods=["POST"])
def reset_sam_cleaning():
    session_id = _current_session_id()

    try:
        summary = treatment_service.reset_sam_cleaning(
            session_id,
            session_store.snapshot(session_id),
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"cleaning": summary, "success": True}, session_id)


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
        saved = treatment_service.save_sam_cleaned_h5(
            session_id,
            session_store.snapshot(session_id),
            angle_threshold,
            surface_threshold,
            output_file_name=output_file_name,
        )
    except ValueError as exc:
        return _error(str(exc), session_id)

    return _json_response({"cleaning": saved, "success": True}, session_id)


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
        normalized = _ensure_within_allowed_root(str(raw_file_path))
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
