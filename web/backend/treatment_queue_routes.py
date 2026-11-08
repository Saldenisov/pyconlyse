"""Queue and project-manifest Flask handlers."""

from pathlib import Path
import math


def _vd2_manifest_plan(payload):
    import treatment_api as api

    if api.h5py is None:
        raise ValueError("VD2 manifest treatment requires H5 support")
    path = api._ensure_within_allowed_root(str(payload.get("manifest_path") or ""))
    if api.is_smb_path(path):
        raise ValueError("Open the VD2 manifest through its local project folder")
    plan = api.inspect_project(path, allowed=api._ensure_readable_treatment_file, include_results=True)
    # All axes must agree before any queued cleaning or DAT output is created.
    import numpy as np
    for sample in plan["samples"]:
        if not sample["ready"]:
            continue
        try:
            axes = None
            for role, source in sample["inputs"].items():
                with api.h5py.File(source, "r") as handle:
                    if handle["metadata"].attrs.get("phase") != role:
                        raise ValueError(f"H5 phase does not match manifest role {role}")
                    current = (handle["wavelengths"][:], handle["timedelays"][:])
                if axes is not None and any(not np.array_equal(a, b) for a, b in zip(axes, current)):
                    raise ValueError("Bruit/Base/Absorption axes differ; acquire compatible inputs")
                axes = current
        except (OSError, KeyError, ValueError) as exc:
            sample.update(ready=False, error=str(exc))
    return {**plan, "project_folder": str(Path(plan["manifest_path"]).parent)}


def preview_vd2_manifest():
    import treatment_api as api

    session_id = api._current_session_id()
    try:
        plan = api._vd2_manifest_plan(api.request.get_json(silent=True) or {})
        return api._json_response({"success": True, "manifest": plan}, session_id)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return api._error(str(exc), session_id)


def queue_vd2_manifest():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    try:
        plan = api._vd2_manifest_plan(payload)
        mode = payload.get("mode")
        if mode not in (None, "all", "new"):
            raise ValueError("Calculation mode must be all or new")
        clean = payload.get("clean", True)
        if not isinstance(clean, bool):
            raise ValueError("clean must be a boolean")
        for key in ("angle_threshold", "surface_threshold"):
            value = float(payload.get(key, 1.0))
            if not math.isfinite(value) or value <= 0:
                raise ValueError("Cleaning thresholds must be finite and positive")
        selected = payload.get("samples")
        if not isinstance(selected, list) or not selected or len(selected) > 100 or len(set(selected)) != len(selected):
            raise ValueError("Select 1–100 distinct manifest samples")
        by_name = {sample["name"]: sample for sample in plan["samples"]}
        recipes = []
        skipped = []
        for name in selected:
            sample = by_name.get(name)
            if not sample or not sample["ready"]:
                raise ValueError(f"Sample is incomplete or changed: {name}")
            if mode == "new" and sample.get("result_path"):
                skipped.append(name)
                continue
            folder = str(Path(sample["inputs"]["ABS"]).parent)
            save_folder = plan["project_folder"] if mode else folder
            state = api._default_state()
            state.update(exp_type="ABS+BASE+NOISE", calc_mode="averaged", selected_data_type="ABS",
                         paths=sample["inputs"], path_sources=sample["inputs"], folder_path=folder,
                         save_folder=save_folder, save_file_name=f"{name}.dat", selection={})
            recipe = api._queue_recipe(session_id, {
                "profile": "VD2", "label": name, "allow_overwrite": False,
                "cleaning": {"enabled": clean, "state": "pending" if clean else "not_requested", "data_types": ["ABS", "BASE", "NOISE"] if clean else [],
                             "angle_threshold": payload.get("angle_threshold", 1.0),
                             "surface_threshold": payload.get("surface_threshold", 1.0)},
            }, session_state=state)
            recipe["provenance"]["vd2_project"] = {
                "manifest_path": plan["manifest_path"], "project_id": plan["project_id"],
                "sample": name, "bruit_reference": sample["bruit_reference"],
                "bruit_sample": sample["bruit_sample"], "bruit_reused": sample["bruit_reused"],
                "artifact_ids": sample["artifact_ids"],
            }
            for role, identity in sample["fingerprints"].items():
                recipe["inputs"][role]["fingerprint"]["sha256"] = identity["sha256"]
            recipes.append(recipe)
        # Validate every selected sample before enqueuing any of them. Private
        # snapshots leave the operator's currently open treatment unchanged.
        jobs = api.treatment_queue_store.enqueue_batch(session_id, recipes) if recipes else []
        started = bool(jobs) and api.treatment_queue_store.start(session_id, api._execute_treatment_queue_job)
        return api._json_response({"success": True, "queue_jobs": jobs, "started": started,
                               "skipped_samples": skipped,
                               "queue": api.treatment_queue_store.snapshot(session_id)}, session_id)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        return api._error(str(exc), session_id)


def get_treatment_queue():
    import treatment_api as api

    session_id = api._current_session_id()
    return api._json_response(
        {"queue": api.treatment_queue_store.snapshot(session_id), "success": True},
        session_id,
    )


def enqueue_treatment_queue_job():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    try:
        recipe = api._queue_recipe(session_id, payload)
        job = api.treatment_queue_store.enqueue(session_id, recipe)
        started = api.treatment_queue_store.start(
            session_id,
            api._execute_treatment_queue_job,
        )
    except (ValueError, OSError) as exc:
        return api._error(str(exc), session_id)
    return api._json_response(
        {
            "queue_job": job,
            "queue": api.treatment_queue_store.snapshot(session_id),
            "started": started,
            "success": True,
        },
        session_id,
    )


def enqueue_standard_folder_queue_job():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    try:
        if "folder_paths" in payload:
            paths = payload["folder_paths"]
            if (not isinstance(paths, list) or not 1 <= len(paths) <= 100
                    or any(not isinstance(path, str) or not path.strip() for path in paths)):
                raise ValueError("Select 1–100 measurement folders")
            recipes = [api._queue_standard_folder_recipe(session_id, {**payload, "folder_path": path}) for path in paths]
            if len({api._normalize_path(recipe["folder_set"]["folder_path"]) for recipe in recipes}) != len(recipes):
                raise ValueError("Select distinct measurement folders")
        else:
            recipes = [api._queue_standard_folder_recipe(session_id, payload)]
        jobs = api.treatment_queue_store.enqueue_batch(session_id, recipes)
        recipe = recipes[0]
        current = api.session_store.snapshot(session_id)
        selected_folder = str(current.get("folder_path") or "")
        current_save_folder = str(current.get("save_folder") or "")
        save_folder = str(recipe["save_target"]["save_folder"])
        if (
            selected_folder
            and api._normalize_path(selected_folder) == api._normalize_path(current_save_folder)
            and api._normalize_path(selected_folder) != api._normalize_path(save_folder)
        ):
            api.session_store.set_browsing_folder(session_id, save_folder)
        # Reflect the clicked measurement's name immediately while retaining
        # the parent selected in the file browser as the save folder.
        session = api.session_store.update_config(session_id, dict(recipe["save_target"]))
        started = api.treatment_queue_store.start(
            session_id,
            api._execute_treatment_queue_job,
        )
    except (ValueError, OSError) as exc:
        return api._error(str(exc), session_id)
    return api._json_response(
        {
            "queue_job": jobs[0],
            "queue_jobs": jobs,
            "queue": api.treatment_queue_store.snapshot(session_id),
            "session": session,
            "started": started,
            "success": True,
        },
        session_id,
    )


def run_treatment_queue():
    import treatment_api as api

    session_id = api._current_session_id()
    started = api.treatment_queue_store.start(session_id, api._execute_treatment_queue_job)
    queue = api.treatment_queue_store.snapshot(session_id)
    return api._json_response(
        {
            "queue": queue,
            "started": started,
            "success": True,
        },
        session_id,
    )


def remove_treatment_queue_job(job_id: str):
    import treatment_api as api

    session_id = api._current_session_id()
    try:
        removed = api.treatment_queue_store.remove_queued(session_id, str(job_id))
    except KeyError:
        return api._error("Queue job not found", session_id, 404)
    except RuntimeError as exc:
        return api._error(str(exc), session_id, 409)
    return api._json_response(
        {
            "removed": removed,
            "queue": api.treatment_queue_store.snapshot(session_id),
            "success": True,
        },
        session_id,
    )
