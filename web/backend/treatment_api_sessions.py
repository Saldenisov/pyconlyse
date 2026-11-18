"""Treatment session persistence, configuration and session routes."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _default_state(session_id="") -> api.Dict[str, object]:
        folder = api._default_folder()
        vd2 = api._saved_session_profile(session_id) == "vd2" if session_id else False
        default_exp_type = "ABS+BASE+NOISE" if vd2 else api.EXP_TYPES[1]
        default_required = api.REQUIRED_DATA_TYPES[default_exp_type]
        return {
            "exp_type": default_exp_type,
            "selected_data_type": default_required[0],
            "active_data_type": "",
            "dat_preview_path": "",
            "map_index": 0,
            "selection": {},
            "calc_mode": api.SPECTRAL_SUM if vd2 else api.CALC_MODES[0],
            "spectral_reference": None,
            "first_map_with_electrons": True,
            "folder_path": folder,
            "save_folder": folder,
            "save_file_name": "",
            "paths": {},
            "path_sources": {},
            "status_label": "Treatment session is ready.",
            "noise_ready": False,
            "result_ready": False,
            "result_map_policy": "selected_maps",
            "result_shape": None,
            "result_source_path": "",
            "cleaning_preview_request": None,
        }


    def _checked_spectral_reference(value, state):
        if value is None:
            return None
        role = {"HIS+NOISE": "ABS+BASE", "ABS+BASE+NOISE": "ABS"}.get(state.get("exp_type"))
        path = (state.get("paths") or {}).get(role)
        if not path:
            raise ValueError("Assign an ABS input before setting its reference window")
        source = (state.get("path_sources") or {}).get(role) or path
        start, stop = api.reference_window(value, source)
        _, info = api.treatment_service._get_opener_and_info(api.Path(path))
        if stop >= info.timedelays_length:
            raise ValueError("The reference window must end before the last time row")
        return {"source": source, "start": start, "stop": stop,
                "time_start": float(info.timedelays[start]), "time_stop": float(info.timedelays[stop]),
                "time_unit": info.scaling_yunit}


    class TreatmentSessionStore:
        def __init__(self, repository=None):
            self._lock = api.Lock()
            self._repository = repository
            self._sessions: api.Dict[str, api.Dict[str, object]] = (
                repository.load_sessions() if repository else {}
            )

        def _persist_locked(self, session_id):
            self._sessions[session_id]["saved_at"] = api.datetime.now(api.timezone.utc).isoformat()
            if self._repository:
                self._repository.save_session(session_id, self._sessions[session_id])

        @staticmethod
        def _clone_state(state: api.Dict[str, object]) -> api.Dict[str, object]:
            snapshot = dict(state)
            snapshot["paths"] = dict(state["paths"])
            snapshot["path_sources"] = dict(state.get("path_sources") or {})
            snapshot["selection"] = dict(state["selection"])
            if state.get("spectral_reference"):
                snapshot["spectral_reference"] = dict(state["spectral_reference"])
            return snapshot

        def _get_or_create_state(self, session_id: str) -> api.Dict[str, object]:
            state = self._sessions.get(session_id)
            if state is None:
                state = api._default_state(session_id)
                self._sessions[session_id] = state
                self._persist_locked(session_id)
            return state

        def snapshot(self, session_id: str) -> api.Dict[str, object]:
            with self._lock:
                state = self._get_or_create_state(session_id)
                return self._clone_state(state)

        def saved_sessions(self, browser, profile):
            prefix = f"browser:{api.workspace_identity(browser)}:"
            with self._lock:
                items = [dict(session_id=key, folder=state.get("folder_path", ""),
                              name=state.get("save_file_name") or state.get("folder_path") or "Treatment",
                              updated_at=state.get("saved_at", ""))
                         for key, state in self._sessions.items()
                         if key.startswith(prefix) and api._saved_session_profile(key) == profile
                         and (state.get("paths") or state.get("save_file_name") or state.get("selection")
                              or (state.get("folder_path") and state.get("status_label") != "Treatment session is ready."))]
            return sorted(items, key=lambda item: item["updated_at"], reverse=True)[:40]

        def copy_saved_session(self, source_id, target_id):
            with self._lock:
                source = self._sessions.get(source_id)
                if source is None:
                    raise ValueError("Saved treatment session no longer exists")
                source = api.deepcopy(source)
            return self.restore_if_empty(target_id, source, origin="server snapshot")

        def reset(self, session_id: api.Optional[str] = None) -> api.Dict[str, object]:
            with self._lock:
                if session_id is None:
                    self._sessions.clear()
                    if self._repository:
                        self._repository.delete_session()
                    return self._clone_state(api._default_state())
                self._sessions[session_id] = api._default_state(session_id)
                self._persist_locked(session_id)
                return self._clone_state(self._sessions[session_id])

        def restore_if_empty(self, session_id: str, snapshot: api.Dict[str, object], *, origin="browser backup") -> bool:
            """Import a browser backup only into an untouched, empty server session."""
            if not isinstance(snapshot, dict):
                raise ValueError("session backup must be an object")
            exp_type = str(snapshot.get("exp_type") or "")
            if exp_type not in api.EXP_TYPES:
                raise ValueError("session backup has an unsupported experiment type")
            selected_data_type = str(snapshot.get("selected_data_type") or "")
            if selected_data_type not in api.REQUIRED_DATA_TYPES[exp_type]:
                raise ValueError("session backup has an invalid selected data type")
            calc_mode = str(snapshot.get("calc_mode") or "")
            if calc_mode not in api.CALC_MODES:
                raise ValueError("session backup has an invalid calculation mode")

            folder = api._ensure_within_allowed_root(str(snapshot.get("folder_path") or ""))
            save_folder = api._ensure_within_allowed_root(str(snapshot.get("save_folder") or folder))
            if not api._folder_exists(folder) or not api._folder_exists(save_folder):
                raise ValueError("session backup folder no longer exists")
            save_file_name = api.os.path.basename(str(snapshot.get("save_file_name") or "").strip())
            if save_file_name and not save_file_name.lower().endswith(".dat"):
                raise ValueError("session backup save file name must end in .dat")

            paths = {}
            sources = {}
            raw_paths = snapshot.get("paths") or {}
            raw_sources = snapshot.get("path_sources") or {}
            if not isinstance(raw_paths, dict) or not isinstance(raw_sources, dict):
                raise ValueError("session backup paths must be objects")
            for data_type, path in raw_paths.items():
                if data_type not in api.DATA_TYPES:
                    raise ValueError("session backup has an invalid input data type")
                paths[data_type] = api._ensure_readable_treatment_file(str(path))
                source = str(raw_sources.get(data_type) or path)
                sources[data_type] = api._ensure_within_allowed_root(source) if source != path else paths[data_type]

            active_data_type = str(snapshot.get("active_data_type") or "")
            reference = snapshot.get("spectral_reference")
            if reference is not None:
                reference = api._checked_spectral_reference(reference, {**snapshot, "paths": paths, "path_sources": sources})
            if active_data_type not in {"", "OD", "DAT", *api.DATA_TYPES}:
                raise ValueError("session backup has an invalid active data type")
            dat_preview_path = str(snapshot.get("dat_preview_path") or "")
            if dat_preview_path:
                dat_preview_path = api._ensure_readable_treatment_file(dat_preview_path)
                if api._path_suffix(dat_preview_path) != ".dat":
                    raise ValueError("session backup preview must be DAT")
            if active_data_type == "DAT" and not dat_preview_path:
                raise ValueError("session backup preview file is missing")
            preview_request = None
            raw_preview = snapshot.get("cleaning_preview_request")
            if isinstance(raw_preview, dict) and str(raw_preview.get("file_path") or "") == paths.get(active_data_type):
                try:
                    angle_threshold = float(raw_preview["angle_threshold"])
                    surface_threshold = float(raw_preview["surface_threshold"])
                    if api.math.isfinite(angle_threshold) and api.math.isfinite(surface_threshold):
                        preview_request = {
                            "angle_threshold": angle_threshold,
                            "surface_threshold": surface_threshold,
                            "file_path": paths[active_data_type],
                        }
                except (KeyError, TypeError, ValueError):
                    pass
            try:
                map_index = max(0, int(snapshot.get("map_index") or 0))
                raw_selection = snapshot.get("selection") or {}
                if not isinstance(raw_selection, dict):
                    raise ValueError("selection must be an object")
                selection = {
                    key: int(value) for key, value in raw_selection.items()
                    if key in {"x1", "x2", "y1", "y2"} and value is not None
                }
            except (TypeError, ValueError) as exc:
                raise ValueError("session backup has invalid selection values") from exc

            with self._lock:
                current = self._get_or_create_state(session_id)
                if current.get("status_label") != "Treatment session is ready." or current.get("paths"):
                    return False
                current.update({
                    "exp_type": exp_type,
                    "selected_data_type": selected_data_type,
                    "active_data_type": active_data_type,
                    "dat_preview_path": dat_preview_path,
                    "map_index": map_index,
                    "selection": selection,
                    "calc_mode": calc_mode,
                    "spectral_reference": reference,
                    "first_map_with_electrons": bool(snapshot.get("first_map_with_electrons", True)),
                    "folder_path": folder,
                    "save_folder": save_folder,
                    "save_file_name": save_file_name,
                    "paths": paths,
                    "path_sources": sources,
                    "result_ready": bool(snapshot.get("result_ready", False)),
                    "result_map_policy": (
                        "all_raw_maps"
                        if snapshot.get("result_map_policy") == "all_raw_maps"
                        else "selected_maps"
                    ),
                    "cleaning_preview_request": preview_request,
                    "status_label": f"Treatment session restored from {origin}.",
                })
                self._persist_locked(session_id)
                return True

        def update_config(self, session_id: str, payload: api.Dict[str, object]) -> api.Dict[str, object]:
            with self._lock:
                state = dict(self._get_or_create_state(session_id))
                previous_calculation = (
                    state["exp_type"], state["selected_data_type"],
                    state["calc_mode"], state["first_map_with_electrons"], state.get("spectral_reference"),
                )
                if "spectral_reference" in payload:
                    state["spectral_reference"] = api._checked_spectral_reference(payload["spectral_reference"], state)
                if payload.get("exp_type", state["exp_type"]) != state["exp_type"] or (
                    "first_map_with_electrons" in payload and state["exp_type"] == "HIS+NOISE"
                    and bool(payload["first_map_with_electrons"]) != state["first_map_with_electrons"]
                ):
                    state["spectral_reference"] = None
                requested_exp_type = str(state["exp_type"])
                if "exp_type" in payload:
                    exp_type = str(payload["exp_type"])
                    if exp_type not in api.EXP_TYPES:
                        raise ValueError(f"Unsupported exp_type '{exp_type}'")
                    state["exp_type"] = exp_type
                    requested_exp_type = exp_type

                if "selected_data_type" in payload:
                    selected_data_type = str(payload["selected_data_type"])
                    if selected_data_type not in api.DATA_TYPES:
                        raise ValueError(
                            f"Unsupported selected_data_type '{selected_data_type}'"
                        )
                    if selected_data_type not in api.REQUIRED_DATA_TYPES[requested_exp_type]:
                        raise ValueError(
                            f"selected_data_type '{selected_data_type}' is not valid for exp_type '{requested_exp_type}'"
                        )
                    state["selected_data_type"] = selected_data_type
                else:
                    required_data_types = api.REQUIRED_DATA_TYPES[requested_exp_type]
                    if state["selected_data_type"] not in required_data_types:
                        state["selected_data_type"] = required_data_types[0]

                if "calc_mode" in payload:
                    calc_mode = str(payload["calc_mode"])
                    if calc_mode not in api.CALC_MODES:
                        raise ValueError(f"Unsupported calc_mode '{calc_mode}'")
                    if requested_exp_type == "HIS" and calc_mode in api.SPECTRAL_MODES:
                        raise ValueError("Spectral correction requires a separate BRUIT reference")
                    state["calc_mode"] = calc_mode
                elif requested_exp_type != previous_calculation[0]:
                    if api._saved_session_profile(session_id) == "v0" and requested_exp_type == "HIS+NOISE":
                        state["calc_mode"] = "individual"
                    else:
                        state["calc_mode"] = api.SPECTRAL_SUM if requested_exp_type != "HIS" else "averaged"
                if requested_exp_type == "ABS+BASE+NOISE" and state["calc_mode"] == "individual":
                    state["calc_mode"] = "averaged"

                if "first_map_with_electrons" in payload:
                    state["first_map_with_electrons"] = bool(
                        payload["first_map_with_electrons"]
                    )

                if "save_folder" in payload:
                    save_folder = api._ensure_within_allowed_root(str(payload["save_folder"]))
                    if not api._folder_exists(save_folder):
                        raise ValueError("save_folder does not exist")
                    state["save_folder"] = save_folder

                if "save_file_name" in payload:
                    save_file_name = api.os.path.basename(str(payload["save_file_name"]).strip())
                    if save_file_name and not save_file_name.lower().endswith(".dat"):
                        save_file_name = f"{api.Path(save_file_name).stem}.dat"
                    state["save_file_name"] = save_file_name

                state["status_label"] = "Treatment session updated."
                if previous_calculation != (
                    state["exp_type"], state["selected_data_type"],
                    state["calc_mode"], state["first_map_with_electrons"], state.get("spectral_reference"),
                ):
                    state["result_ready"] = False
                    state["result_map_policy"] = "selected_maps"
                    state["cleaning_preview_request"] = None
                self._sessions[session_id] = state
                self._persist_locked(session_id)

            return self.snapshot(session_id)

        def set_folder(self, session_id: str, folder_path: str) -> api.Dict[str, object]:
            folder = api._ensure_within_allowed_root(folder_path)
            if not api._folder_exists(folder):
                raise ValueError("Selected folder does not exist")

            with self._lock:
                state = self._get_or_create_state(session_id)
                state["folder_path"] = folder
                _, save_file_name = api._default_save_target_for_folder(folder)
                state["save_folder"] = folder
                state["save_file_name"] = save_file_name
                state["result_ready"] = False
                state["result_map_policy"] = "selected_maps"
                state["cleaning_preview_request"] = None
                state["status_label"] = f"Folder selected: {folder}"
                self._persist_locked(session_id)

            return self.snapshot(session_id)

        def clear_folder_inputs(self, session_id: str) -> None:
            """Start a folder selection without inheriting a previous sample's roles."""
            with self._lock:
                state = self._get_or_create_state(session_id)
                state.update(paths={}, path_sources={}, active_data_type="", map_index=0,
                             noise_ready=False, result_ready=False, dat_preview_path="",
                             cleaning_preview_request=None, selection={}, spectral_reference=None)
                self._persist_locked(session_id)

        def set_data_path(
            self,
            session_id: str,
            data_type: str,
            file_path: str,
            source_path: api.Optional[str] = None,
        ) -> api.Dict[str, object]:
            if data_type not in api.DATA_TYPES:
                raise ValueError(f"Unsupported data_type '{data_type}'")

            normalized_source = api._normalize_path(source_path) if source_path else api._normalize_path(file_path)
            mapped_source = (
                api._mapped_smb_local_file(normalized_source)
                if api.is_smb_path(normalized_source)
                else None
            )
            if mapped_source and api.os.path.abspath(file_path) == mapped_source:
                normalized = mapped_source
            else:
                normalized = api._ensure_readable_treatment_file(file_path)

            with self._lock:
                state = self._get_or_create_state(session_id)
                previous_source = (state.get("path_sources") or {}).get(data_type)
                if data_type in {"ABS", "ABS+BASE"} and previous_source != normalized_source:
                    state["spectral_reference"] = None
                state["paths"][data_type] = normalized
                state.setdefault("path_sources", {})[data_type] = normalized_source
                state["active_data_type"] = data_type
                state["map_index"] = 0
                state["result_ready"] = False
                state["result_map_policy"] = "selected_maps"
                state["cleaning_preview_request"] = None
                if not state["save_file_name"]:
                    stem = api.os.path.splitext(api.os.path.basename(normalized))[0]
                    state["save_file_name"] = f"{stem}.dat"
                state["status_label"] = f"{data_type} file selected."
                self._persist_locked(session_id)

            return self.snapshot(session_id)

        def set_browsing_folder(self, session_id: str, folder_path: str) -> api.Dict[str, object]:
            """Repair browser folder context without resetting active processing state."""
            folder = api._ensure_within_allowed_root(folder_path)
            if not api._folder_exists(folder):
                raise ValueError("Selected folder does not exist")
            with self._lock:
                state = self._get_or_create_state(session_id)
                state["folder_path"] = folder
                self._persist_locked(session_id)
            return self.snapshot(session_id)

        def mark_result_ready(
            self, session_id: str, ready: bool, map_policy: str = "selected_maps"
        ) -> None:
            with self._lock:
                state = self._get_or_create_state(session_id)
                state["result_ready"] = bool(ready)
                state["result_map_policy"] = (
                    "all_raw_maps" if ready and map_policy == "all_raw_maps" else "selected_maps"
                )
                self._persist_locked(session_id)

        def set_cleaning_preview_request(self, session_id: str, request_payload) -> None:
            with self._lock:
                state = self._get_or_create_state(session_id)
                state["cleaning_preview_request"] = dict(request_payload) if request_payload else None
                self._persist_locked(session_id)

        def update_selection(self, session_id: str, payload: api.Dict[str, object]) -> api.Dict[str, object]:
            with self._lock:
                state = self._get_or_create_state(session_id)

                if "active_data_type" in payload:
                    active_data_type = str(payload["active_data_type"])
                    if active_data_type and active_data_type not in {"OD", "DAT"} and active_data_type not in api.DATA_TYPES:
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
                self._persist_locked(session_id)

            return self.snapshot(session_id)

        def set_dat_preview(self, session_id, path):
            with self._lock:
                state = self._get_or_create_state(session_id)
                state.update(dat_preview_path=path, active_data_type="DAT", map_index=0, selection={})
                self._persist_locked(session_id)


    def _current_session_id() -> str:
        session_id = (
            api.request.headers.get("X-Treatment-Session-Id")
            or api.request.cookies.get(api.TREATMENT_SESSION_COOKIE)
            or ""
        ).strip()
        if session_id:
            return session_id
        return api.uuid4().hex


    def _session_payload(session_id: str) -> api.Dict[str, object]:
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


    def _json_response(payload: api.Dict[str, object], session_id: str, status_code: int = 200):
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
        return api._json_response({"error": message, "success": False}, session_id, status_code)


    def get_session():
        session_id = api._current_session_id()
        return api._json_response(api._session_payload(session_id), session_id)


    def reset_session():
        session_id = api._current_session_id()
        api.session_store.reset(session_id)
        api.treatment_service.reset_runtime(session_id)
        return api._json_response(api._session_payload(session_id), session_id)


    def _saved_session_profile(session_id):
        match = api.re.search(r":profile:(vd2|v0)(?::workspace:[A-Za-z0-9-]+)?$", session_id)
        return match.group(1) if match else None


    def _saved_session_browser(session_id):
        browser = api.workspace_identity(api.request.headers.get("X-Workspace-Browser"))
        if not session_id.startswith(f"browser:{browser}:") or api._saved_session_profile(session_id) is None:
            raise ValueError("Treatment session does not belong to this browser")
        return browser


    def saved_treatment_sessions():
        session_id = api._current_session_id()
        try:
            browser = api._saved_session_browser(session_id)
            return api._json_response(dict(success=True, sessions=api.session_store.saved_sessions(browser, api._saved_session_profile(session_id))), session_id)
        except ValueError as exc:
            return api._error(str(exc), session_id)


    def copy_treatment_session():
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
                "spectral_reference",
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


    def update_session_selection():
        session_id = api._current_session_id()
        payload = api.request.get_json(silent=True) or {}

        try:
            api.session_store.update_selection(session_id, payload)
        except ValueError as exc:
            return api._error(str(exc), session_id)

        return api._json_response(api._session_payload(session_id), session_id)

    api._default_state = _default_state
    api._checked_spectral_reference = _checked_spectral_reference
    api.TreatmentSessionStore = TreatmentSessionStore
    api._current_session_id = _current_session_id
    api._session_payload = _session_payload
    api._json_response = _json_response
    api._error = _error
    api.get_session = get_session
    api.reset_session = reset_session
    api._saved_session_profile = _saved_session_profile
    api._saved_session_browser = _saved_session_browser
    api.saved_treatment_sessions = saved_treatment_sessions
    api.copy_treatment_session = copy_treatment_session
    api.restore_session_from_browser = restore_session_from_browser
    api.update_session_config = update_session_config
    api.update_session_root = update_session_root
    api.set_session_folder = set_session_folder
    api.update_session_selection = update_session_selection
