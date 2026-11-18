"""Treatment queue recipes, input fingerprints and output policy."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _queue_required_paths(session: api.Dict[str, object]) -> api.Dict[str, str]:
        exp_type = str(session.get("exp_type") or "")
        required = api.REQUIRED_DATA_TYPES.get(exp_type)
        if not required:
            raise ValueError(f"Unsupported experiment type '{exp_type}'")
        paths = session.get("paths") or {}
        missing = [data_type for data_type in required if not paths.get(data_type)]
        if missing:
            raise ValueError(f"Queue job is missing required input roles: {', '.join(missing)}")
        return {data_type: str(paths[data_type]) for data_type in required}


    def _queue_input_fingerprint(file_path: str, source_path: str) -> api.Dict[str, object]:
        stat = api.os.stat(file_path)
        fingerprint: api.Dict[str, object] = {
            "cached_path": file_path,
            "size_bytes": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
        if api.is_smb_path(source_path):
            fingerprint["source_size_bytes"] = int(api._smb_size_bytes(source_path))
        return fingerprint


    def _queue_output_path(session: api.Dict[str, object], allow_overwrite: bool) -> api.Dict[str, object]:
        save_folder = api._ensure_within_allowed_root(str(session.get("save_folder") or ""))
        if not api._folder_exists(save_folder):
            raise ValueError("save_folder does not exist")
        file_name = api.Path(str(session.get("save_file_name") or "").strip()).name
        if not file_name:
            raise ValueError("save_file_name is not configured")
        if not file_name.lower().endswith(".dat"):
            file_name = f"{api.Path(file_name).stem}.dat"
        path = api.smb_join(save_folder, file_name) if api.is_smb_path(save_folder) else str(api.Path(save_folder) / file_name)
        return {
            "save_folder": save_folder,
            "save_file_name": file_name,
            "path": path,
            "allow_overwrite": allow_overwrite,
            "archive_existing": True,
        }


    def _configured_result_output_path(session: api.Dict[str, object]) -> str:
        save_folder = str(session.get("save_folder") or "").strip()
        save_file_name = api.Path(str(session.get("save_file_name") or "").strip()).name
        if not save_folder or not save_file_name:
            return ""
        if not save_file_name.lower().endswith(".dat"):
            save_file_name = f"{api.Path(save_file_name).stem}.dat"
        return (
            api.smb_join(save_folder, save_file_name)
            if api.is_smb_path(save_folder)
            else str(api.Path(save_folder).expanduser() / save_file_name)
        )


    def _result_output_exists(output_path: str) -> bool:
        return api.smb_isfile(output_path) if api.is_smb_path(output_path) else api.Path(output_path).is_file()


    def _renamed_queue_output_path(output_path: str) -> str:
        if api.is_smb_path(output_path):
            output_folder = api.smb_parent(output_path)
            output_name = api.smb_name(output_path)
        else:
            local_output = api.Path(output_path)
            output_folder = str(local_output.parent)
            output_name = local_output.name

        suffix = api.Path(output_name).suffix
        stem = output_name[:-len(suffix)] if suffix else output_name
        number = 1
        while True:
            backup_name = f"{stem}_old1_{number}{suffix}"
            backup_path = (
                api.smb_join(output_folder, backup_name)
                if api.is_smb_path(output_path)
                else str(api.Path(output_folder) / backup_name)
            )
            if not api._result_output_exists(backup_path):
                return backup_path
            number += 1


    def _rename_result_output(source_path: str, target_path: str) -> None:
        if api.is_smb_path(source_path):
            api.smb_rename(source_path, target_path)
        else:
            api.Path(source_path).replace(target_path)


    def _save_queued_result(runtime_id: str, session_state: api.Dict[str, object]) -> api.Dict[str, object]:
        """Save a queue result, retaining any previous DAT as a numbered backup."""
        output_path = api._configured_result_output_path(session_state)
        archived_output_path = None
        if output_path and api._result_output_exists(output_path):
            archived_output_path = api._renamed_queue_output_path(output_path)
            api._rename_result_output(output_path, archived_output_path)

        try:
            saved = api.treatment_service.save_result(runtime_id, session_state)
        except Exception:
            if archived_output_path and not api._result_output_exists(output_path):
                api._rename_result_output(archived_output_path, output_path)
            raise

        saved = dict(saved)
        if archived_output_path:
            saved["archived_output_path"] = archived_output_path
        return saved


    def _queue_preflight(recipe: api.Dict[str, object]) -> None:
        for data_type, input_data in (recipe.get("inputs") or {}).items():
            cached_path = str(input_data.get("path") or "")
            fingerprint = input_data.get("fingerprint") or {}
            api._ensure_readable_treatment_file(cached_path)
            stat = api.os.stat(cached_path)
            if int(stat.st_size) != int(fingerprint.get("size_bytes", -1)) or int(stat.st_mtime_ns) != int(fingerprint.get("mtime_ns", -1)):
                raise ValueError(f"Queued input changed after enqueue: {data_type}")
            if fingerprint.get("sha256") and api.vd2_fingerprint(cached_path)["sha256"] != fingerprint["sha256"]:
                raise ValueError(f"Queued manifest input changed after enqueue: {data_type}")

        output = recipe.get("output") or {}
        if not output:
            return
        output_path = str(output.get("path") or "")
        save_folder = api._ensure_within_allowed_root(str(output.get("save_folder") or ""))
        if not api._folder_exists(save_folder):
            raise ValueError("Queued output folder no longer exists")
        expected_output = (
            api.smb_join(save_folder, str(output.get("save_file_name") or ""))
            if api.is_smb_path(save_folder)
            else str(api.Path(save_folder) / str(output.get("save_file_name") or ""))
        )
        if output_path != expected_output:
            raise ValueError("Queued output target is invalid")


    def _queue_convert_plan(payload: api.Dict[str, object], required_data_types: api.List[str]) -> api.Dict[str, bool]:
        raw_plan = payload.get("convert_to_h5", False)
        if isinstance(raw_plan, bool):
            return {data_type: raw_plan for data_type in required_data_types}
        if isinstance(raw_plan, list):
            requested = {str(data_type) for data_type in raw_plan}
            unsupported = requested.difference(required_data_types)
            if unsupported:
                raise ValueError(f"convert_to_h5 has unsupported roles: {', '.join(sorted(unsupported))}")
            return {data_type: data_type in requested for data_type in required_data_types}
        if not isinstance(raw_plan, dict):
            raise ValueError("convert_to_h5 must be a boolean, role list, or role object")
        unsupported = set(raw_plan).difference(required_data_types)
        if unsupported:
            raise ValueError(f"convert_to_h5 has unsupported roles: {', '.join(sorted(unsupported))}")
        if any(not isinstance(value, bool) for value in raw_plan.values()):
            raise ValueError("convert_to_h5 role values must be boolean")
        return {data_type: raw_plan.get(data_type, False) for data_type in required_data_types}


    def _queue_cleaning_plan(payload: api.Dict[str, object], required_data_types: api.List[str]) -> api.Dict[str, object]:
        raw_plan = payload.get("cleaning") or {}
        if not isinstance(raw_plan, dict):
            raise ValueError("cleaning must be an object")

        raw_enabled = raw_plan.get("enabled", False)
        if not isinstance(raw_enabled, bool):
            raise ValueError("cleaning.enabled must be a boolean")
        enabled = raw_enabled
        state = str(raw_plan.get("state") or ("pending" if enabled else "not_requested"))
        if state not in api.QUEUE_CLEANING_STATES:
            raise ValueError("cleaning.state must be not_requested, applied, or pending")
        if state == "pending" and not enabled:
            raise ValueError("cleaning.pending requires cleaning.enabled=true")
        if state != "pending" and enabled:
            raise ValueError("cleaning.enabled=true requires cleaning.state=pending")

        raw_data_types = raw_plan.get("data_types")
        if raw_data_types is None:
            data_types = (
                list(required_data_types)
                if state == "pending" and set(required_data_types).issubset({"ABS", "BASE", "NOISE"})
                else []
            )
        elif not isinstance(raw_data_types, list):
            raise ValueError("cleaning.data_types must be a role list")
        else:
            data_types = [str(data_type) for data_type in raw_data_types]
        unsupported = set(data_types).difference(required_data_types)
        if unsupported:
            raise ValueError(f"cleaning.data_types has unsupported roles: {', '.join(sorted(unsupported))}")
        if state == "pending" and not data_types:
            raise ValueError("cleaning.pending requires at least one input role")
        if state == "pending" and not set(data_types).issubset({"ABS", "BASE", "NOISE"}):
            raise ValueError(
                "Queued SAM cleaning is not available for paired inputs; it supports independent ABS, BASE, and NOISE roles only"
            )

        try:
            angle_threshold = float(raw_plan.get("angle_threshold", 1.0))
            surface_threshold = float(raw_plan.get("surface_threshold", 1.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("cleaning thresholds must be numeric") from exc
        if not all(api.math.isfinite(value) and value > 0 for value in (angle_threshold, surface_threshold)):
            raise ValueError("cleaning thresholds must be finite and positive")

        return {
            "state": state,
            "enabled": state == "pending",
            "data_types": data_types,
            "angle_threshold": angle_threshold,
            "surface_threshold": surface_threshold,
        }


    def _queue_recipe(session_id: str, payload: api.Dict[str, object], *, session_state=None) -> api.Dict[str, object]:
        session = api.deepcopy(session_state) if session_state is not None else api.session_store.snapshot(session_id)
        required_paths = api._queue_required_paths(session)
        required_data_types = list(required_paths)
        for file_path in required_paths.values():
            api._ensure_readable_treatment_file(file_path)
        if session.get("calc_mode") in api.SPECTRAL_MODES:
            if api._checked_spectral_reference(session.get("spectral_reference"), session) is None:
                raise ValueError("Select the pre-pulse reference window on the current ABS preview")

        cleaning_plan = api._queue_cleaning_plan(payload, required_data_types)
        runtime = api.treatment_service.runtime_status(session_id)
        if runtime.get("cleaning_ready"):
            preview_path = api._normalize_path(str(runtime.get("cleaning_file_path") or ""))
            preview_role = next(
                (
                    data_type
                    for data_type, file_path in (session.get("paths") or {}).items()
                    if file_path and api._normalize_path(str(file_path)) == preview_path
                ),
                "",
            )
            if (
                cleaning_plan["state"] != "pending"
                or preview_role not in cleaning_plan["data_types"]
            ):
                raise ValueError(
                    "Cleaning preview is transient. Apply/reset it or queue pending cleaning for its active role."
                )

        profile = str(payload.get("profile") or "VD2").strip().upper()
        if profile not in {"VD2", "V0"}:
            raise ValueError("profile must be VD2 or V0")
        label = str(payload.get("label") or "").strip()
        if len(label) > 160:
            raise ValueError("label must be 160 characters or fewer")
        raw_allow_overwrite = payload.get("allow_overwrite", False)
        if not isinstance(raw_allow_overwrite, bool):
            raise ValueError("allow_overwrite must be a boolean")
        allow_overwrite = raw_allow_overwrite
        output = api._queue_output_path(session, allow_overwrite)
        sources = {
            data_type: str((session.get("path_sources") or {}).get(data_type) or file_path)
            for data_type, file_path in required_paths.items()
        }
        convert_plan = api._queue_convert_plan(payload, required_data_types)
        exp_type = str(session.get("exp_type") or "")
        paired_his_mode = exp_type in {"HIS", "HIS+NOISE"}
        if paired_his_mode and any(convert_plan.values()):
            raise ValueError(
                "Queued H5 conversion is not available for paired HIS modes; keep their source roles unchanged"
            )
        if not paired_his_mode:
            for data_type, source_path in sources.items():
                if api._path_suffix(source_path) == ".his":
                    convert_plan[data_type] = True
        map_selections = {
            data_type: api._map_selection_status(file_path)
            for data_type, file_path in required_paths.items()
        }
        if cleaning_plan["state"] == "applied":
            applied_roles = cleaning_plan["data_types"]
            if not applied_roles:
                raise ValueError("cleaning.applied requires explicit input roles")
            missing_applied_masks = [
                data_type
                for data_type in applied_roles
                if not map_selections[data_type].get("applied")
            ]
            if missing_applied_masks:
                raise ValueError(
                    "Persisted H5 map selection is missing for: "
                    f"{', '.join(missing_applied_masks)}"
                )

        return {
            "format_version": 1,
            "kind": "recipe",
            "profile": profile,
            "label": label,
            "created_at": api.datetime.now(api.timezone.utc).isoformat(),
            "session": api.deepcopy(session),
            "inputs": {
                data_type: {
                    "path": file_path,
                    "source_path": sources[data_type],
                    "fingerprint": api._queue_input_fingerprint(file_path, sources[data_type]),
                }
                for data_type, file_path in required_paths.items()
            },
            "convert_to_h5": convert_plan,
            "cleaning": cleaning_plan,
            "output": output,
            "map_selections": map_selections,
            "provenance": {
                "enqueued_by_session": session_id,
                "source_paths": {
                    data_type: sources[data_type]
                    for data_type, file_path in required_paths.items()
                },
                "paired_his_canonicalization": (
                    "deferred: H5 pair semantics are not implemented"
                    if paired_his_mode
                    else "not_applicable"
                ),
            },
        }


    def _queue_standard_folder_recipe(session_id: str, payload: api.Dict[str, object]) -> api.Dict[str, object]:
        """Capture one immutable per-folder VD2 action for sequential execution."""
        folder_path = payload.get("folder_path")
        if not folder_path:
            raise ValueError("folder_path is required")
        folder = api._ensure_within_allowed_root(str(folder_path))
        if not api._folder_exists(folder):
            raise ValueError("Folder does not exist")

        profile = str(payload.get("profile") or "VD2").strip().upper()
        if profile != "VD2":
            raise ValueError("Standard folder queue is available only for the VD2 profile")
        naming = payload.get("output_naming")
        if naming not in (None, "sample"):
            raise ValueError("Unsupported folder output naming")
        exp_type = str(payload.get("exp_type") or "ABS+BASE+NOISE")
        if exp_type not in api.EXP_TYPES:
            raise ValueError("Unsupported experiment type")
        raw_allow_overwrite = payload.get("allow_overwrite", False)
        if not isinstance(raw_allow_overwrite, bool):
            raise ValueError("allow_overwrite must be a boolean")
        raw_clean = payload.get("clean", True)
        if not isinstance(raw_clean, bool):
            raise ValueError("clean must be a boolean")
        raw_convert = payload.get("convert", True)
        if not isinstance(raw_convert, bool):
            raise ValueError("convert must be a boolean")
        raw_calculate = payload.get("calculate", True)
        if not isinstance(raw_calculate, bool):
            raise ValueError("calculate must be a boolean")
        if raw_clean and not raw_convert:
            raise ValueError("clean requires convert")
        try:
            angle_threshold = float(payload.get("angle_threshold", 1.0))
            surface_threshold = float(payload.get("surface_threshold", 1.0))
        except (TypeError, ValueError) as exc:
            raise ValueError("angle_threshold and surface_threshold must be numeric") from exc
        if not all(api.math.isfinite(value) and value > 0 for value in (angle_threshold, surface_threshold)):
            raise ValueError("angle_threshold and surface_threshold must be positive")

        candidates = api._folder_input_candidates(
            folder,
            exp_type,
            convert=raw_convert,
        )
        required = api.REQUIRED_DATA_TYPES[exp_type] if naming == "sample" and raw_calculate else api._folder_required_input_types(exp_type)
        missing = [
            data_type
            for data_type in required
            if not candidates.get(data_type)
        ]
        if missing:
            raise ValueError(
                f"Folder requires {', '.join(required)} for {exp_type}; missing "
                f"{', '.join(missing)}"
            )

        session = api.session_store.snapshot(session_id)
        folder_calc_mode = "averaged"
        if naming == "sample" and exp_type == session["exp_type"]:
            folder_calc_mode = session["calc_mode"]
        elif naming == "sample" and exp_type != "HIS":
            folder_calc_mode = api.SPECTRAL_SUM
        if raw_calculate and folder_calc_mode in api.SPECTRAL_MODES:
            raise ValueError("Load the folder inputs and select the reference window on ABS before Calculate OD. "
                             "Use Classic OD of averages for automatic folder batches.")
        save_folder = api._save_folder_for_measurement({} if naming == "sample" else session, folder)
        save_file_name = f"{api._path_name(folder)}.dat" if naming == "sample" else api._dated_save_file_name_for_folder(folder)
        save_target = {"save_folder": save_folder, "save_file_name": save_file_name}
        output: api.Dict[str, object] = {}
        if raw_calculate:
            output_path = (
                api.smb_join(save_folder, save_file_name)
                if api.is_smb_path(save_folder)
                else str(api.Path(save_folder) / save_file_name)
            )
            output = {
                **save_target,
                "path": output_path,
                "allow_overwrite": raw_allow_overwrite,
                "archive_existing": True,
            }
        label = str(payload.get("label") or api._path_name(folder) or "Standard folder treatment").strip()
        if len(label) > 160:
            raise ValueError("label must be 160 characters or fewer")
        return {
            "format_version": 1,
            "kind": "standard_folder_set",
            "profile": profile,
            "label": label,
            "created_at": api.datetime.now(api.timezone.utc).isoformat(),
            "session_id": session_id,
            "session_config": {
                "exp_type": exp_type,
                "selected_data_type": api.REQUIRED_DATA_TYPES[exp_type][0],
                "calc_mode": folder_calc_mode,
                "first_map_with_electrons": session["first_map_with_electrons"] if naming == "sample" else True,
            },
            "folder_set": {
                "folder_path": folder,
                "convert": raw_convert,
                "clean": raw_clean,
                "calculate": raw_calculate,
                **({"_tree_workflow": True} if naming == "sample" else {}),
                "angle_threshold": angle_threshold,
                "surface_threshold": surface_threshold,
            },
            "save_target": save_target,
            "output": output,
            "provenance": {
                "enqueued_by_session": session_id,
                "source_folder": folder,
                "source_his_policy": (
                    "delete_after_verified_h5" if raw_convert else "preserve"
                ),
            },
        }

    api._queue_required_paths = _queue_required_paths
    api._queue_input_fingerprint = _queue_input_fingerprint
    api._queue_output_path = _queue_output_path
    api._configured_result_output_path = _configured_result_output_path
    api._result_output_exists = _result_output_exists
    api._renamed_queue_output_path = _renamed_queue_output_path
    api._rename_result_output = _rename_result_output
    api._save_queued_result = _save_queued_result
    api._queue_preflight = _queue_preflight
    api._queue_convert_plan = _queue_convert_plan
    api._queue_cleaning_plan = _queue_cleaning_plan
    api._queue_recipe = _queue_recipe
    api._queue_standard_folder_recipe = _queue_standard_folder_recipe
