"""Preparation, cleaning, and calculation for queued recipes."""

from copy import deepcopy
from pathlib import Path
from typing import Dict
from uuid import uuid4
import tempfile


def _queue_assign_job_path(job_state: Dict[str, object], data_type: str, source_path: str, *, local_artifact=False) -> None:
    import treatment_api as api

    if local_artifact and not api.is_smb_path(source_path):
        source_path = api._ensure_within_allowed_root(source_path)
        api._ensure_readable_treatment_file(source_path)
        local_path = source_path
    else:
        cached = api._cache_assignable_source(source_path)
        local_path = str(cached["cached_path"])
        source_path = str(cached["source_path"])
    job_state.setdefault("paths", {})[data_type] = local_path
    job_state.setdefault("path_sources", {})[data_type] = source_path


def _queue_cleaning_output_name(source_path: str, data_type: str, job_id: str) -> str:
    import treatment_api as api

    return f"{Path(api._path_name(source_path)).stem}_queue_{job_id[:8]}_{data_type.lower()}.h5"


def _tree_cleaning_sources(cached_files):
    import treatment_api as api

    return {
        role: {"path": item["source_path"], "sha256": api.vd2_fingerprint(item["cached_path"])["sha256"]}
        for role, item in cached_files.items()
    }


def _tree_cleaning_for_calculation(session_id, folder, cached_files):
    """Reuse a complete cleaning from this workspace only for identical inputs."""
    import treatment_api as api

    for job in reversed(api.treatment_queue_store.snapshot(session_id)["jobs"]):
        preparation = (job.get("preparation") or {}).get("folder_set") or {}
        cleaned = preparation.get("cleaned") or {}
        if (
            job["status"] != "completed" or preparation.get("folder") != folder
            or not preparation.get("clean_source_fingerprints") or cleaned.keys() != cached_files.keys()
        ):
            continue
        if preparation["clean_source_fingerprints"] != api._tree_cleaning_sources(cached_files):
            return {}
        outputs = {}
        for role, item in cleaned.items():
            path = api._ensure_within_allowed_root(str(item["output_path"]))
            cached = api._cache_assignable_source(path)
            api._validate_canonical_h5(Path(cached["cached_path"]), path)
            outputs[role] = cached
        return outputs
    return {}


def _queue_artifact_path(job_state: Dict[str, object], file_name: str) -> str:
    import treatment_api as api

    save_folder = str(job_state.get("save_folder") or "")
    if api.is_smb_path(save_folder):
        return api.smb_join(save_folder, file_name)
    return str(Path(save_folder).expanduser() / file_name)


def _queue_convert_to_job_h5(job_state: Dict[str, object], data_type: str, job_id: str) -> Dict[str, object]:
    """Create a job-owned H5 from the immutable cached input without deleting it."""
    import treatment_api as api

    cached_path = str(job_state["paths"][data_type])
    source_path = str((job_state.get("path_sources") or {}).get(data_type) or cached_path)
    api._ensure_readable_treatment_file(cached_path)
    output_name = f"{Path(api._path_name(source_path)).stem}_queue_{job_id[:8]}_{data_type.lower()}_raw.h5"
    output_path = api._queue_artifact_path(job_state, output_name)
    if api.is_smb_path(output_path):
        with tempfile.TemporaryDirectory(prefix="pyconlyse_queue_convert_") as tmp_dir:
            local_output = Path(tmp_dir) / output_name
            summary = api.treatment_service.convert_file_to_h5(Path(cached_path), local_output)
            if not local_output.is_file():
                raise ValueError(f"Queue conversion did not create H5 for {data_type}")
            bytes_written = api.copy_local_file_to_smb_atomic(local_output, output_path)
        summary["output_size_bytes"] = int(bytes_written)
    else:
        local_output = Path(output_path)
        local_output.parent.mkdir(parents=True, exist_ok=True)
        summary = api.treatment_service.convert_file_to_h5(Path(cached_path), local_output)
        if not local_output.is_file():
            raise ValueError(f"Queue conversion did not create H5 for {data_type}")
        summary["output_size_bytes"] = int(local_output.stat().st_size)
    summary.update(
        {
            "source_path": source_path,
            "cached_input_path": cached_path,
            "output_path": output_path,
            "converted": True,
            "deleted_source": False,
            "job_owned": True,
        }
    )
    return summary


def _queue_convert_worker(data_type: str, job_state: Dict[str, object], job_id: str, _progress_queue):
    import treatment_api as api

    return api._queue_convert_to_job_h5(job_state, data_type, job_id)


def _queue_clean_worker(
    data_type: str,
    session_state: Dict[str, object],
    angle_threshold: float,
    surface_threshold: float,
    output_file_name: str,
    _progress_queue,
):
    """Clean one independent role in its own process and service runtime."""
    import treatment_api as api

    role_state = deepcopy(session_state)
    role_state["active_data_type"] = data_type
    return api.TreatmentDataService().save_sam_cleaned_h5(
        f"clean:{uuid4()}",
        role_state,
        angle_threshold,
        surface_threshold,
        output_file_name=output_file_name,
    )


def _execute_standard_folder_queue_job(job_id: str, recipe: Dict[str, object]) -> Dict[str, object]:
    """Run one frozen folder action inside the serialized session queue."""
    import treatment_api as api

    session_id = str(recipe.get("session_id") or "")
    if not session_id:
        raise ValueError("Standard folder queue recipe is missing its session")
    operation_id = f"queue:{job_id}"
    with api._folder_set_jobs_lock:
        if api._folder_set_session_jobs.get(session_id):
            raise RuntimeError("A folder operation is already running for this treatment session")
        api._folder_set_session_jobs[session_id] = operation_id

    def progress(
        phase: str,
        current: int,
        total: int,
        message: str,
        files: Dict[str, Dict[str, object]],
    ) -> None:
        api.treatment_queue_store.update_job(
            job_id,
            phase=f"folder-{phase}",
            message=message,
            progress={
                "current_items": int(current or 0),
                "total_items": int(total or 0),
                "files": {key: dict(value) for key, value in (files or {}).items()},
            },
        )

    try:
        api._queue_preflight(recipe)
        api.session_store.update_config(session_id, dict(recipe.get("session_config") or {}))
        folder_payload = dict(recipe.get("folder_set") or {})
        folder_payload["_preserve_selected_folder"] = True
        progress("checking", 0, 0, "Checking standard folder recipe.", {})
        response_payload = api._set_inputs_from_folder_job_payload(
            session_id,
            folder_payload,
            progress_callback=progress,
            **({"queue_job_id": job_id} if folder_payload.get("_tree_workflow") else {}),
        )
        preparation = {"folder_set": response_payload.get("folder_set", {})}
        if not folder_payload.get("calculate", False):
            return {
                "result": None,
                "saved": None,
                "preparation": preparation,
                "message": "Folder action complete; calculation was not requested.",
            }
        if folder_payload.get("_tree_workflow") and not response_payload.get("result"):
            raise ValueError(preparation["folder_set"].get("auto_calc_error") or "No OD result was calculated for this folder")

        api.treatment_queue_store.update_job(
            job_id,
            phase="saving",
            message="Saving optical-density DAT result.",
        )
        session_state = api.session_store.snapshot(session_id)
        session_state.update(dict(recipe.get("save_target") or {}))
        saved = api._save_queued_result(session_id, session_state)
        api.record_treatment_manifest(
            saved,
            session_state=session_state,
            workflow={
                "kind": "standard_folder_set",
                "profile": recipe.get("profile"),
                "label": recipe.get("label"),
                "queue_job_id": job_id,
            },
            recipe=recipe,
            preparation=preparation,
        )
        return {
            "result": response_payload.get("result") or {"result_ready": True},
            "saved": saved,
            "preparation": preparation,
        }
    finally:
        with api._folder_set_jobs_lock:
            if api._folder_set_session_jobs.get(session_id) == operation_id:
                api._folder_set_session_jobs.pop(session_id, None)


def _execute_treatment_queue_job(job_id: str, recipe: Dict[str, object]) -> Dict[str, object]:
    """Run a job against a private session-state/runtime pair only."""
    import treatment_api as api

    if recipe.get("kind") == "standard_folder_set":
        return api._execute_standard_folder_queue_job(job_id, recipe)

    job_state = deepcopy(recipe["session"])
    job_state["save_folder"] = str(recipe["output"]["save_folder"])
    job_state["save_file_name"] = str(recipe["output"]["save_file_name"])
    runtime_id = f"queue:{job_id}"
    project = (recipe.get("provenance") or {}).get("vd2_project")
    preparation = {"conversions": {}, "cleaned": {}}
    try:
        api.treatment_queue_store.update_job(
            job_id,
            phase="preparing",
            message="Checking immutable queue inputs.",
        )
        api._queue_preflight(recipe)

        # Queue conversion is job-local and never deletes or overwrites a source.
        api.treatment_queue_store.update_job(
            job_id,
            phase="converting",
            message="Converting requested HIS inputs to H5.",
        )
        def complete_conversion(data_type, conversion):
            output_path = str(conversion["output_path"])
            if api._path_suffix(output_path) != ".h5":
                raise ValueError(f"Convert/Compress did not create H5 for {data_type}")
            api._queue_assign_job_path(job_state, data_type, output_path)
            preparation["conversions"][data_type] = conversion

        conversion_roles = [
            data_type for data_type, requested in (recipe.get("convert_to_h5") or {}).items()
            if requested
        ]
        if len(conversion_roles) == 1:
            data_type = conversion_roles[0]
            complete_conversion(
                data_type, api._queue_convert_to_job_h5(job_state, data_type, job_id)
            )
        elif conversion_roles:
            conversion_state = deepcopy(job_state)
            api._run_parallel_cpu_jobs(
                {data_type: (conversion_state, job_id) for data_type in conversion_roles},
                api._queue_convert_worker,
                on_complete=complete_conversion,
            )

        cleaning = recipe.get("cleaning") or {}
        if cleaning.get("state") == "pending":
            api.treatment_queue_store.update_job(
                job_id,
                phase="cleaning",
                message="Applying SAM map selections to job-specific H5 files.",
            )
            def complete_cleaning(data_type, saved):
                output_path = str(saved.get("output_path") or "")
                if not output_path or api._path_suffix(output_path) != ".h5":
                    raise ValueError(f"Cleaning did not create H5 for {data_type}")
                # Manifest cleaning already created a local file owned by this job.
                api._queue_assign_job_path(job_state, data_type, output_path, local_artifact=bool(project))
                preparation["cleaned"][data_type] = saved

            cleaning_state = deepcopy(job_state)
            cleaning_items = {}
            for data_type in cleaning.get("data_types") or []:
                source_path = str(
                    (cleaning_state.get("path_sources") or {}).get(data_type)
                    or cleaning_state["paths"][data_type]
                )
                cleaning_items[data_type] = (
                    cleaning_state,
                    float(cleaning["angle_threshold"]),
                    float(cleaning["surface_threshold"]),
                    api._queue_cleaning_output_name(source_path, data_type, job_id),
                )
            api._run_parallel_cpu_jobs(
                cleaning_items,
                api._queue_clean_worker,
                on_complete=complete_cleaning,
            )

        api.treatment_queue_store.update_job(
            job_id,
            phase="calculating",
            message="Calculating optical density.",
        )
        result = api.treatment_service.calc_abs(runtime_id, job_state)
        api.treatment_queue_store.update_job(
            job_id,
            phase="saving",
            message="Saving optical-density DAT result.",
        )
        saved = api._save_queued_result(runtime_id, job_state)
        api.record_treatment_manifest(
            saved,
            session_state=job_state,
            workflow={
                "kind": "queue_recipe",
                "profile": recipe.get("profile"),
                "label": recipe.get("label"),
                "queue_job_id": job_id,
            },
            recipe=recipe,
            preparation=preparation,
        )
        if project:
            api.record_project_treatment(project, saved, preparation)
        return {"result": result, "saved": saved, "preparation": preparation}
    finally:
        # Do not retain potentially large OD arrays after a queue item finishes.
        api.treatment_service.reset_runtime(runtime_id)
