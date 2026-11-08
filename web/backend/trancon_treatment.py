"""Pure OD operations; RAW and coordinate arrays never enter this module.

Matrices use [delay, wavelength]. Cleaning preserves the source's ascending,
sequential neighbour repair and inclusive pixel selection. Legacy baseline
deliberately subtracts background[i] from row i and truncates to min(D, W),
as documented in docs/data-treatment/baseline-2026-10-09/static-contract.json.
SG is an explicitly versioned shifted-polynomial model, supported by bounded
G01/G02 NI references at N=window=3, not a general NI kernel/error emulator.
"""
from numbers import Integral, Real

import numpy as np


SG_VERSION = "shifted-polynomial-v1"


def _matrix(od):
    try:
        source = np.asarray(od)
    except (TypeError, ValueError) as exc:
        raise ValueError("OD must be a nonempty rectangular numeric matrix [delay,wavelength]") from exc
    if source.ndim != 2 or not all(source.shape) or source.dtype.kind not in "iuf":
        raise ValueError("OD must be a nonempty rectangular real numeric matrix [delay,wavelength]")
    if source.dtype.kind == "f" and source.dtype.itemsize > 8:
        raise ValueError("OD precision wider than float64 is unsupported")
    if source.dtype.kind in "iu" and ((source > 2**53).any() or (source < -(2**53)).any()):
        raise ValueError("Integer OD values must be exactly representable within float64's integer range")
    return np.array(source, dtype=np.float64, copy=True), str(source.dtype)


def _keys(operation, required, optional=()):
    allowed = {"kind", *required, *optional}
    if set(operation) - allowed:
        raise ValueError("Unknown operation parameter: " + ", ".join(sorted(map(str, set(operation) - allowed))))
    missing = set(required) - set(operation)
    if missing:
        raise ValueError("Missing operation parameter: " + ", ".join(sorted(missing)))


def _integer(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _finite(value, name):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        converted = float(value)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite float64 value") from exc
    if not np.isfinite(converted):
        raise ValueError(f"{name} must be a finite float64 value")
    return converted


def _pixels(value, size, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must contain two inclusive integer pixels")
    lower, upper = (_integer(x, name) for x in value)
    if not 0 <= lower <= upper < size:
        raise ValueError(f"{name} must be ordered and within 0..{size - 1}")
    return [lower, upper]


def _bounds(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("od_bounds must contain two ordered finite values")
    lower, upper = (_finite(x, "od_bounds") for x in value)
    if lower > upper:
        raise ValueError("od_bounds must be ordered")
    return [lower, upper]


def _require_finite(data, name):
    if not np.isfinite(data).all():
        raise ValueError(f"{name} requires finite OD; use explicit replace_nonfinite first")


def _result(original, output, retained, operation, details, input_dtype, assigned=()):
    retained = np.asarray(retained, dtype=np.intp).copy()
    before = original[retained]
    after = np.asarray(output, dtype=np.float64)
    equal = (before == after) | (np.isnan(before) & np.isnan(after))
    changed = retained[np.any(~equal, axis=1)].tolist()
    removed = np.setdiff1d(np.arange(len(original)), retained, assume_unique=True).tolist()
    modified = sorted(set(changed) | set(removed) | set(assigned))
    details.update(input_dtype=input_dtype, computation_dtype="float64", output_dtype=str(output.dtype),
                   modified_indices_space="input_rows", removed_indices=removed)
    return {"od": output, "retained_indices": retained, "modified_indices": modified,
            "operation": operation, "details": details}


def _clean(original, operation):
    _keys(operation, ("mode", "wavelength_pixels", "delay_pixels", "od_bounds", "precision"))
    if operation["mode"] not in ("delete", "approx"):
        raise ValueError("mode must be delete or approx")
    if operation["precision"] not in ("legacy_sgl", "float64"):
        raise ValueError("precision must be explicitly legacy_sgl or float64")
    if original.shape[1] < 2:
        raise ValueError("kinetic_clean requires at least two wavelength columns (legacy projection boundary)")
    wavelengths = _pixels(operation["wavelength_pixels"], original.shape[1], "wavelength_pixels")
    delays = _pixels(operation["delay_pixels"], original.shape[0], "delay_pixels")
    bounds = _bounds(operation["od_bounds"])
    _require_finite(original, "kinetic_clean")
    legacy_sgl = operation["precision"] == "legacy_sgl"
    with np.errstate(over="ignore", invalid="ignore"):
        data = original.astype(np.float32).astype(np.float64) if legacy_sgl else original.copy()
    _require_finite(data, "legacy_sgl conversion" if legacy_sgl else "kinetic_clean")
    # Calc_clean_kinetics adds selected columns in increasing pixel order,
    # then divides. Do not use nanmean or reorder this reduction.
    kinetics = np.zeros(data.shape[0], dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore"):
        for pixel in range(wavelengths[0], wavelengths[1] + 1):
            kinetics += data[:, pixel]
        kinetics /= wavelengths[1] - wavelengths[0] + 1
    _require_finite(kinetics, "kinetic projection")
    selected = np.arange(delays[0], delays[1] + 1)
    flagged = selected[(kinetics[selected] < bounds[0]) | (kinetics[selected] > bounds[1])].tolist()
    retained = np.arange(data.shape[0], dtype=np.intp)
    if operation["mode"] == "delete":
        retained = np.delete(retained, flagged)
        output = data[retained].copy()
    else:
        output = data.copy()
        if flagged and len(data) == 1:
            raise ValueError("Approximation of a flagged singleton has no qualified neighbour")
        # Each replacement sees the previously repaired state. This is not
        # simultaneous interpolation and deliberately ignores delay spacing.
        with np.errstate(over="ignore", invalid="ignore"):
            for index in flagged:
                if index == 0:
                    output[index] = output[index + 1]
                elif index == len(output) - 1:
                    output[index] = output[index - 1]
                else:
                    output[index] = (output[index - 1] + output[index + 1]) / 2.0
        _require_finite(output, "Sequential approximation")
    with np.errstate(over="ignore", invalid="ignore"):
        output = output.astype(np.float32) if legacy_sgl else output
    _require_finite(output, "Output precision conversion")
    canonical = {"kind": "kinetic_clean", "mode": operation["mode"], "wavelength_pixels": wavelengths,
                 "delay_pixels": delays, "od_bounds": bounds, "precision": operation["precision"]}
    details = {"kinetics": kinetics.tolist(), "flagged_indices": flagged,
               "selection": "inclusive_pixels_and_strictly_outside_od_bounds",
               "replacement_order": "ascending_sequential_neighbours",
               "precision_policy": "round_input_sgl_compute_dbl_round_output_sgl" if legacy_sgl else "float64",
               "row_coordinate_policy": "positional; no delay-value lookup"}
    return output, retained, canonical, details, flagged


def _baseline(data, operation):
    _keys(operation, ("delay_pixels",))
    pixels = _pixels(operation["delay_pixels"], data.shape[0], "delay_pixels")
    lower, upper = pixels
    if lower == upper:
        upper += 1
        if upper >= len(data):
            raise ValueError("Equal-last baseline bounds require an unqualified truncated window")
    background = np.zeros(data.shape[1], dtype=np.float64)
    with np.errstate(over="ignore", invalid="ignore"):
        for row in data[lower:upper + 1]:
            background += row
        background /= upper - lower + 1
        retained = np.arange(min(data.shape), dtype=np.intp)
        output = data[retained] - background[:len(retained), None]
    return output, retained, {"kind": "legacy_baseline", "delay_pixels": pixels}, {
        "effective_delay_pixels": [lower, upper], "background": background.tolist(),
        "formula": "out[i,j] = od[i,j] - background[i]",
        "output_rows": "min(input_delays,input_wavelengths)", "precision_policy": "float64",
        "nonfinite_policy": "ordinary_arithmetic; no omission or replacement"}, ()


def _sg(data, operation):
    _keys(operation, ("side", "order", "axis"), ("version", "weights"))
    side = _integer(operation["side"], "side")
    order = _integer(operation["order"], "order")
    axis = operation["axis"]
    if axis not in ("wavelength", "delay"):
        raise ValueError("axis must be wavelength or delay")
    if operation.get("version", SG_VERSION) != SG_VERSION:
        raise ValueError(f"Unsupported SG version; expected {SG_VERSION}")
    weights = operation.get("weights", [])
    if not isinstance(weights, list) or weights:
        raise ValueError("Only explicit empty SG weights are supported")
    window = 2 * side + 1
    if side < 0 or order < 0 or order >= window:
        raise ValueError("SG requires side>=0 and 0<=order<2*side+1")
    _require_finite(data, "savitzky_golay")
    lines = data.T if axis == "wavelength" else data
    if len(lines) < window:
        raise ValueError("SG axis is shorter than 2*side+1; NI short-input error is not emulated")
    output_lines = np.empty_like(lines)
    for index in range(len(lines)):
        start = min(max(index - side, 0), len(lines) - window)
        coordinates = np.arange(start, start + window, dtype=np.float64) - index
        with np.errstate(over="ignore", invalid="ignore"):
            design = np.vander(coordinates, N=order + 1, increasing=True)
        _require_finite(design, "SG polynomial coordinates")
        try:
            coefficients, _, rank, _ = np.linalg.lstsq(design, lines[start:start + window], rcond=None)
        except np.linalg.LinAlgError as exc:
            raise ValueError("SG polynomial solve failed") from exc
        if rank != order + 1:
            raise ValueError("SG polynomial design is numerically rank deficient")
        output_lines[index] = coefficients[0]
    _require_finite(output_lines, "SG result")
    output = output_lines.T.copy() if axis == "wavelength" else output_lines
    canonical = {"kind": "savitzky_golay", "side": side, "order": order, "axis": axis,
                 "version": SG_VERSION, "weights": []}
    details = {"window": window, "edge_policy": "shift_full_window_then_evaluate_local_polynomial",
               "precision_policy": "float64", "weights_policy": "unit_weights",
               "NI_reference_scope": "G01/G02: N=window=3, order=1, empty weights, display tolerance5e-6",
               "whole_NI_equivalence": False, "NI_error_policy_emulated": False}
    return output, np.arange(len(data), dtype=np.intp), canonical, details, ()


def _replace(data, operation):
    _keys(operation, ("nan", "positive_inf", "negative_inf"))
    values = {key: _finite(operation[key], key) for key in ("nan", "positive_inf", "negative_inf")}
    output = data.copy()
    masks = {"nan": np.isnan(data), "positive_inf": np.isposinf(data), "negative_inf": np.isneginf(data)}
    for key, mask in masks.items():
        output[mask] = values[key]
    return output, np.arange(len(data), dtype=np.intp), {"kind": "replace_nonfinite", **values}, {
        "replacement_counts": {key: int(mask.sum()) for key, mask in masks.items()},
        "policy": "explicit_web_replacement; not exact legacy NaN search semantics", "precision_policy": "float64"}, ()


def apply_od_operation(od, operation):
    """Return a new OD matrix and positional row lineage without mutating inputs.

    retained_indices maps output rows to input rows. modified_indices uses
    input row coordinates and includes removed rows, flagged assignments and
    numeric changes from explicit SGL rounding. Floating computation/output
    dtype is disclosed in details; only kinetic_clean requests SGL storage.
    """
    if not isinstance(operation, dict):
        raise ValueError("Operation must be an object")
    data, input_dtype = _matrix(od)
    kind = operation.get("kind")
    functions = {"kinetic_clean": _clean, "legacy_baseline": _baseline,
                 "savitzky_golay": _sg, "replace_nonfinite": _replace}
    if not isinstance(kind, str) or kind not in functions:
        raise ValueError(f"Unsupported OD operation: {kind}")
    output, retained, canonical, details, assigned = functions[kind](data, operation)
    return _result(data, output, retained, canonical, details, input_dtype, assigned)
