"""Folder-based input selection and background assignment handlers."""

from typing import Dict
from uuid import uuid4


def _set_inputs_from_folder_job_payload(session_id: str, payload: Dict[str, object], progress_callback=None, *, queue_job_id=None):
    import treatment_api as api

    folder_path = payload.get("folder_path")
    convert = bool(payload.get("convert", False))
    clean = bool(payload.get("clean", False))
    calculate = bool(payload.get("calculate", True))
    if clean:
        convert = True
    if not folder_path:
        raise ValueError("folder_path is required")

    try:
        angle_threshold = float(payload.get("angle_threshold", 1.0))
        surface_threshold = float(payload.get("surface_threshold", 1.0))
    except (TypeError, ValueError):
        raise ValueError("angle_threshold and surface_threshold must be numeric")

    folder = api._ensure_within_allowed_root(str(folder_path))
    if progress_callback:
        progress_callback("checking", 0, 0, f"Checking folder {folder}", {})
    if not api._folder_exists(folder):
        raise ValueError("Folder does not exist")

    session = api.session_store.snapshot(session_id)
    exp_type = str(session.get("exp_type"))
    candidates = api._folder_input_candidates(folder, exp_type, convert=convert)
    tree_workflow = bool(queue_job_id and payload.get("_tree_workflow"))
    if exp_type == "HIS+NOISE" and not tree_workflow:
        separate_candidates = api._folder_input_candidates(folder, "ABS+BASE+NOISE", convert=convert)
        separate_found = {
            data_type: sorted(paths, key=api._convert_sort_key if convert else api._candidate_sort_key)
            for data_type, paths in separate_candidates.items()
            if paths
        }
        if "ABS" in separate_found and "BASE" in separate_found:
            exp_type = "ABS+BASE+NOISE"
            candidates = separate_candidates
            api.session_store.update_config(
                session_id,
                {"exp_type": exp_type, "selected_data_type": "ABS"},
            )
            if progress_callback:
                progress_callback(
                    "checking",
                    0,
                    0,
                    "Detected separate ABS/BASE folder; using ABS+BASE+NOISE mode",
                    {},
                )
    found = {
        data_type: sorted(paths, key=api._convert_sort_key if convert else api._candidate_sort_key)
        for data_type, paths in candidates.items()
        if paths
    }
    required_in_folder = api.REQUIRED_DATA_TYPES[exp_type] if tree_workflow and calculate else api._folder_required_input_types(exp_type)
    missing_in_folder = [
        data_type for data_type in required_in_folder if data_type not in found
    ]
    if missing_in_folder:
        names = ", ".join(sorted(found.keys())) or "none"
        missing = ", ".join(missing_in_folder)
        required = ", ".join(required_in_folder)
        raise ValueError(
            f"Folder must contain {required} for {exp_type}; missing {missing}; found {names}."
        )

    file_statuses = {
        data_type: {
            "source_path": paths[0],
            "status": "queued" if convert else "ready",
        }
        for data_type, paths in found.items()
    }
    total_items = len(file_statuses)
    if convert:
        has_smb_sources = any(
            api.is_smb_path(paths[0]) and not api._mapped_smb_local_file(paths[0])
            for paths in found.values()
            if paths
        )
        planned_workers = api._treatment_worker_count(len(found))
    else:
        has_smb_sources = False
        planned_workers = 0

    if progress_callback:
        convert_message = (
            f"SMB I/O sequential; converting {total_items} local files with {planned_workers} worker(s)"
            if has_smb_sources
            else f"Converting {total_items} files with {planned_workers} worker(s)"
        )
        progress_callback(
            "converting" if convert else "assigning",
            0,
            total_items,
            convert_message if convert else f"Assigning {total_items} files",
            file_statuses,
        )

    prepared: Dict[str, Dict[str, object]] = {}
    if convert:
        selected_paths = {
            data_type: paths[0]
            for data_type, paths in found.items()
        }
        status_lock = api.Lock()

        def set_file_status(data_type: str, **updates) -> Dict[str, Dict[str, object]]:
            with status_lock:
                file_statuses[data_type] = {**file_statuses.get(data_type, {}), **updates}
                return {key: dict(value) for key, value in file_statuses.items()}

        def item_progress(data_type: str, *args) -> None:
            if len(args) >= 4:
                phase, current, total, message = args[:4]
            elif len(args) >= 2:
                phase, current, total, message = "convert", args[0], args[1], "Converting"
            else:
                phase, current, total, message = "convert", 0, 0, "Converting"
            statuses = set_file_status(
                data_type,
                status="running",
                phase=str(phase),
                current=int(current or 0),
                total=int(total or 0),
                message=str(message),
            )
            if progress_callback:
                progress_callback(
                    "converting",
                    sum(1 for item in statuses.values() if item.get("status") == "complete"),
                    total_items,
                    f"{data_type}: {message}",
                    statuses,
                )

        completed = 0
        if any(api.is_smb_path(path) and not api._mapped_smb_local_file(path) for path in selected_paths.values()):
            try:
                conversion_results = api._convert_smb_sources_to_h5_pipeline(
                    selected_paths,
                    progress_callback=item_progress,
                )
            except Exception as exc:
                statuses = {
                    key: {
                        **value,
                        "status": "error" if value.get("status") == "running" else value.get("status", "queued"),
                        "error": str(exc) if value.get("status") == "running" else value.get("error", ""),
                    }
                    for key, value in file_statuses.items()
                }
                if progress_callback:
                    progress_callback("error", completed, total_items, str(exc), statuses)
                raise
            for data_type in selected_paths:
                conversion = conversion_results[data_type]
                completed += 1
                statuses = set_file_status(
                    data_type,
                    status="complete",
                    phase="complete",
                    output_path=str(conversion["output_path"]),
                    current=int(conversion.get("output_size_bytes") or 0),
                    total=int(conversion.get("output_size_bytes") or 0),
                    message="Complete",
                )
                prepared[data_type] = {
                    "source_path": str(conversion["output_path"]),
                    "conversion": conversion,
                }
                if api._path_suffix(str(conversion["output_path"])) != ".h5":
                    raise ValueError(
                        f"Set/Convert did not create H5 for {data_type}: {conversion['output_path']}"
                    )
                if progress_callback:
                    progress_callback(
                        "converting",
                        completed,
                        total_items,
                        f"Converted {completed}/{total_items} files",
                        statuses,
                    )
        else:
            for data_type, selected_path in selected_paths.items():
                statuses = set_file_status(data_type, status="running")
                if progress_callback:
                    progress_callback(
                        "converting", completed, total_items,
                        f"Converting {data_type}: {api._path_name(selected_path)}", statuses,
                    )

            def complete_conversion(data_type, conversion):
                nonlocal completed
                if api._path_suffix(str(conversion["output_path"])) != ".h5":
                    raise ValueError(
                        f"Set/Convert did not create H5 for {data_type}: {conversion['output_path']}"
                    )
                completed += 1
                statuses = set_file_status(
                    data_type,
                    status="complete",
                    phase="complete",
                    output_path=str(conversion["output_path"]),
                    current=int(conversion.get("output_size_bytes") or 0),
                    total=int(conversion.get("output_size_bytes") or 0),
                    message="Complete",
                )
                prepared[data_type] = {
                    "source_path": str(conversion["output_path"]),
                    "conversion": conversion,
                }
                if progress_callback:
                    progress_callback(
                        "converting", completed, total_items,
                        f"Converted {completed}/{total_items} files", statuses,
                    )

            def failed_conversion(data_type, exc):
                statuses = set_file_status(data_type, status="error", error=str(exc))
                if progress_callback:
                    progress_callback("error", completed, total_items, str(exc), statuses)

            api._run_parallel_cpu_jobs(
                {data_type: (selected_path,) for data_type, selected_path in selected_paths.items()},
                api._convert_folder_source_worker,
                on_progress=item_progress if progress_callback else None,
                on_complete=complete_conversion,
                on_error=failed_conversion,
            )
    else:
        for data_type, paths in found.items():
            prepared[data_type] = {
                "source_path": paths[0],
                "conversion": None,
            }

    if not payload.get("_preserve_selected_folder"):
        api.session_store.set_folder(session_id, folder)
    if tree_workflow:
        api.session_store.clear_folder_inputs(session_id)
    assigned: Dict[str, str] = {}
    cached_files: Dict[str, Dict[str, object]] = {}
    conversions: Dict[str, Dict[str, object]] = {}
    cleaned: Dict[str, Dict[str, object]] = {}
    for data_type, prepared_item in prepared.items():
        source_path = str(prepared_item["source_path"])
        if progress_callback:
            file_statuses[data_type] = {**file_statuses.get(data_type, {}), "status": "assigning"}
            assign_message = (
                f"Caching {data_type} from SMB"
                if api.is_smb_path(source_path)
                else f"Assigning {data_type}"
            )
            progress_callback("assigning", len(assigned), total_items, assign_message, file_statuses)
        cached = api._cache_assignable_source(source_path)
        api.session_store.set_data_path(
            session_id,
            data_type,
            str(cached["cached_path"]),
            source_path=str(cached["source_path"]),
        )
        assigned[data_type] = str(cached["cached_path"])
        cached_files[data_type] = cached
        if prepared_item["conversion"]:
            conversions[data_type] = prepared_item["conversion"]
        if progress_callback:
            file_statuses[data_type] = {**file_statuses.get(data_type, {}), "status": "assigned"}
            progress_callback("assigning", len(assigned), total_items, f"Assigned {len(assigned)}/{total_items} files", file_statuses)

    clean_sources = api._tree_cleaning_sources(cached_files) if tree_workflow and clean else None
    if tree_workflow and calculate and not clean:
        reused = api._tree_cleaning_for_calculation(session_id, folder, cached_files)
        for data_type, cached in reused.items():
            api.session_store.set_data_path(session_id, data_type, str(cached["cached_path"]),
                                        source_path=str(cached["source_path"]))
            assigned[data_type] = str(cached["cached_path"])
            cached_files[data_type] = cached

    if clean:
        cleaning_state = api.session_store.snapshot(session_id)
        cleaning_items = {
            data_type: (
                cleaning_state, angle_threshold, surface_threshold,
                f".{api._queue_cleaning_output_name(cached_files[data_type]['source_path'], data_type, queue_job_id)}"
                if tree_workflow else "",
            )
            for data_type in assigned
        }
        for data_type in cleaning_items:
            file_statuses[data_type] = {
                **file_statuses.get(data_type, {}),
                "status": "cleaning",
            }
        if progress_callback:
            progress_callback(
                "cleaning", 0, total_items,
                f"Cleaning {total_items} files with {api._treatment_worker_count(total_items)} worker(s)",
                file_statuses,
            )

        def assign_cleaned(data_type, saved):
            output_path = str(saved.get("output_path") or "")
            if output_path:
                if api.is_smb_path(output_path):
                    cleaned_cache = api._cache_assignable_source(output_path)
                    assigned_path = str(cleaned_cache["cached_path"])
                    source_path = str(cleaned_cache["source_path"])
                    saved["cached_file"] = cleaned_cache
                    cached_files[data_type] = cleaned_cache
                else:
                    assigned_path = output_path
                    source_path = output_path
                api.session_store.set_data_path(
                    session_id,
                    data_type,
                    assigned_path,
                    source_path=source_path,
                )
                assigned[data_type] = assigned_path
                saved["assigned_data_type"] = data_type
                saved["assigned_path"] = assigned_path

        def complete_cleaning(data_type, saved):
            deleted_source_file = api._delete_source_his_after_cleaning(saved)
            if deleted_source_file:
                saved["deleted_source_file"] = deleted_source_file
            if not tree_workflow:
                assign_cleaned(data_type, saved)
            cleaned[data_type] = saved
            if progress_callback:
                file_statuses[data_type] = {**file_statuses.get(data_type, {}), "status": "cleaned"}
                progress_callback("cleaning", len(cleaned), total_items, f"Cleaned {len(cleaned)}/{total_items} files", file_statuses)

        def failed_cleaning(data_type, exc):
            file_statuses[data_type] = {
                **file_statuses.get(data_type, {}),
                "status": "error",
                "error": str(exc),
            }
            if progress_callback:
                progress_callback("error", len(cleaned), total_items, str(exc), file_statuses)

        api._run_parallel_cpu_jobs(
            cleaning_items,
            api._queue_clean_worker,
            on_complete=complete_cleaning,
            on_error=failed_cleaning,
        )
        if tree_workflow:
            for data_type, saved in cleaned.items():
                assign_cleaned(data_type, saved)

    use_selected_maps = clean or tree_workflow
    map_policy = "selected_maps" if use_selected_maps else "all_raw_maps"
    map_counts = {}
    for data_type, assigned_path in assigned.items():
        selection = api._map_selection_status(assigned_path)
        total = selection.get("total_count")
        if total is not None:
            map_counts[data_type] = {
                "total_count": total,
                "used_count": selection.get("included_count") if use_selected_maps else total,
                "stored_mask_included_count": selection.get("included_count"),
            }

    api.treatment_service.reset_runtime(session_id)
    response_payload = api._session_payload(session_id)
    response_payload["folder_set"] = {
        "folder": folder,
        "convert": convert,
        "clean": clean,
        "calculate": calculate,
        "assigned": assigned,
        "cached_files": cached_files,
        "conversions": conversions,
        "cleaned": cleaned,
        "map_policy": map_policy,
        "map_counts": map_counts,
    }
    if calculate:
        try:
            auto_result = api._auto_calc_od_if_ready(
                session_id, include_excluded_maps=not use_selected_maps
            )
        except ValueError as exc:
            response_payload = api._session_payload(session_id)
            response_payload["folder_set"] = {
                "folder": folder,
                "convert": convert,
                "clean": clean,
                "calculate": calculate,
                "assigned": assigned,
                "cached_files": cached_files,
                "conversions": conversions,
                "cleaned": cleaned,
                "map_policy": map_policy,
                "map_counts": map_counts,
                "auto_calc_error": str(exc),
            }
        else:
            if auto_result:
                response_payload = api._session_payload(session_id)
                response_payload["folder_set"] = {
                    "folder": folder,
                    "convert": convert,
                    "clean": clean,
                    "calculate": calculate,
                    "assigned": assigned,
                    "cached_files": cached_files,
                    "conversions": conversions,
                    "cleaned": cleaned,
                    "map_policy": map_policy,
                    "map_counts": map_counts,
                    "auto_calculated": True,
                }
                response_payload["result"] = auto_result
    if clean_sources is not None:
        response_payload["folder_set"]["clean_source_fingerprints"] = clean_sources
    if progress_callback:
        progress_callback("complete", total_items, total_items, "Folder operation complete", file_statuses)
    return response_payload


def _run_folder_set_job(job_id: str, session_id: str, request_payload: Dict[str, object]) -> None:
    import treatment_api as api

    def progress(phase: str, current: int, total: int, message: str, files: Dict[str, Dict[str, object]]) -> None:
        api._update_folder_set_job(
            job_id,
            phase=phase,
            current_items=int(current or 0),
            total_items=int(total or 0),
            message=message,
            files={key: dict(value) for key, value in (files or {}).items()},
        )

    try:
        progress("start", 0, 0, "Starting folder operation", {})
        response_payload = api._set_inputs_from_folder_job_payload(
            session_id,
            request_payload,
            progress_callback=progress,
        )
        total_items = int(api._folder_set_job_snapshot(job_id).get("total_items") or 0)
        api._update_folder_set_job(
            job_id,
            status="complete",
            phase="complete",
            current_items=total_items,
            message="Folder operation complete",
            payload=response_payload,
            folder_set=response_payload.get("folder_set", {}),
        )
    except Exception as exc:
        api._update_folder_set_job(
            job_id,
            status="error",
            phase="error",
            message=str(exc),
            error=str(exc),
        )
    finally:
        with api._folder_set_jobs_lock:
            if api._folder_set_session_jobs.get(session_id) == job_id:
                api._folder_set_session_jobs.pop(session_id, None)


def set_inputs_from_folder():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    try:
        response_payload = api._set_inputs_from_folder_job_payload(session_id, payload)
    except ValueError as exc:
        return api._error(str(exc), session_id)
    except OSError as exc:
        return api._error(str(exc), session_id)
    return api._json_response(response_payload, session_id)


def start_folder_set():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    if not payload.get("folder_path"):
        return api._error("folder_path is required", session_id)

    job_id = uuid4().hex
    with api._folder_set_jobs_lock:
        active_job_id = api._folder_set_session_jobs.get(session_id)
        if active_job_id:
            return api._error("A folder operation is already running for this treatment session", session_id, 409)
        api._folder_set_jobs[job_id] = {
            "job_id": job_id,
            "session_id": session_id,
            "status": "running",
            "phase": "queued",
            "message": "Queued folder operation",
            "folder_path": str(payload.get("folder_path") or ""),
            "convert": bool(payload.get("convert", False) or payload.get("clean", False)),
            "clean": bool(payload.get("clean", False)),
            "current_items": 0,
            "total_items": 0,
            "files": {},
            "created_at": api.monotonic(),
            "updated_at": api.monotonic(),
        }
        api._folder_set_session_jobs[session_id] = job_id

    thread = api.Thread(
        target=api._run_folder_set_job,
        args=(job_id, session_id, payload),
        daemon=True,
    )
    thread.start()
    return api._json_response({"folder_set_job": api._folder_set_job_snapshot(job_id), "success": True}, session_id)


def get_folder_set_status(job_id: str):
    import treatment_api as api

    session_id = api._current_session_id()
    job = api._folder_set_job_snapshot(str(job_id))
    if not job or job.get("session_id") != session_id:
        return api._error("folder operation job not found", session_id, 404)
    return api._json_response({"folder_set_job": job, "success": True}, session_id)
