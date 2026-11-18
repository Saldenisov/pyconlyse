"""Publish paired DCAM run metadata beside the directly recorded H5."""

import json
from pathlib import Path


def write_paired_metadata(h5_path, result, machine):
    path = Path(h5_path)
    first_has_electrons = result["first_map_with_electrons"]
    metadata = {
        "schema_version": 1, "measurement": "paired_absorption_base",
        "capture_rate_hz": 10, "lamp_rate_hz": 10, "electron_rate_hz": 5,
        "first_frame_with_electrons": first_has_electrons, "beam_phase_source": "operator_selection",
        "beam_phase_verified": False,
        "frame_order": ["absorption", "base"] if first_has_electrons else ["base", "absorption"],
        "status": result["status"], "stop_reason": result["stop_reason"],
        "job_id": result["job_id"], "raw_h5": path.name,
        "sample_name": result["sample_name"], "sample_description": result.get("sample_description", ""),
        "requested_at": result.get("requested_at"), "capture_started_at": result.get("capture_started_at"),
        "machine": machine,
        "frames_recorded": result["frames_recorded"], "pairs_recorded": result["pairs_recorded"],
        "bruit_artifact_id": result["bruit_artifact_id"], "mode": result["mode"],
        "target_mod": result.get("target_mod"), "error_mod": result.get("error_mod"),
        "band": result.get("band"), "completed_at": result["completed_at"],
    }
    sidecar = path.with_suffix(".json")
    temporary = sidecar.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        temporary.rename(sidecar)
    finally:
        temporary.unlink(missing_ok=True)
    return {"metadata_path": str(sidecar)}
