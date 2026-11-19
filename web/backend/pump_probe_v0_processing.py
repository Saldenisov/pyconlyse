"""Bounded TRANCON numeric integration, without devices or mutable RAW state.

Native LabVIEW diagram verification remains pending. The two RAW layouts
below have distinct background meanings and must not be interchanged.
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy.trancon_client import raw_background, raw_data, scale


TRANCON_GROUPS = ("BGI", "BGII", "IeI", "IeII", "I0I", "I0II")
V0_RAW_GROUPS = ("BG1", "Ir1", "Is1", "BG2", "Ir2", "Is2")
TRANCON_LAYOUT = "trancon-detectors-v1"
TRANCON_FLOAT_LAYOUT = "trancon-detectors-float32-v1"
V0_LAYOUT = "v0-pulse-states-v1"
OD_ALGORITHM = "signed-mean-of-shot-log10-v1"


def trancon_shot_od(frames, background=None):
    """Detector I/II pairing; transform each shot before averaging shots."""
    bg_i, bg_ii, ie_i, ie_ii, i0_i, i0_ii = np.asarray(frames, dtype=np.float64)
    if background is not None:
        bg_i = bg_i + background[0]
        bg_ii = bg_ii + background[1]
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return np.log10(((i0_i - bg_i) / (ie_i - bg_i))
                        / ((i0_ii - bg_ii) / (ie_ii - bg_ii)))


def float32_detector_counts(values):
    """Copy finite counts without silently rounding higher-precision inputs."""
    original = np.asarray(values)
    if original.dtype.kind not in "iuf" or not np.isfinite(original).all():
        raise ValueError("TRANCON float32 RAW counts must be finite numbers")
    with np.errstate(over="ignore", invalid="ignore"):
        result = original.astype(np.float32)
    if (not np.isfinite(result).all()
            or not np.array_equal(original, result.astype(original.dtype))):
        raise ValueError("TRANCON RAW counts must be exactly representable as float32")
    return np.array(result, dtype=np.float32, copy=True)


def v0_shot_od(frames):
    """V0 emulator: backgrounds belong to OFF/ON states, not detector I/II."""
    bg1, ir1, is1, bg2, ir2, is2 = np.asarray(frames, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        return np.log10(((is1 - bg1) / (ir1 - bg1)) / ((is2 - bg2) / (ir2 - bg2)))


def calculate_raw_od(blocks, layout, zero_slot_policy="retain", background=None):
    """Compute one row per delay; retain all stored slots unless explicitly asked."""
    if zero_slot_policy not in {"retain", "drop_whole_zero"}:
        raise ValueError("Unknown zero-slot policy")
    if layout not in {TRANCON_LAYOUT, TRANCON_FLOAT_LAYOUT, V0_LAYOUT}:
        raise ValueError("RAW channel semantics are unknown; OD cannot be reconstructed")
    if background is not None and layout not in {TRANCON_LAYOUT, TRANCON_FLOAT_LAYOUT}:
        raise ValueError("Detector RAW background correction requires TRANCON channel semantics")
    if background is not None:
        if (not isinstance(background, list) or len(background) != 2
                or any(isinstance(x, bool) or not isinstance(x, int)
                       or not -65535 <= x <= 65535 for x in background)):
            raise ValueError("RAW background requires two integer counts in -65535..65535")

    rows, used_counts, removed_counts = [], [], []
    for block in blocks:
        if layout == TRANCON_FLOAT_LAYOUT:
            block = float32_detector_counts(block)
        block = np.asarray(block, dtype=np.float64)
        if block.ndim != 3 or block.shape[0] != 6 or block.shape[2] == 0:
            raise ValueError("RAW must have six groups x shots x wavelengths")
        keep = np.ones(block.shape[1], dtype=bool)
        if zero_slot_policy == "drop_whole_zero":
            keep = ~(block == 0).all(axis=(0, 2))
        selected = block[:, keep, :]
        used_counts.append(int(keep.sum()))
        removed_counts.append(int((~keep).sum()))
        if selected.shape[1] == 0:
            rows.append(np.full(block.shape[2], np.nan))
        elif layout == TRANCON_LAYOUT:
            if (not np.isfinite(selected).all() or (selected < 0).any()
                    or (selected > 65535).any() or (selected != np.floor(selected)).any()):
                raise ValueError("TRANCON RAW counts must be integers in 0..65535")
            lists = selected.astype(np.int64).tolist()
            if background is None:
                row = raw_data(raw_data=[lists], trabs_precalc=[]).exp_data[0]
            else:
                row = raw_background(data_raw=[lists], raw_bg=background).data_corrected[0]
            rows.append(np.asarray(row, dtype=np.float64))
        else:
            # Frames stored by V0 are unaveraged: the nonlinear transform
            # precedes the shot mean. Do not ignore any NaN or infinity.
            with np.errstate(invalid="ignore", over="ignore"):
                shot_od = (trancon_shot_od(selected, background)
                           if layout == TRANCON_FLOAT_LAYOUT else v0_shot_od(selected))
                rows.append(shot_od.mean(axis=0))
    return np.asarray(rows), used_counts, removed_counts


def apply_dataset_recipe(od, blocks, layout, operations, wavelengths, delays,
                         source_row_indices=None):
    """Replay one detached dataset, carrying positional row identity and axes.

    ``blocks`` and the supplied axes describe the original source, never a
    previously shortened preview. RAW recalculation therefore remains first.
    """
    if not isinstance(operations, list) or len(operations) > 32:
        raise ValueError("Recipe must be a list with at most 32 operations")
    waves = np.asarray(wavelengths, dtype=np.float64).copy()
    axis = np.asarray(delays, dtype=np.float64).copy()
    if (waves.ndim != 1 or axis.ndim != 1 or not waves.size or not axis.size
            or not np.isfinite(waves).all() or not np.isfinite(axis).all()):
        raise ValueError("Dataset axes must be nonempty finite vectors")
    result = np.asarray(od, dtype=np.float64).copy() if od is not None else None
    if result is not None and result.shape != (axis.size, waves.size):
        raise ValueError("OD shape disagrees with dataset axes")
    row_map = np.arange(axis.size, dtype=np.int64)
    if source_row_indices is not None:
        supplied = np.asarray(source_row_indices)
        if (supplied.shape != axis.shape or supplied.dtype.kind not in "iu"
                or (supplied < 0).any() or np.unique(supplied).size != supplied.size):
            raise ValueError("Source row indices must be distinct nonnegative integers")
        row_map = supplied.astype(np.int64, copy=True)
    canonical, shot_info = [], None
    details, modified, removed_rows = [], set(), set()
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise ValueError("Each recipe operation must be an object")
        kind = operation.get("kind")
        if kind in {"raw_od", "raw_background"}:
            if index != 0:
                raise ValueError("RAW recalculation must be the first operation")
            if blocks is None:
                raise ValueError("This file does not contain shot-resolved RAW")
            policy = operation.get("zero_slot_policy", "retain")
            background = operation.get("counts") if kind == "raw_background" else None
            if kind == "raw_background" and background is None:
                raise ValueError("RAW background counts are required")
            allowed = {"kind", "zero_slot_policy", "counts"} if kind == "raw_background" else {"kind", "zero_slot_policy"}
            if set(operation) - allowed:
                raise ValueError("Unknown RAW operation parameter")
            result, counts, removed = calculate_raw_od(blocks, layout, policy, background)
            if result.shape != (axis.size, waves.size):
                raise ValueError("Source RAW dimensions disagree with dataset axes")
            shot_info = {"used_counts": counts, "removed_zero_slots": removed}
            canonical.append({"kind": kind, "zero_slot_policy": policy,
                              **({"counts": background} if background is not None else {})})
        elif kind == "scale":
            if set(operation) != {"kind", "factor"}:
                raise ValueError("Scale requires only kind and factor")
            factor = operation.get("factor")
            if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not np.isfinite(factor):
                raise ValueError("Scale factor must be finite")
            if result is None:
                raise ValueError("Load an OD map or recalculate RAW first")
            result = np.asarray(scale(scaleup=float(factor), data=result.tolist()).data_corrected)
            canonical.append({"kind": kind, "factor": float(factor)})
            modified.update(int(value) for value in row_map)
            details.append({"kind": kind, "modified_source_row_indices": row_map.tolist()})
        elif kind in {"kinetic_clean", "legacy_baseline", "savitzky_golay", "replace_nonfinite"}:
            if result is None:
                raise ValueError("Load an OD map or recalculate RAW first")
            from trancon_treatment import apply_od_operation

            before_map = row_map.copy()
            treated = apply_od_operation(result, operation)
            retained = np.asarray(treated["retained_indices"])
            changed = np.asarray(treated["modified_indices"])
            if (retained.ndim != 1 or retained.dtype.kind not in "iu"
                    or retained.size == 0 or (retained < 0).any()
                    or (retained >= len(before_map)).any()
                    or np.unique(retained).size != retained.size):
                raise ValueError("Treatment returned invalid retained row indices")
            if (changed.ndim != 1 or (changed.size and changed.dtype.kind not in "iu")
                    or (changed < 0).any() or (changed >= len(before_map)).any()):
                raise ValueError("Treatment returned invalid modified row indices")
            result = np.asarray(treated["od"], dtype=np.float64).copy()
            if result.shape != (retained.size, waves.size):
                raise ValueError("Treatment OD shape disagrees with retained rows")
            row_map = before_map[retained]
            axis = axis[retained]
            removed_step = sorted(set(before_map.tolist()) - set(row_map.tolist()))
            removed_rows.update(removed_step)
            modified.update(int(value) for value in before_map[changed.astype(np.int64)])
            modified.intersection_update(row_map.tolist())
            canonical.append(treated["operation"])
            details.append({"kind": kind, "input_source_row_indices": before_map.tolist(),
                            "retained_input_indices": retained.tolist(),
                            "modified_input_indices": changed.tolist(),
                            "modified_source_row_indices": before_map[changed.astype(np.int64)].tolist(),
                            "removed_source_row_indices": removed_step,
                            "details": treated["details"]})
        else:
            raise ValueError(f"Unsupported TRANCON operation: {kind}")
    if result is None:
        raise ValueError("This file has no OD map")
    return {"od": result, "wavelengths": waves, "delays": axis,
            "source_row_indices": row_map, "operations": canonical,
            "shot_selection": shot_info, "treatment_details": details,
            "modified_source_row_indices": sorted(modified),
            "removed_source_row_indices": sorted(removed_rows)}


def apply_recipe(od, blocks, layout, operations):
    """Compatibility result: OD, canonical recipe and source shot selection."""
    if od is not None:
        shape = np.asarray(od).shape
        if len(shape) != 2:
            raise ValueError("OD must be a rectangular delay x wavelength matrix")
    elif blocks is not None and len(blocks):
        shape = (len(blocks), np.asarray(blocks[0]).shape[-1])
    else:
        raise ValueError("Load an OD map or recalculate RAW first")
    result = apply_dataset_recipe(od, blocks, layout, operations,
                                  np.arange(shape[1]), np.arange(shape[0]))
    return result["od"], result["operations"], result["shot_selection"]
