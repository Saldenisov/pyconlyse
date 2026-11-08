"""File inspection, compression, caching, and preview handlers."""

from pathlib import Path
from typing import Dict
from typing import List
from uuid import uuid4
import os


def _cache_assignable_source(source_path: str) -> Dict[str, object]:
    import treatment_api as api

    if api.is_smb_path(source_path):
        mapped_file = api._mapped_smb_local_file(source_path)
        if mapped_file:
            stat = os.stat(mapped_file)
            return {
                "source_path": api._normalize_path(source_path),
                "cached_path": mapped_file,
                "copied": False,
                "size_bytes": int(stat.st_size),
                "cache": {
                    "cache_root": api.get_cache_root(),
                    "limit_bytes": api.get_cache_limit_bytes(),
                    "removed": [],
                    "size_bytes": 0,
                    "local_map": True,
                },
            }
        if not api.smb_isfile(source_path):
            raise ValueError("Selected file does not exist")
        return api.cache_external_file(
            source_path,
            api.smb_name(source_path),
            lambda target_path: api.copy_smb_file_to_local(source_path, target_path),
        )

    if not os.path.isfile(source_path):
        raise ValueError("Selected file does not exist")
    return api.cache_file(source_path)


def compress_file_path():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    file_path = payload.get("file_path")
    if not file_path:
        return api._error("file_path is required", session_id)

    try:
        source_path = api._ensure_within_allowed_root(str(file_path))
        conversion = api._convert_source_to_h5(source_path)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    response_payload = api._session_payload(session_id)
    response_payload["conversion"] = conversion
    return api._json_response(response_payload, session_id)


def start_compress_file_path():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    file_path = payload.get("file_path")
    if not file_path:
        return api._error("file_path is required", session_id)

    try:
        source_path = api._ensure_within_allowed_root(str(file_path))
    except ValueError as exc:
        return api._error(str(exc), session_id)

    job_id = uuid4().hex
    with api._compression_jobs_lock:
        api._compression_jobs[job_id] = {
            "job_id": job_id,
            "status": "running",
            "phase": "queued",
            "message": "Queued Convert/Compress",
            "source_path": source_path,
            "current_bytes": 0,
            "total_bytes": 0,
            "created_at": api.monotonic(),
            "updated_at": api.monotonic(),
        }

    thread = api.Thread(
        target=api._run_compression_job,
        args=(job_id, session_id, source_path),
        daemon=True,
    )
    thread.start()
    return api._json_response({"compression_job": api._compression_job_snapshot(job_id), "success": True}, session_id)


def get_compress_file_status(job_id: str):
    import treatment_api as api

    session_id = api._current_session_id()
    job = api._compression_job_snapshot(str(job_id))
    if not job:
        return api._error("compression job not found", session_id, 404)
    return api._json_response({"compression_job": job, "success": True}, session_id)


def list_files():
    import treatment_api as api

    session_id = api._current_session_id()
    folder = api.request.args.get("folder") or api.session_store.snapshot(session_id).get("folder_path")
    if not folder:
        return api._json_response(
            {"folder": "", "folders": [], "files": [], "success": True},
            session_id,
        )

    try:
        normalized = api._ensure_within_allowed_root(folder)
    except ValueError as exc:
        return api._error(str(exc), session_id, 403)

    try:
        folder_exists = api._folder_exists(normalized)
    except ValueError as exc:
        return api._error(str(exc), session_id)
    if not folder_exists:
        return api._error("Folder does not exist", session_id, 404)

    folders: List[Dict[str, str]] = []
    files: List[Dict[str, object]] = []
    try:
        mapped_folder = api._mapped_smb_local_dir(normalized) if api.is_smb_path(normalized) else None
        if mapped_folder:
            with os.scandir(mapped_folder) as entries:
                for entry in entries:
                    mapped_path = api.smb_join(normalized, entry.name)
                    if entry.is_dir():
                        folders.append({"name": entry.name, "path": mapped_path})
                    elif entry.is_file():
                        suffix = os.path.splitext(entry.name)[1].lower()
                        files.append(
                            {
                                "name": entry.name,
                                "path": mapped_path,
                                "suffix": suffix,
                                "size_bytes": int(entry.stat().st_size),
                                "supported": suffix in api.treatment_service.supported_suffixes,
                            }
                        )
        elif api.is_smb_path(normalized):
            entries = api.smb_listdir(normalized)
            for entry in entries:
                if entry["is_dir"]:
                    folders.append({"name": entry["name"], "path": entry["path"]})
                elif entry["is_file"]:
                    suffix = api.smb_suffix(str(entry["path"]))
                    files.append(
                        {
                            "name": entry["name"],
                            "path": entry["path"],
                            "suffix": suffix,
                            "size_bytes": int(entry.get("size_bytes") or 0),
                            "supported": suffix in api.treatment_service.supported_suffixes,
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
                                "supported": suffix in api.treatment_service.supported_suffixes,
                            }
                        )
    except ValueError as exc:
        return api._error(str(exc), session_id)

    folders.sort(key=lambda item: item["name"].lower())
    files.sort(key=lambda item: item["name"].lower())

    return api._json_response(
        {
            "folder": normalized,
            "folders": folders,
            "files": files,
            "success": True,
        },
        session_id,
    )


def get_file_info():
    import treatment_api as api

    session_id = api._current_session_id()
    file_path = api.request.args.get("file_path")
    data_type = api.request.args.get("data_type")
    if not file_path and data_type:
        file_path = api.session_store.snapshot(session_id).get("paths", {}).get(data_type)
    if not file_path:
        return api._error("file_path or data_type is required", session_id)

    try:
        normalized = api._ensure_readable_treatment_file(file_path)
        file_info = api.treatment_service.get_file_info(Path(normalized))
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response({"file_info": file_info, "success": True}, session_id)


def get_file_summary():
    import treatment_api as api

    session_id = api._current_session_id()
    file_path = api.request.args.get("file_path")
    if not file_path:
        return api._error("file_path is required", session_id)

    try:
        source_path = api._ensure_within_allowed_root(file_path)
        suffix = api._path_suffix(source_path)
        if suffix not in {".his", ".h5", ".dat"}:
            return api._json_response({"file_summary": {}, "success": True}, session_id)

        if api.is_smb_path(source_path):
            cached = api._cache_assignable_source(source_path)
            readable_path = str(cached["cached_path"])
        else:
            readable_path = api._ensure_readable_treatment_file(source_path)

        file_info = api.treatment_service.get_file_info(Path(readable_path))
        time_scale = str(file_info.get("time_scale") or "").strip()
        if not time_scale or time_scale == "??":
            time_scale = api._infer_time_scale_from_path(source_path)
        file_summary = {
            "file_path": source_path,
            "number_maps": file_info.get("number_maps"),
            "original_number_maps": file_info.get("original_number_maps"),
            "time_scale": time_scale,
            "timedelay_min": file_info.get("timedelay_min"),
            "timedelay_max": file_info.get("timedelay_max"),
            "wavelength_min": file_info.get("wavelength_min"),
            "wavelength_max": file_info.get("wavelength_max"),
        }
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response({"file_summary": file_summary, "success": True}, session_id)


def preview_file():
    import treatment_api as api

    session_id = api._current_session_id()
    file_path = api.request.args.get("file_path")
    data_type = api.request.args.get("data_type")
    if not file_path and data_type:
        file_path = api.session_store.snapshot(session_id).get("paths", {}).get(data_type)
    if not file_path:
        return api._error("file_path or data_type is required", session_id)

    try:
        map_index = int(api.request.args.get("map_index", "0"))
    except ValueError:
        return api._error("map_index must be an integer", session_id)

    try:
        normalized = api._ensure_readable_treatment_file(file_path)
        preview = api.treatment_service.get_preview(Path(normalized), map_index=map_index)
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response({"preview": preview, "success": True}, session_id)


def average_noise():
    import treatment_api as api

    session_id = api._current_session_id()
    try:
        summary = api.treatment_service.average_noise(session_id, api.session_store.snapshot(session_id))
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response({"noise": summary, **api._session_payload(session_id)}, session_id)


def open_dat_preview():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    try:
        source = api._ensure_readable_treatment_file(str(payload.get("file_path") or ""))
        if api._path_suffix(source) != ".dat":
            raise ValueError("Preview requires a DAT file")
        cached = api._cache_assignable_source(source)
        path = str(cached["cached_path"])
        # Validate before changing the preview. ABS/BASE/NOISE assignments and
        # calculated results remain independent of the inspected DAT.
        api.treatment_service._read_od_dat(Path(path))
        api.treatment_service.get_selection_view({"active_data_type": "DAT", "dat_preview_path": path})
        api.session_store.set_dat_preview(session_id, path)
        return api._json_response({"success": True, "preview_source": source}, session_id)
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return api._error(str(exc), session_id)


def get_selection():
    import treatment_api as api

    session_id = api._current_session_id()
    try:
        selection = api.treatment_service.get_selection_view(
            api.session_store.snapshot(session_id),
            session_id=session_id,
        )
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response({"selection": selection, "success": True}, session_id)


def export_selection_average():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    user_type = str(payload.get("user_type") or "").strip().lower()
    ranges_text = str(payload.get("ranges") or "")

    if not user_type:
        return api._error("user_type is required", session_id)

    try:
        exported = api.treatment_service.export_selection_average(
            api.session_store.snapshot(session_id),
            user_type,
            ranges_text,
        )
    except ValueError as exc:
        return api._error(str(exc), session_id)

    response_payload = api._session_payload(session_id)
    response_payload["exported"] = exported
    return api._json_response(response_payload, session_id)
