"""Treatment SAM cleaning and restoration endpoints."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def analyze_sam_cleaning():
        session_id = api._current_session_id()
        payload = api.request.get_json(silent=True) or {}

        try:
            angle_threshold = float(payload.get("angle_threshold", 1.0))
            surface_threshold = float(payload.get("surface_threshold", 1.0))
        except (TypeError, ValueError):
            return api._error("angle_threshold and surface_threshold must be numeric", session_id)

        try:
            summary = api.treatment_service.analyze_sam_cleaning(
                session_id,
                api.session_store.snapshot(session_id),
                angle_threshold,
                surface_threshold,
            )
            cleaning_view = api.treatment_service.get_cleaning_view(
                session_id,
                api.session_store.snapshot(session_id),
            )
            api.session_store.set_cleaning_preview_request(
                session_id,
                {
                    "angle_threshold": angle_threshold,
                    "surface_threshold": surface_threshold,
                    "file_path": summary.get("file_path"),
                } if summary.get("state_updated") else None,
            )
        except ValueError as exc:
            return api._error(str(exc), session_id)

        return api._json_response(
            {"cleaning": summary, "cleaning_view": cleaning_view, "success": True},
            session_id,
        )


    def get_sam_cleaning_view():
        session_id = api._current_session_id()

        try:
            cleaning_view = api.treatment_service.get_cleaning_view(
                session_id,
                api.session_store.snapshot(session_id),
            )
        except ValueError as exc:
            return api._error(str(exc), session_id)

        return api._json_response({"cleaning_view": cleaning_view, "success": True}, session_id)


    def reset_sam_cleaning():
        session_id = api._current_session_id()

        try:
            summary = api.treatment_service.reset_sam_cleaning(
                session_id,
                api.session_store.snapshot(session_id),
            )
            cleaning_view = api.treatment_service.get_cleaning_view(
                session_id,
                api.session_store.snapshot(session_id),
            )
            api.session_store.set_cleaning_preview_request(session_id, None)
        except ValueError as exc:
            return api._error(str(exc), session_id)

        return api._json_response(
            {"cleaning": summary, "cleaning_view": cleaning_view, "success": True},
            session_id,
        )


    def restore_sam_cleaning():
        session_id = api._current_session_id()

        try:
            session_state = api.session_store.snapshot(session_id)
            active_data_type = api._active_assignable_data_type(session_state)
            if not active_data_type:
                raise ValueError("No active H5 file is selected")
            active_path = str(session_state.get("paths", {}).get(active_data_type) or "")
            source_path = str(
                session_state.get("path_sources", {}).get(active_data_type)
                or active_path
            )
            if api._path_suffix(source_path) != ".h5":
                raise ValueError("Restore denoising requires an H5 file")

            if api.is_smb_path(source_path):
                cached = api._cache_assignable_source(source_path)
                local_path = api.Path(str(cached["cached_path"]))
                restored = api.treatment_service.restore_cleaned_h5_file(local_path)
                api.copy_local_file_to_smb_atomic(local_path, source_path)
                restored["output_path"] = source_path
                restored["cached_file"] = cached
                api.session_store.set_data_path(
                    session_id,
                    active_data_type,
                    str(local_path),
                    source_path=source_path,
                )
            else:
                restored = api.treatment_service.restore_cleaned_h5_file(api.Path(active_path))
                restored["output_path"] = active_path
            api.treatment_service.reset_runtime(session_id)
            api.session_store.set_cleaning_preview_request(session_id, None)
            cleaning_view = api.treatment_service.get_cleaning_view(
                session_id,
                api.session_store.snapshot(session_id),
            )
        except ValueError as exc:
            return api._error(str(exc), session_id)

        payload = api._session_payload(session_id)
        payload["cleaning"] = restored
        payload["cleaning_view"] = cleaning_view
        return api._json_response(payload, session_id)


    def save_sam_cleaning():
        session_id = api._current_session_id()
        payload = api.request.get_json(silent=True) or {}

        try:
            angle_threshold = float(payload.get("angle_threshold", 1.0))
            surface_threshold = float(payload.get("surface_threshold", 1.0))
        except (TypeError, ValueError):
            return api._error("angle_threshold and surface_threshold must be numeric", session_id)

        output_file_name = str(payload.get("output_file_name") or "")

        try:
            before_save_state = api.session_store.snapshot(session_id)
            active_data_type = api._active_assignable_data_type(before_save_state)
            saved = api.treatment_service.save_sam_cleaned_h5(
                session_id,
                before_save_state,
                angle_threshold,
                surface_threshold,
                output_file_name=output_file_name,
            )
            api.session_store.set_cleaning_preview_request(session_id, None)
            deleted_source_file = api._delete_source_his_after_cleaning(saved)
            if deleted_source_file:
                saved["deleted_source_file"] = deleted_source_file
            output_path = str(saved.get("output_path") or "")
            if output_path and active_data_type:
                if api.is_smb_path(output_path):
                    cached = api._cache_assignable_source(output_path)
                    assigned_path = str(cached["cached_path"])
                    source_path = str(cached["source_path"])
                    saved["cached_file"] = cached
                else:
                    assigned_path = output_path
                    source_path = output_path
                api.session_store.set_data_path(
                    session_id,
                    active_data_type,
                    assigned_path,
                    source_path=source_path,
                )
                reference = before_save_state.get("spectral_reference")
                previous_source = (before_save_state.get("path_sources") or {}).get(active_data_type)
                if reference and reference["source"] == previous_source and active_data_type in {"ABS", "ABS+BASE"}:
                    api.session_store.update_config(session_id, {
                        "spectral_reference": {**reference, "source": source_path},
                    })
                api.treatment_service.reset_runtime(session_id)
                saved["assigned_data_type"] = active_data_type
                saved["assigned_path"] = assigned_path
        except ValueError as exc:
            return api._error(str(exc), session_id)

        payload = api._session_payload(session_id)
        payload["cleaning"] = saved
        return api._json_response(payload, session_id)


    def save_sam_cleaning_for_file():
        session_id = api._current_session_id()
        payload = api.request.get_json(silent=True) or {}
        raw_file_path = payload.get("file_path")
        if not raw_file_path:
            return api._error("file_path is required", session_id)

        try:
            angle_threshold = float(payload.get("angle_threshold", 1.0))
            surface_threshold = float(payload.get("surface_threshold", 1.0))
        except (TypeError, ValueError):
            return api._error("angle_threshold and surface_threshold must be numeric", session_id)

        output_file_name = str(payload.get("output_file_name") or "")

        try:
            normalized = api._ensure_readable_treatment_file(str(raw_file_path))
            saved = api.treatment_service.save_file_sam_cleaned_h5(
                api.Path(normalized),
                angle_threshold,
                surface_threshold,
                output_file_name=output_file_name,
            )
        except ValueError as exc:
            return api._error(str(exc), session_id)

        return api._json_response({"cleaning": saved, "success": True}, session_id)

    api.analyze_sam_cleaning = analyze_sam_cleaning
    api.get_sam_cleaning_view = get_sam_cleaning_view
    api.reset_sam_cleaning = reset_sam_cleaning
    api.restore_sam_cleaning = restore_sam_cleaning
    api.save_sam_cleaning = save_sam_cleaning
    api.save_sam_cleaning_for_file = save_sam_cleaning_for_file
