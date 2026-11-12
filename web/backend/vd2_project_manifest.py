"""Atomic VD2 project provenance and explicit, portable Bruit references. No device access."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import tempfile
from threading import RLock
from uuid import uuid4

MANIFEST_NAME = "vd2-manifest.json"
SCHEMA = "pyconlyse.vd2.project"
_lock = RLock()
BRUIT_SETTINGS = ("time_range", "streak_mode", "gate_mode", "mcp_gain", "wavelength_nm", "grating",
                  "acquire_exposure_time", "analog_integration_count", "delay_trigger_mode", "delay_a", "delay_e")


def now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return {"size_bytes": Path(path).stat().st_size, "sha256": digest.hexdigest()}


def load_manifest(path):
    path = Path(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("VD2 manifest exceeds 8 MiB")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("version") != 1
            or not isinstance(data.get("project_id"), str)
            or not isinstance(data.get("samples"), dict) or not isinstance(data.get("artifacts"), dict)):
        raise ValueError("Not a supported VD2 project manifest")
    for name, sample in data["samples"].items():
        if (not isinstance(sample, dict) or sample.get("name") != name or sample.get("folder") != name
                or not isinstance(sample.get("phases"), dict) or PureWindowsPath(name).name != name
                or PureWindowsPath(name).drive or name in {".", ".."}):
            raise ValueError("Invalid manifest sample identity")
    for identity, artifact in data["artifacts"].items():
        if (not isinstance(artifact, dict) or artifact.get("id") != identity
                or artifact.get("sample") not in data["samples"]
                or artifact.get("phase") not in {"BRUIT", "BASE", "ABSORPTION"}):
            raise ValueError("Invalid manifest acquisition identity")
    return data


def _write(path, data):
    data["updated_at"] = now()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".vd2-manifest-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _relative(root, path):
    return Path(path).resolve().relative_to(root.resolve()).as_posix()


def artifact_file(root, artifact, kind="h5", allowed=None, verify=True):
    relative = artifact.get(kind, {}).get("path", "")
    windows = PureWindowsPath(relative)
    if not relative or windows.drive or windows.root or ".." in windows.parts:
        raise ValueError("Manifest file paths must stay inside the project folder")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Manifest file escapes the project folder")
    if allowed is not None:
        allowed(str(path))
    if not path.is_file():
        raise ValueError(f"Manifest input is missing: {path}")
    expected = artifact[kind]
    if verify and fingerprint(path) != {key: expected.get(key) for key in ("size_bytes", "sha256")}:
        raise ValueError(f"Manifest input changed: {path}")
    return str(path)


class Vd2ProjectManifest:
    @staticmethod
    def verify_bruit_settings(request, machine):
        if request.phase == "BRUIT" or request.reuse_bruit in {"latest", "none", ""}:
            return
        with _lock:
            data = load_manifest(Path(request.output_root) / MANIFEST_NAME)
            artifact = data["artifacts"].get(request.reuse_bruit, {})
        if artifact.get("status") != "completed" or artifact.get("frames_requested") != request.frames_per_his:
            raise ValueError("Selected Bruit is incomplete or frame settings changed; record a new Bruit")
        old = (artifact.get("machine_before") or {}).get("streak_control", {}).get("values", {})
        current = (machine or {}).get("streak_control", {}).get("values", {})
        for key in BRUIT_SETTINGS:
            if old.get(key) is None or old.get(key) == "" or old[key] != current.get(key):
                raise ValueError(f"Bruit reuse cannot be verified ({key}); record a new Bruit")

    @staticmethod
    def _noise_candidate(data, request):
        if request.phase == "BRUIT":
            return None
        sample = data["samples"].get(request.run_name, {})
        if sample.get("bruit_reference"):
            return None
        own = sample.get("pending_bruit_reference")
        pending = {key: item for key, item in data["artifacts"].items()
                   if item.get("phase") == "BRUIT" and item.get("status") in {"saved", "processing"}}
        completed = {key: item for key, item in data["artifacts"].items()
                     if item.get("phase") == "BRUIT" and item.get("status") == "completed"}
        reference = request.reuse_bruit
        if own in pending and reference in {"latest", "none", ""}:
            reference = own
        elif reference == "latest":
            if completed:
                reference = max(completed, key=lambda key: completed[key]["completed_at"])
            elif pending:
                reference = max(pending, key=lambda key: pending[key].get("acquisition_completed_at", pending[key]["created_at"]))
        if reference in {"latest", "none", ""}:
            return None
        artifact = completed.get(reference) or pending.get(reference)
        if not artifact:
            raise ValueError("Selected Bruit has not been saved successfully")
        return reference, artifact

    def prepare(self, request):
        root = Path(request.output_root)
        path = root / MANIFEST_NAME
        with _lock:
            initial = load_manifest(path) if path.exists() else {"samples": {}, "artifacts": {}}
            noise = self._noise_candidate(initial, request)
        # Hashing a large source must not hold the manifest lock needed by the
        # camera worker and other project readers.
        if noise and noise[1]["status"] == "completed":
            artifact_file(root, noise[1])
        with _lock:
            data = load_manifest(path) if path.exists() else {
                "schema": SCHEMA, "version": 1, "project_id": uuid4().hex,
                "created_at": now(), "project_root_at_creation": str(root),
                "samples": {}, "artifacts": {},
            }
            sample = data["samples"].setdefault(request.run_name, {
                "name": request.run_name, "description": request.sample_description,
                "folder": request.run_name, "phases": {}, "bruit_reference": None,
            })
            if request.repeat_of:
                sample.update(repeat_of=request.repeat_of, repeat_series=request.repeat_series)
            previous = sample["phases"].get(request.phase)
            if request.replaces_artifact and previous != request.replaces_artifact:
                raise ValueError("Current measurement changed after replacement review")
            if request.sample_description:
                sample["description"] = request.sample_description
            bound = sample.get("bruit_reference")
            if (request.phase != "BRUIT" and bound and request.reuse_bruit not in {"latest", "none", "", bound}):
                raise ValueError("Sample already references a different Bruit; choose a new sample name")
            if request.phase != "BRUIT" and not sample.get("bruit_reference"):
                if noise:
                    reference, selected = noise
                    artifact = data["artifacts"].get(reference, {})
                    if artifact.get("status") not in {"completed", "saved", "processing"}:
                        raise ValueError("Selected Bruit failed before this acquisition started")
                    if selected.get("h5") and selected["h5"] != artifact.get("h5"):
                        raise ValueError("Selected Bruit changed while its source was being checked")
                    sample["bruit_reference"] = reference
            identity = uuid4().hex
            data["artifacts"][identity] = {
                "id": identity, "sample": request.run_name, "phase": request.phase,
                "status": "planned", "created_at": now(), "frames_requested": request.frames_per_his,
                "his": {"path": _relative(root, request.his_path)},
            }
            if request.replaces_artifact:
                data["artifacts"][identity]["replaces"] = request.replaces_artifact
            # Keep a completed measurement selected until its replacement has
            # passed conversion and its new fingerprints are durably recorded.
            if not previous or data["artifacts"].get(previous, {}).get("status") != "completed":
                sample["phases"][request.phase] = identity
            Path(request.his_path).parent.mkdir(parents=True, exist_ok=not request.reserve_directory)
            _write(path, data)
            return {"manifest_path": str(path), "artifact_id": identity,
                    "sample_name": request.run_name, "bruit_reference": sample["bruit_reference"]}

    def record(self, request, identity, status, **details):
        path = Path(request.output_root) / MANIFEST_NAME
        files = {}
        if status == "completed":
            for kind in ("his", "h5"):
                source = Path(request.his_path).with_suffix(f".{kind}")
                files[kind] = {"path": _relative(path.parent, source), **fingerprint(source)}
        with _lock:
            data = load_manifest(path)
            artifact = data["artifacts"][identity]
            artifact.update(status=status, **details)
            artifact["observed_at"] = now()
            if status == "saved":
                artifact["acquisition_completed_at"] = now()
                if request.phase == "BRUIT":
                    sample = data["samples"][request.run_name]
                    sample["pending_bruit_reference"] = identity
                    bound = data["artifacts"].get(sample.get("bruit_reference"), {})
                    if not bound or bound.get("status") == "failed":
                        # Pin the saved acquisition even before H5 exists.
                        # A failed conversion stays an explicit dependency,
                        # never a reason to substitute unrelated noise.
                        sample["bruit_reference"] = identity
            if status == "completed":
                artifact["completed_at"] = now()
                artifact.update(files)
                artifact["his"]["retained"] = True
                data["samples"][request.run_name]["phases"][request.phase] = identity
                if request.phase == "BRUIT":
                    data["samples"][request.run_name]["bruit_reference"] = identity
            elif status == "failed" and artifact.get("replaces"):
                sample = data["samples"][request.run_name]
                previous = artifact["replaces"]
                if data["artifacts"].get(previous, {}).get("status") == "completed":
                    if sample["phases"].get(request.phase) == identity:
                        sample["phases"][request.phase] = previous
                    if request.phase == "BRUIT" and sample.get("bruit_reference") == identity:
                        sample["bruit_reference"] = previous
            if status in {"completed", "failed"}:
                sample = data["samples"][request.run_name]
                if sample.get("pending_bruit_reference") == identity:
                    sample.pop("pending_bruit_reference", None)
            _write(path, data)

    def record_retention(self, request, identity, cleanup):
        path = Path(request.output_root) / MANIFEST_NAME
        with _lock:
            data = load_manifest(path)
            artifact = data["artifacts"][identity]
            artifact["his"].update(retained=cleanup["source_his_retained"],
                                   cleanup_status=cleanup["source_his_cleanup_status"],
                                   cleanup_observed_at=now())
            if cleanup.get("cleanup_warning"):
                artifact["cleanup_warning"] = cleanup["cleanup_warning"]
            _write(path, data)


def inspect_project(path, allowed=None, verify_files=True, include_results=False):
    path = Path(path)
    data = load_manifest(path)
    samples = []
    for name, sample in data["samples"].items():
        row = {"name": name, "description": sample.get("description", ""), "inputs": {},
               "folder": str(path.parent / sample["folder"]),
               "measurements": [{"id": item["id"], "phase": item["phase"], "status": item.get("status"),
                                 "frames": item.get("frames_requested"), "error": item.get("error", ""),
                                 "recorded_at": item.get("completed_at") or item.get("created_at"),
                                 "selected": sample["phases"].get(item["phase"]) == item["id"]}
                                for item in sorted(data["artifacts"].values(), key=lambda value: str(value.get("completed_at") or value.get("created_at") or ""), reverse=True)
                                if item["sample"] == name],
               "ready": False, "error": "", "bruit_reference": sample.get("bruit_reference"),
               "pending_bruit_reference": sample.get("pending_bruit_reference"),
               "paired_runs": sample.get("paired_runs", []), "artifact_ids": {}, "fingerprints": {}}
        try:
            for role, identity in {"BASE": sample.get("phases", {}).get("BASE"),
                                   "ABS": sample.get("phases", {}).get("ABSORPTION"),
                                   "NOISE": sample.get("bruit_reference")}.items():
                artifact = data["artifacts"].get(identity)
                expected = {"BASE": "BASE", "ABS": "ABSORPTION", "NOISE": "BRUIT"}[role]
                if not artifact or artifact.get("status") != "completed" or artifact.get("phase") != expected:
                    raise ValueError(f"Missing completed {expected}")
                if role != "NOISE" and artifact.get("sample") != name:
                    raise ValueError(f"{role} belongs to a different sample")
                row["inputs"][role] = artifact_file(path.parent, artifact, allowed=allowed, verify=verify_files)
                row["artifact_ids"][role] = identity
                row["fingerprints"][role] = {key: artifact["h5"][key] for key in ("size_bytes", "sha256")}
                if role == "NOISE":
                    row["bruit_sample"] = artifact.get("sample")
                    row["bruit_reused"] = artifact.get("sample") != name
            row["ready"] = True
            if include_results:
                row["result_path"] = None
                for result in reversed(sample.get("treatments") or []):
                    if not isinstance(result, dict) or result.get("artifact_ids") != row["artifact_ids"]:
                        continue
                    try:
                        row["result_path"] = artifact_file(path.parent, result, kind="dat", allowed=allowed)
                    except (OSError, ValueError, KeyError, TypeError, AttributeError):
                        continue
                    break
        except (ValueError, OSError, KeyError, TypeError) as exc:
            row["error"] = str(exc)
        samples.append(row)
    return {"manifest_path": str(path), "project_folder": str(path.parent), "project_id": data["project_id"], "samples": samples,
            "bruit_options": [{"id": key, "sample": item["sample"], "completed_at": item.get("completed_at"), "status": item["status"]}
                              for key, item in data["artifacts"].items()
                              if item.get("phase") == "BRUIT" and item.get("status") in {"completed", "saved", "processing"}]}


def record_paired_project_run(root, sample_name, file, result):
    """Append a paired acquisition without replacing the sample's legacy phases."""
    path = root / MANIFEST_NAME
    identity = {"path": _relative(root, file), **fingerprint(file)}
    record = {key: result[key] for key in (
        "job_id", "status", "pairs_recorded", "frames_recorded", "stop_reason", "completed_at",
        "bruit_artifact_id", "first_map_with_electrons", "mode",
    )}
    with _lock:
        data = load_manifest(path)
        sample = data["samples"].setdefault(sample_name, {
            "name": sample_name, "folder": sample_name, "description": "", "phases": {}, "bruit_reference": None,
        })
        sample.setdefault("paired_runs", []).append({**record, "h5": identity})
        _write(path, data)
    return str(path)


def record_project_treatment(provenance, saved, preparation):
    path = Path(provenance["manifest_path"])
    with _lock:
        data = load_manifest(path)
        if data["project_id"] != provenance["project_id"]:
            raise ValueError("Project manifest identity changed while treatment was running")
        output = Path(saved["save_path"])
        record = {"completed_at": now(), "artifact_ids": provenance["artifact_ids"],
                  "dat": {"path": _relative(path.parent, output), **fingerprint(output)},
                  "cleaning": preparation.get("cleaned", {})}
        sample = data["samples"][provenance["sample"]]
        sample.setdefault("treatments", []).append(record)
        _write(path, data)
