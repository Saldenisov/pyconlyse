"""Treatment per-file compression and progress routes."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    def _compression_job_snapshot(job_id: str) -> api.Dict[str, object]:
        with api._compression_jobs_lock:
            return dict(api._compression_jobs.get(job_id) or {})


    def _folder_set_job_snapshot(job_id: str) -> api.Dict[str, object]:
        with api._folder_set_jobs_lock:
            return dict(api._folder_set_jobs.get(job_id) or {})


    def _update_compression_job(job_id: str, **updates) -> None:
        with api._compression_jobs_lock:
            job = api._compression_jobs.setdefault(job_id, {})
            job.update(updates)
            job["updated_at"] = api.monotonic()


    def _update_folder_set_job(job_id: str, **updates) -> None:
        with api._folder_set_jobs_lock:
            job = api._folder_set_jobs.setdefault(job_id, {})
            job.update(updates)
            job["updated_at"] = api.monotonic()


    def _run_compression_job(job_id: str, session_id: str, source_path: str) -> None:
        def progress(phase: str, current: int, total: int, message: str) -> None:
            api._update_compression_job(
                job_id,
                phase=phase,
                current_bytes=int(current or 0),
                total_bytes=int(total or 0),
                message=message,
            )

        try:
            progress("start", 0, 0, "Starting Convert/Compress")
            conversion = api._compression_progress_summary(source_path, progress_callback=progress)
            api._update_compression_job(
                job_id,
                status="complete",
                phase="complete",
                current_bytes=int(conversion.get("output_size_bytes") or 0),
                total_bytes=int(conversion.get("output_size_bytes") or 0),
                message="Convert/Compress complete",
                conversion=conversion,
                payload={**api._session_payload(session_id), "conversion": conversion},
            )
        except ValueError as exc:
            api._update_compression_job(
                job_id,
                status="error",
                phase="error",
                message=str(exc),
                error=str(exc),
            )


    def compress_file_path():
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
        session_id = api._current_session_id()
        payload = api.request.get_json(silent=True) or {}
        file_path = payload.get("file_path")
        if not file_path:
            return api._error("file_path is required", session_id)

        try:
            source_path = api._ensure_within_allowed_root(str(file_path))
        except ValueError as exc:
            return api._error(str(exc), session_id)

        job_id = api.uuid4().hex
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
        session_id = api._current_session_id()
        job = api._compression_job_snapshot(str(job_id))
        if not job:
            return api._error("compression job not found", session_id, 404)
        return api._json_response({"compression_job": job, "success": True}, session_id)

    api._compression_job_snapshot = _compression_job_snapshot
    api._folder_set_job_snapshot = _folder_set_job_snapshot
    api._update_compression_job = _update_compression_job
    api._update_folder_set_job = _update_folder_set_job
    api._run_compression_job = _run_compression_job
    api.compress_file_path = compress_file_path
    api.start_compress_file_path = start_compress_file_path
    api.get_compress_file_status = get_compress_file_status
