"""Optical-density stitching request validation and Flask handlers."""

from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
import json
import os
import re
import tempfile


def _stitch_od_roots() -> List[str]:
    import treatment_api as api

    raw_roots = os.environ.get("PYCONLYSE_STITCH_OD_ROOTS")
    roots = raw_roots.split(os.pathsep) if raw_roots else list(api.DEFAULT_STITCH_OD_ROOTS)
    return [api._normalize_path(root) for root in roots if str(root).strip()]


def _is_within_stitch_od_root(path: str) -> bool:
    import treatment_api as api

    if api._is_within_allowed_root(path):
        return True
    candidate = api._normalize_path(path)
    for root in api._stitch_od_roots():
        if api.is_smb_path(candidate) or api.is_smb_path(root):
            if api.is_smb_path(candidate) and api.is_smb_path(root):
                try:
                    if api.smb_is_within(candidate, root):
                        return True
                except ValueError:
                    continue
        elif api._is_within_local_path(candidate, root):
            return True
    return False


def _ensure_readable_od_dat(path: str) -> str:
    import treatment_api as api

    normalized = api._normalize_path(path)
    if not api._is_within_stitch_od_root(normalized):
        raise ValueError("Path is outside the allowed treatment or stitch OD root")
    if api._path_suffix(normalized) != ".dat":
        raise ValueError("OD stitch input must be a .dat file")
    if api.is_smb_path(normalized):
        if api._mapped_smb_local_file(normalized):
            return normalized
        if not api.smb_isfile(normalized):
            raise ValueError("Selected OD DAT file does not exist")
        return normalized
    if not os.path.isfile(normalized):
        raise ValueError("Selected OD DAT file does not exist")
    return normalized


def _stitch_time_regions(payload: Dict[str, object]) -> List[Dict[str, float]]:
    regions = payload.get("time_regions") or []
    if not isinstance(regions, list):
        raise ValueError("time_regions must be a list")
    normalized: List[Dict[str, float]] = []
    for index, region in enumerate(regions):
        if not isinstance(region, dict):
            continue
        try:
            delay_start = float(region.get("delay_start", region.get("start")))
            delay_end = float(region.get("delay_end", region.get("end")))
        except (TypeError, ValueError):
            continue
        normalized_region = {
            "delay_start": delay_start,
            "delay_end": delay_end,
            "label": str(region.get("label") or f"Region {index + 1}"),
        }
        for prefix in ("left", "right"):
            try:
                normalized_region[f"{prefix}_wavelength_start"] = float(
                    region.get(f"{prefix}_wavelength_start", region.get("wavelength_start"))
                )
                normalized_region[f"{prefix}_wavelength_end"] = float(
                    region.get(f"{prefix}_wavelength_end", region.get("wavelength_end"))
                )
            except (TypeError, ValueError):
                pass
        normalized.append(normalized_region)
    return normalized


def _stitch_coefficients(payload: Dict[str, object]) -> Dict[str, float]:
    try:
        return {
            "left_scale": float(payload.get("left_scale", 1.0)),
            "left_offset": float(payload.get("left_offset", 0.0)),
            "right_scale": float(payload.get("right_scale", 1.0)),
            "right_offset": float(payload.get("right_offset", 0.0)),
            "right_delay_shift_pixels": int(float(payload.get("right_delay_shift_pixels", 0))),
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("Stitch coefficients must be numeric") from exc


def _default_stitched_output_name(
    first_path: str,
    second_path: str,
    wavelength_min: Optional[float] = None,
    wavelength_max: Optional[float] = None,
) -> str:
    import treatment_api as api

    first_stem = Path(api._path_name(first_path)).stem
    second_stem = Path(api._path_name(second_path)).stem
    first_tokens = re.split(r"[_\-\s]+", first_stem)
    second_tokens = re.split(r"[_\-\s]+", second_stem)
    shared_tokens = []
    for first_token, second_token in zip(first_tokens, second_tokens):
        if first_token != second_token:
            break
        shared_tokens.append(first_token)
    stem = "_".join(shared_tokens) or f"{first_stem}_{second_stem}"
    if wavelength_min is not None and wavelength_max is not None:
        stem = f"{stem}_{wavelength_min:g}-{wavelength_max:g}nm"
    return f"{stem}_stitched.dat"


def _stitch_manifest_path(output_path: str) -> str:
    import treatment_api as api

    if api.is_smb_path(output_path):
        output_name = api.smb_name(output_path)
        manifest_name = f"{Path(output_name).stem}.manifest.json"
        return api.smb_join(api.smb_parent(output_path), manifest_name)
    output = Path(output_path)
    return str(output.with_name(f"{output.stem}.manifest.json"))


def _write_stitch_manifest(output_path: str, manifest: Dict[str, object]) -> str:
    import treatment_api as api

    manifest_path = api._stitch_manifest_path(output_path)
    manifest_payload = json.dumps(manifest, indent=2, sort_keys=True)
    if api.is_smb_path(manifest_path):
        with tempfile.TemporaryDirectory(prefix="pyconlyse_stitch_manifest_") as tmp_dir:
            local_manifest = Path(tmp_dir) / api.smb_name(manifest_path)
            local_manifest.write_text(manifest_payload + "\n", encoding="utf-8")
            api.copy_local_file_to_smb_atomic(local_manifest, manifest_path)
    else:
        local_manifest = Path(manifest_path).expanduser()
        local_manifest.parent.mkdir(parents=True, exist_ok=True)
        local_manifest.write_text(manifest_payload + "\n", encoding="utf-8")
    return manifest_path


def _run_with_local_stitch_inputs(first_path: str, second_path: str, callback):
    import treatment_api as api

    with tempfile.TemporaryDirectory(prefix="pyconlyse_stitch_od_") as tmp_dir:
        tmp_root = Path(tmp_dir)

        def local_input(source_path: str, suffix: str) -> Path:
            mapped = api._mapped_smb_local_file(source_path) if api.is_smb_path(source_path) else None
            if mapped:
                return Path(mapped)
            if api.is_smb_path(source_path):
                local_path = tmp_root / f"{suffix}_{api._path_name(source_path)}"
                api.copy_smb_file_to_local(source_path, local_path)
                return local_path
            return Path(source_path)

        return callback(
            local_input(first_path, "a"),
            local_input(second_path, "b"),
            tmp_root,
        )


def stitch_od_dat_files():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    first_path = str(payload.get("file_a") or "").strip()
    second_path = str(payload.get("file_b") or "").strip()
    output_folder = str(payload.get("output_folder") or "").strip()
    output_file_name = Path(str(payload.get("output_file_name") or "")).name

    if not first_path or not second_path:
        return api._error("Two OD DAT files are required", session_id)
    if first_path == second_path:
        return api._error("Select two different OD DAT files", session_id)

    try:
        normalized_first = api._ensure_readable_od_dat(first_path)
        normalized_second = api._ensure_readable_od_dat(second_path)
        if not output_folder:
            output_folder = (
                api.smb_parent(normalized_first)
                if api.is_smb_path(normalized_first)
                else str(Path(normalized_first).parent)
            )
        normalized_output_folder = api._ensure_writable_output_folder(output_folder)
        coefficients = api._stitch_coefficients(payload)
        time_regions = api._stitch_time_regions(payload)
        if not output_file_name:
            preview = api._run_with_local_stitch_inputs(
                normalized_first,
                normalized_second,
                lambda local_first, local_second, _tmp_root: api.treatment_service.preview_od_stitch(
                    local_first,
                    local_second,
                    time_regions=time_regions,
                    left_scale=coefficients["left_scale"],
                    left_offset=coefficients["left_offset"],
                    right_scale=coefficients["right_scale"],
                    right_offset=coefficients["right_offset"],
                    right_delay_shift_pixels=coefficients["right_delay_shift_pixels"],
                ),
            )
            output_file_name = api._default_stitched_output_name(
                normalized_first,
                normalized_second,
                preview["stitched"]["wavelength_min"],
                preview["stitched"]["wavelength_max"],
            )
        if not output_file_name.lower().endswith(".dat"):
            output_file_name = f"{Path(output_file_name).stem}.dat"
        output_path = (
            api.smb_join(normalized_output_folder, output_file_name)
            if api.is_smb_path(normalized_output_folder)
            else str(Path(normalized_output_folder) / output_file_name)
        )

        def save_with_local_inputs(local_first, local_second, tmp_root):
            local_output = tmp_root / output_file_name if api.is_smb_path(output_path) else Path(output_path)
            stitched = api.treatment_service.stitch_od_dat_files(
                local_first,
                local_second,
                local_output,
                time_regions=time_regions,
                **coefficients,
            )
            if api.is_smb_path(output_path):
                bytes_written = api.copy_local_file_to_smb_atomic(local_output, output_path)
                stitched["bytes"] = int(bytes_written)
            return stitched

        stitched = api._run_with_local_stitch_inputs(
            normalized_first,
            normalized_second,
            save_with_local_inputs,
        )

        stitched.update(
            {
                "first_path": normalized_first,
                "second_path": normalized_second,
                "output_path": output_path,
            }
        )
        manifest = {
            "format_version": 1,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "operation": "vd2_od_stitch",
            "algorithm": {
                "name": "trusted_overlap_average",
                "description": (
                    "Keep left wavelengths below trusted overlap, average left/right in "
                    "trusted overlap, keep right wavelengths above trusted overlap."
                ),
            },
            "inputs": {
                "file_a": first_path,
                "file_b": second_path,
                "normalized_file_a": normalized_first,
                "normalized_file_b": normalized_second,
                "left_path": stitched.get("left_path"),
                "right_path": stitched.get("right_path"),
            },
            "output": {
                "path": output_path,
                "file_name": output_file_name,
                "rows": stitched.get("rows"),
                "cols": stitched.get("cols"),
                "bytes": stitched.get("bytes"),
                "wavelengths": stitched.get("wavelengths"),
                "timedelays": stitched.get("timedelays"),
                "wavelength_min": stitched.get("wavelength_min"),
                "wavelength_max": stitched.get("wavelength_max"),
                "timedelay_min": stitched.get("timedelay_min"),
                "timedelay_max": stitched.get("timedelay_max"),
            },
            "stitch": {
                "axis_overlap_range": stitched.get("axis_overlap_range"),
                "trusted_overlap_range": stitched.get("overlap_range"),
                "trusted_ranges": stitched.get("trusted_ranges"),
                "time_regions": time_regions,
            },
            "coefficients": coefficients,
            "fit": payload.get("fit") or payload.get("fit_summary") or None,
        }
        manifest_path = api._write_stitch_manifest(output_path, manifest)
        stitched["manifest_path"] = manifest_path
        stitched["manifest"] = manifest
    except ValueError as exc:
        return api._error(str(exc), session_id)

    payload = api._session_payload(session_id)
    payload["stitched"] = stitched
    return api._json_response(payload, session_id)


def preview_stitch_od_dat_files():
    import treatment_api as api

    session_id = api._current_session_id()
    payload = api.request.get_json(silent=True) or {}
    first_path = str(payload.get("file_a") or "").strip()
    second_path = str(payload.get("file_b") or "").strip()
    if not first_path or not second_path:
        return api._error("Two OD DAT files are required", session_id)
    if first_path == second_path:
        return api._error("Select two different OD DAT files", session_id)

    try:
        normalized_first = api._ensure_readable_od_dat(first_path)
        normalized_second = api._ensure_readable_od_dat(second_path)
        coefficients = api._stitch_coefficients(payload)
        time_regions = api._stitch_time_regions(payload)

        def preview_with_local_inputs(local_first, local_second, _tmp_root):
            fitted = None
            if bool(payload.get("fit_right")):
                coefficients["right_scale"] = 1.0
                coefficients["right_offset"] = 0.0
                fitted = api.treatment_service.fit_od_stitch_right_scale(
                    local_first,
                    local_second,
                    time_regions=time_regions,
                    right_delay_shift_pixels=coefficients["right_delay_shift_pixels"],
                )
                coefficients["right_scale"] = fitted["right_scale"]
                coefficients["right_offset"] = fitted["right_offset"]
            preview = api.treatment_service.preview_od_stitch(
                local_first,
                local_second,
                time_regions=time_regions,
                left_scale=coefficients["left_scale"],
                left_offset=coefficients["left_offset"],
                right_scale=coefficients["right_scale"],
                right_offset=coefficients["right_offset"],
                right_delay_shift_pixels=coefficients["right_delay_shift_pixels"],
            )
            preview["first_path"] = normalized_first
            preview["second_path"] = normalized_second
            preview["coefficients"] = dict(coefficients)
            if fitted:
                preview["fit"] = fitted
            preview["suggested_output_file_name"] = api._default_stitched_output_name(
                normalized_first,
                normalized_second,
                preview["stitched"]["wavelength_min"],
                preview["stitched"]["wavelength_max"],
            )
            return preview

        preview = api._run_with_local_stitch_inputs(
            normalized_first,
            normalized_second,
            preview_with_local_inputs,
        )
    except ValueError as exc:
        return api._error(str(exc), session_id)

    return api._json_response({"stitch_preview": preview, "success": True}, session_id)
