"""Session configuration, selection, calculation, and save handlers."""

from typing import Dict
from typing import List
from typing import Optional
from uuid import uuid4
import os
import re


def _current_session_id() -> str:
    import treatment_api as api

    session_id = (
        api.request.headers.get("X-Treatment-Session-Id")
        or api.request.cookies.get(api.TREATMENT_SESSION_COOKIE)
        or ""
    ).strip()
    if session_id:
        return session_id
    return uuid4().hex


def _session_payload(session_id: str) -> Dict[str, object]:
    import treatment_api as api

    session = api.session_store.snapshot(session_id)
    runtime = api.treatment_service.runtime_status(session_id)
    preview_request = session.get("cleaning_preview_request") or {}
    if preview_request and not runtime.get("cleaning_ready"):
        try:
            if str(preview_request.get("file_path") or "") != str(
                (session.get("paths") or {}).get(session.get("active_data_type")) or ""
            ):
                raise ValueError("Cleaning preview source changed")
            recovery_summary = api.treatment_service.analyze_sam_cleaning(
                session_id,
                session,
                float(preview_request["angle_threshold"]),
                float(preview_request["surface_threshold"]),
            )
            if not recovery_summary.get("state_updated"):
                raise ValueError("Cleaning preview no longer has accepted measurements")
            runtime = api.treatment_service.runtime_status(session_id)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            api.session_store.set_cleaning_preview_request(session_id, None)
            session["cleaning_recovery_error"] = str(exc)
    if session.get("result_ready") and not runtime.get("result_ready") and not runtime.get("cleaning_ready"):
        try:
            recovery_state = dict(session)
            recovery_state["include_excluded_maps"] = (
                session.get("result_map_policy") == "all_raw_maps"
            )
            api.treatment_service.calc_abs(session_id, recovery_state)
            runtime = api.treatment_service.runtime_status(session_id)
        except (ValueError, OSError) as exc:
            api.session_store.mark_result_ready(session_id, False)
            session["result_recovery_error"] = str(exc)
    session.update(runtime)
    required_data_types = api.REQUIRED_DATA_TYPES.get(str(session.get("exp_type")), api.DATA_TYPES)
    paths = session.get("paths") or {}
    missing_data_types = [
        data_type for data_type in required_data_types if not paths.get(data_type)
    ]
    session["required_data_types"] = list(required_data_types)
    session["missing_data_types"] = missing_data_types
    session["ready_for_calc"] = len(missing_data_types) == 0
    session["map_selections"] = {
        data_type: api._map_selection_status(str(file_path))
        for data_type, file_path in paths.items()
        if file_path
    }
    preview_file_path = str(runtime.get("cleaning_file_path") or "")
    normalized_preview_path = api._normalize_path(preview_file_path) if preview_file_path else ""
    preview_data_type = next(
        (
            data_type
            for data_type, file_path in paths.items()
            if file_path and api._normalize_path(str(file_path)) == normalized_preview_path
        ),
        "",
    )
    session["cleaning_preview"] = {
        "ready": bool(runtime.get("cleaning_ready")),
        "file_path": preview_file_path,
        "data_type": preview_data_type,
        "current_measurements": int(runtime.get("cleaning_current_measurements") or 0),
        "original_measurements": int(runtime.get("cleaning_original_measurements") or 0),
    }
    allowed_root = api._normalize_path(api.get_allowed_root())
    return {
        "session_id": session_id,
        "session_persistence": "sqlite" if api._state_repository else "process_local",
        "root_restore_error": api._root_restore_error,
        "session": session,
        "allowed_root": allowed_root,
        "allowed_root_exists": api._root_exists(allowed_root),
        "treatment_root_base": api._normalize_path(api.get_treatment_root_base()),
        "treatment_root_bases": [api._normalize_path(root_base) for root_base in api.get_treatment_root_bases()],
        "cache_root": str(api.get_cache_root()),
        "cache_limit_bytes": api.get_cache_limit_bytes(),
        "exp_types": api.EXP_TYPES,
        "data_types": api.DATA_TYPES,
        "calc_modes": api.CALC_MODES,
        "supported_suffixes": list(api.treatment_service.supported_suffixes),
        "success": True,
    }


def _active_assignable_data_type(session: Dict[str, object]) -> str:
    import treatment_api as api

    paths = session.get("paths") or {}
    active_data_type = str(session.get("active_data_type") or "").strip()
    if active_data_type in api.DATA_TYPES and paths.get(active_data_type):
        return active_data_type
    for data_type in api.DATA_TYPES:
        if paths.get(data_type):
            return data_type
    return ""


def _auto_calc_od_if_ready(
    session_id: str, *, include_excluded_maps: bool = False
) -> Optional[Dict[str, object]]:
    import treatment_api as api

    session = api._session_payload(session_id)["session"]
    if not session.get("ready_for_calc"):
        return None
    calculation_state = api.session_store.snapshot(session_id)
    calculation_state["include_excluded_maps"] = include_excluded_maps
    result = api.treatment_service.calc_abs(session_id, calculation_state)
    api.session_store.mark_result_ready(
        session_id,
        True,
        "all_raw_maps" if include_excluded_maps else "selected_maps",
    )
    api.session_store.update_selection(session_id, {"active_data_type": "OD", "map_index": 0})
    return result


def _json_response(payload: Dict[str, object], session_id: str, status_code: int = 200):
    import treatment_api as api

    response = api.jsonify(payload)
    response.status_code = status_code
    response.set_cookie(
        api.TREATMENT_SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="Lax",
    )
    return response


def _error(message: str, session_id: str, status_code: int = 400):
    import treatment_api as api

    return api._json_response({"error": message, "success": False}, session_id, status_code)


def get_session():
    import treatment_api as api

    session_id = api._current_session_id()
    return api._json_response(api._session_payload(session_id), session_id)


def reset_session():
    import treatment_api as api

    session_id = api._current_session_id()
    api.session_store.reset(session_id)
    api.treatment_service.reset_runtime(session_id)
    return api._json_response(api._session_payload(session_id), session_id)


def _saved_session_profile(session_id):
    match = re.search(r":profile:(vd2|v0)(?::workspace:[A-Za-z0-9-]+)?$", session_id)
    return match.group(1) if match else None


def _saved_session_browser(session_id):
    import treatment_api as api

    browser = api.workspace_identity(api.request.headers.get("X-Workspace-Browser"))
    if not session_id.startswith(f"browser:{browser}:") or api._saved_session_profile(session_id) is None:
        raise ValueError("Treatment session does not belong to this browser")
    return browser


def saved_treatment_sessions():
    import treatment_api as api

    session_id = api._current_session_id()
    try:
        browser = api._saved_session_browser(session_id)
        return api._json_response(dict(success=True, sessions=api.session_store.saved_sessions(browser, api._saved_session_profile(session_id))), session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)


def copy_treatment_session():
    import treatment_api as api

    session_id = api._current_session_id()
    try:
        browser = api._saved_session_browser(session_id)
        payload = api.request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {"source_session_id"}:
            raise ValueError("One saved source session is required")
        source = payload["source_session_id"]
        if not isinstance(source, str) or not source.startswith(f"browser:{browser}:") or api._saved_session_profile(source) != api._saved_session_profile(session_id):
            raise ValueError("Saved treatment session belongs to another browser/profile")
        queue = api.treatment_queue_store.snapshot(session_id)
        if source == session_id or queue.get("running") or queue.get("jobs"):
            return api._error("Restore into a new, empty workspace", session_id, 409)
        if not api.session_store.copy_saved_session(source, session_id):
            return api._error("Restore into a new, empty workspace", session_id, 409)
        # Queue jobs are deliberately not cloned or started. Runtime recovery
        # uses the existing treatment/session GET after opening the new view.
        return api._json_response(dict(success=True, restored=True), session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)


def restore_session_from_browser():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    try:
        restored = api.session_store.restore_if_empty(session_id, payload.get("session"))
    except ValueError as exc:
        return api._error(str(exc), session_id)
    response_payload = api._session_payload(session_id)
    response_payload["restored"] = restored
    return api._json_response(response_payload, session_id)


def update_session_config():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    try:
        previous_session = api.session_store.snapshot(session_id)
        updated_session = api.session_store.update_config(session_id, payload)
        reset_fields = {
            "exp_type",
            "selected_data_type",
            "calc_mode",
            "first_map_with_electrons",
        }
        if any(
            field in payload and previous_session.get(field) != updated_session.get(field)
            for field in reset_fields
        ):
            api.treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)
    return api._json_response(api._session_payload(session_id), session_id)


def update_session_root():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    root_path = payload.get("allowed_root") or payload.get("root_path")
    if not root_path:
        return api._error("allowed_root is required", session_id)

    try:
        previous_root = api._normalize_path(api.get_allowed_root())
        normalized_root = api.set_allowed_root(str(root_path))
        if api._state_repository:
            api._state_repository.save_setting("allowed_root", normalized_root)
        api._clear_root_exists_cache(previous_root)
        api._clear_root_exists_cache(api._normalize_path(str(root_path)))
        api.session_store.reset(session_id)
        api.treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response(api._session_payload(session_id), session_id)


def set_session_folder():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    folder_path = payload.get("folder_path")
    if not folder_path:
        return api._error("folder_path is required", session_id)

    try:
        api.session_store.set_folder(session_id, str(folder_path))
        api.treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response(api._session_payload(session_id), session_id)


def set_session_path():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return api._error("data_type and file_path are required", session_id)

    try:
        api.session_store.set_data_path(
            session_id,
            str(data_type),
            str(file_path),
            source_path=str(file_path),
        )
        api.treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response(api._session_payload(session_id), session_id)


def cache_and_set_session_path():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return api._error("data_type and file_path are required", session_id)

    try:
        source_path = api._ensure_within_allowed_root(str(file_path))
        cached = api._cache_assignable_source(source_path)
        api.session_store.set_data_path(
            session_id,
            str(data_type),
            str(cached["cached_path"]),
            source_path=str(cached["source_path"]),
        )
        api.treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    response_payload = api._session_payload(session_id)
    response_payload["cached_file"] = cached
    return api._json_response(response_payload, session_id)


def compress_and_set_session_path():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    data_type = payload.get("data_type")
    file_path = payload.get("file_path")
    if not data_type or not file_path:
        return api._error("data_type and file_path are required", session_id)

    try:
        source_path = api._ensure_within_allowed_root(str(file_path))
        conversion = api._convert_source_to_h5(source_path)
        output_path = str(conversion["output_path"])
        cached = api._cache_assignable_source(output_path)
        api.session_store.set_data_path(
            session_id,
            str(data_type),
            str(cached["cached_path"]),
            source_path=str(cached["source_path"]),
        )
        api.treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    response_payload = api._session_payload(session_id)
    response_payload["cached_file"] = cached
    response_payload["conversion"] = conversion
    return api._json_response(response_payload, session_id)


def auto_assign_session_paths():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    folder = payload.get("folder_path") or api.session_store.snapshot(session_id).get("folder_path")
    if not folder:
        return api._error("folder_path is required", session_id)

    try:
        normalized_folder = api._ensure_within_allowed_root(str(folder))
    except ValueError as exc:
        return api._error(str(exc), session_id, 403)

    try:
        folder_exists = api._folder_exists(normalized_folder)
    except ValueError as exc:
        return api._error(str(exc), session_id)
    if not folder_exists:
        return api._error("Folder does not exist", session_id, 404)

    session = api.session_store.snapshot(session_id)
    exp_type = str(session.get("exp_type"))
    required_data_types = api.REQUIRED_DATA_TYPES.get(exp_type, [])
    supported_suffixes = set(api.treatment_service.supported_suffixes)
    candidates: Dict[str, List[str]] = {data_type: [] for data_type in required_data_types}

    if api.is_smb_path(normalized_folder):
        entries = api.smb_listdir(normalized_folder)
        for entry in entries:
            if not entry["is_file"]:
                continue
            file_path = str(entry["path"])
            if api._path_suffix(file_path) not in supported_suffixes:
                continue
            data_type = api._file_data_type_candidate(str(entry["name"]), exp_type)
            if data_type in candidates:
                candidates[data_type].append(file_path)
    else:
        with os.scandir(normalized_folder) as entries:
            for entry in entries:
                if not entry.is_file():
                    continue
                file_path = entry.path
                if api._path_suffix(file_path) not in supported_suffixes:
                    continue
                data_type = api._file_data_type_candidate(entry.name, exp_type)
                if data_type in candidates:
                    candidates[data_type].append(file_path)

    assigned: Dict[str, str] = {}
    cached_files: Dict[str, Dict[str, object]] = {}
    try:
        api.session_store.set_folder(session_id, normalized_folder)
        for data_type in required_data_types:
            matches = sorted(candidates.get(data_type, []), key=api._candidate_sort_key)
            if not matches:
                continue
            selected_path = matches[0]
            source_path = selected_path
            if api.is_smb_path(selected_path):
                cached = api._cache_assignable_source(selected_path)
                assigned_path = str(cached["cached_path"])
                source_path = str(cached["source_path"])
                cached_files[data_type] = cached
            else:
                assigned_path = str(selected_path)
            api.session_store.set_data_path(
                session_id,
                data_type,
                assigned_path,
                source_path=source_path,
            )
            assigned[data_type] = assigned_path
        api.treatment_service.reset_runtime(session_id)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    response_payload = api._session_payload(session_id)
    response_payload["auto_assigned"] = assigned
    response_payload["auto_assigned_cached_files"] = cached_files
    response_payload["auto_assign_missing"] = [
        data_type for data_type in required_data_types if data_type not in assigned
    ]
    return api._json_response(response_payload, session_id)


def update_session_selection():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}

    try:
        api.session_store.update_selection(session_id, payload)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response(api._session_payload(session_id), session_id)


def calc_abs():
    import treatment_api as api

    session_id = api._current_session_id()
    try:
        if api.treatment_service.runtime_status(session_id).get("cleaning_ready"):
            raise ValueError(
                "Cleaning preview is not applied; apply mask to H5 or reset preview."
            )
        result = api.treatment_service.calc_abs(session_id, api.session_store.snapshot(session_id))
        api.session_store.mark_result_ready(session_id, True)
        api.session_store.update_selection(session_id, {"active_data_type": "OD", "map_index": 0})
    except ValueError as exc:
        return api._error(str(exc), session_id)

    payload = api._session_payload(session_id)
    payload["result"] = result
    return api._json_response(payload, session_id)


def save_result():
    import treatment_api as api

    session_id = api._current_session_id()
    session_state = api.session_store.snapshot(session_id)
    output_path = api._configured_result_output_path(session_state)
    reservation_owner = None
    try:
        reservation_owner = api.treatment_queue_store.reserve_immediate_output(output_path)
        saved = api.treatment_service.save_result(session_id, session_state)
        api.record_treatment_manifest(
            saved,
            session_state=session_state,
            workflow={"kind": "immediate"},
        )
    except (ValueError, OSError) as exc:
        return api._error(str(exc), session_id)
    finally:
        api.treatment_queue_store.release_immediate_output(output_path, reservation_owner)

    payload = api._session_payload(session_id)
    payload["saved"] = saved
    return api._json_response(payload, session_id)
