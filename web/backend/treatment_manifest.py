"""Durable, folder-local provenance records for treatment DAT exports."""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, Optional

from treatment_network_path import (
    copy_local_file_to_smb_atomic,
    copy_smb_file_to_local,
    is_smb_path,
    smb_isfile,
    smb_join,
    smb_name,
)

TREATMENT_MANIFEST_FILE_NAME = "pyconlyse_treatment_manifest.json"
TREATMENT_MANIFEST_FORMAT = "pyconlyse.treatment-manifest"
TREATMENT_MANIFEST_VERSION = 1

_manifest_lock = Lock()
_OPERATION_FIELDS = (
    "source_path",
    "output_path",
    "converted",
    "overwritten",
    "deleted_source",
    "deleted_source_file",
    "reused_compressed",
    "compression",
    "compression_level",
    "source_size_bytes",
    "output_size_bytes",
    "space_change_bytes",
    "space_change_percent",
    "original_measurements",
    "kept_measurements",
    "removed_measurements",
    "angle_threshold",
    "surface_threshold",
)


def _path_name(path: str) -> str:
    if is_smb_path(path):
        return smb_name(path)
    if re.match(r"^[A-Za-z]:[\\/]", path):
        import ntpath

        return ntpath.basename(path)
    return Path(path).name


def _manifest_path(save_folder: str) -> str:
    return (
        smb_join(save_folder, TREATMENT_MANIFEST_FILE_NAME)
        if is_smb_path(save_folder)
        else str(Path(save_folder).expanduser() / TREATMENT_MANIFEST_FILE_NAME)
    )


def _read_manifest(manifest_path: str) -> Optional[object]:
    if is_smb_path(manifest_path):
        if not smb_isfile(manifest_path):
            return None
        with tempfile.TemporaryDirectory(
            prefix="pyconlyse_treatment_manifest_"
        ) as tmp_dir:
            local_path = Path(tmp_dir) / TREATMENT_MANIFEST_FILE_NAME
            copy_smb_file_to_local(manifest_path, local_path)
            try:
                return json.loads(local_path.read_text(encoding="utf-8"))
            except (OSError, TypeError, ValueError) as exc:
                raise ValueError(
                    f"Treatment manifest is not valid JSON: {manifest_path}"
                ) from exc

    local_path = Path(manifest_path).expanduser()
    if not local_path.is_file():
        return None
    try:
        return json.loads(local_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError) as exc:
        raise ValueError(
            f"Treatment manifest is not valid JSON: {manifest_path}"
        ) from exc


def _write_manifest(manifest_path: str, manifest: Dict[str, object]) -> int:
    payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True, default=str)
        + "\n"
    ).encode("utf-8")
    if is_smb_path(manifest_path):
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".json",
            prefix="pyconlyse_treatment_manifest_",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            try:
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
                return int(copy_local_file_to_smb_atomic(temporary_path, manifest_path))
            finally:
                temporary_path.unlink(missing_ok=True)

    local_path = Path(manifest_path).expanduser()
    local_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".json",
            prefix=f".{TREATMENT_MANIFEST_FILE_NAME}.",
            dir=local_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(payload)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, local_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return len(payload)


def _operation_summary(items: object) -> Dict[str, Dict[str, object]]:
    return {
        str(data_type): {
            field: value
            for field, value in item.items()
            if field in _OPERATION_FIELDS and value is not None
        }
        for data_type, item in (items or {}).items()
        if isinstance(item, dict)
    }


def _input_paths(
    session_state: Dict[str, object], recipe: Optional[Dict[str, object]]
) -> Dict[str, Dict[str, str]]:
    recipe_inputs = (recipe or {}).get("inputs") or {}
    if recipe_inputs:
        return {
            str(data_type): {
                "source_path": str(input_data.get("source_path") or ""),
                "cached_path": str(input_data.get("path") or ""),
            }
            for data_type, input_data in recipe_inputs.items()
            if isinstance(input_data, dict)
        }

    paths = session_state.get("paths") or {}
    sources = session_state.get("path_sources") or {}
    return {
        str(data_type): {
            "source_path": str(sources.get(data_type) or file_path or ""),
            "cached_path": str(file_path or ""),
        }
        for data_type, file_path in paths.items()
        if file_path
    }


def _new_document() -> Dict[str, object]:
    return {
        "format": TREATMENT_MANIFEST_FORMAT,
        "format_version": TREATMENT_MANIFEST_VERSION,
        "dat_files": [],
    }


def _validate_document(document: object, manifest_path: str) -> Dict[str, object]:
    if not isinstance(document, dict):
        raise ValueError(f"Treatment manifest must be a JSON object: {manifest_path}")
    if (
        document.get("format") != TREATMENT_MANIFEST_FORMAT
        or document.get("format_version") != TREATMENT_MANIFEST_VERSION
    ):
        raise ValueError(
            f"Treatment manifest has an unsupported format: {manifest_path}"
        )
    entries = document.get("dat_files")
    if not isinstance(entries, list) or any(
        not isinstance(entry, dict) for entry in entries
    ):
        raise ValueError(
            f"Treatment manifest dat_files must be a list of objects: {manifest_path}"
        )
    return document


def record_treatment_manifest(
    saved: Dict[str, object],
    *,
    session_state: Dict[str, object],
    workflow: Dict[str, object],
    recipe: Optional[Dict[str, object]] = None,
    preparation: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Atomically upsert provenance for one completed DAT result."""
    save_folder = str(session_state.get("save_folder") or "").strip()
    save_path = str(saved.get("save_path") or "").strip()
    if not save_folder or not save_path:
        raise ValueError("DAT was saved but its manifest target is not configured")
    dat_file = _path_name(save_path)
    if not dat_file:
        raise ValueError(
            "DAT was saved but its file name is unavailable for the manifest"
        )

    processing = dict(preparation or {})
    folder_set = (
        processing.get("folder_set")
        if isinstance(processing.get("folder_set"), dict)
        else {}
    )
    conversion_items = processing.get("conversions") or folder_set.get("conversions")
    cleaning_items = processing.get("cleaned") or folder_set.get("cleaned")
    timestamp = datetime.now(timezone.utc).isoformat()
    record = {
        "dat_file": dat_file,
        "saved_at": timestamp,
        "workflow": {
            "kind": str(workflow.get("kind") or "immediate"),
            "profile": str(workflow.get("profile") or ""),
            "label": str(workflow.get("label") or ""),
            "queue_job_id": str(workflow.get("queue_job_id") or ""),
        },
        "session": {
            "experiment_type": str(session_state.get("exp_type") or ""),
            "calculation_mode": str(session_state.get("calc_mode") or ""),
            "first_map_with_electrons": bool(
                session_state.get("first_map_with_electrons")
            ),
            "source_folder": str(
                folder_set.get("folder") or session_state.get("folder_path") or ""
            ),
        },
        "inputs": _input_paths(session_state, recipe),
        "processing": {
            "conversions": _operation_summary(conversion_items),
            "cleaning": _operation_summary(cleaning_items),
        },
        "result": {
            key: value
            for key, value in saved.items()
            if key in {"save_path", "rows", "cols", "bytes"} and value is not None
        },
    }
    manifest_path = _manifest_path(save_folder)

    with _manifest_lock:
        existing = _read_manifest(manifest_path)
        document = (
            _new_document()
            if existing is None
            else _validate_document(existing, manifest_path)
        )
        entries = document["dat_files"]
        document["dat_files"] = [
            entry
            for entry in entries
            if str(entry.get("dat_file") or "").casefold() != dat_file.casefold()
        ]
        document["dat_files"].append(record)
        document["dat_files"].sort(
            key=lambda entry: str(entry.get("dat_file") or "").casefold()
        )
        document["updated_at"] = timestamp
        manifest_bytes = _write_manifest(manifest_path, document)

    receipt = {
        "manifest_path": manifest_path,
        "manifest_dat_file": dat_file,
        "manifest_bytes": manifest_bytes,
    }
    saved.update(receipt)
    return receipt
