"""Read SK-Ana R/Shiny project matrices with a pure Python RData parser."""

from __future__ import annotations

from io import BytesIO

import numpy as np
import rdata

from .matrix import MatrixData


def _read_objects(content: bytes) -> dict:
    if not content.startswith((b"\x1f\x8b", b"BZh", b"\xfd7zXZ", b"RDX", b"RDA")):
        raise ValueError("Cannot read R project: invalid RData header.")
    try:
        return rdata.read_rda(BytesIO(content))
    except Exception as exc:
        raise ValueError(f"Cannot read R project: {exc}") from exc


def read_r_project(content: bytes, *, prefer_original: bool = False) -> MatrixData:
    """Extract current or original matrix from SK-Ana ``.Rda`` state.

    This migrates numerical data and axes only. R widget/session state is not
    interpreted; Python project state can subsequently be saved as ``.npz``.
    """
    objects = _read_objects(content)
    state = objects.get("project_state")
    if isinstance(state, dict):
        source = state.get("data")
        metadata = state.get("metadata") or {}
    else:
        source = objects.get("data", objects.get("Inputs"))
        metadata = {}
    if not isinstance(source, dict):
        raise ValueError("R project does not contain SK-Ana matrix data.")
    for suffix in (("Orig", "") if prefer_original else ("", "Orig")):
        matrix = source.get("mat" + suffix)
        delay = source.get("delay" + suffix)
        wavelength = source.get("wavl" + suffix)
        if matrix is None or delay is None or wavelength is None:
            continue
        matrix = np.asarray(matrix, dtype=float)
        delay = np.asarray(delay, dtype=float)
        wavelength = np.asarray(wavelength, dtype=float)
        if matrix.shape != (delay.size, wavelength.size):
            continue
        ids = source.get("delayId" + suffix)
        time = source.get("delaySave" + suffix)
        orientation = source.get("dataDatStr", source.get("datStr", "wxd"))
        if isinstance(orientation, np.ndarray):
            orientation = str(orientation.item())
        if orientation not in {"wxd", "dxw"}:
            orientation = "wxd"
        name = metadata.get("project_tag") or "R_project"
        if isinstance(name, np.ndarray):
            name = str(name.item())
        return MatrixData(matrix, delay, wavelength, str(name), orientation,
                          None if ids is None else np.asarray(ids, dtype=int),
                          delay if time is None else np.asarray(time, dtype=float))
    raise ValueError("R project has no matrix with matching delay and wavelength axes.")


def read_r_selection(content: bytes) -> dict:
    """Read the numeric ranges and masks saved by R's Selections export."""
    objects = _read_objects(content)
    state = objects.get("selection_state")
    source = state.get("data") if isinstance(state, dict) else objects.get("ll")
    if not isinstance(source, dict):
        raise ValueError("R file does not contain SK-Ana selections.")
    scale = float(np.asarray(source.get("dlScaleFacOrig", 1)).item())
    if not np.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid R delay scale factor.")

    def pair(name: str, multiplier: float = 1.) -> tuple[float, float] | None:
        value = source.get(name)
        if value is None:
            return None
        array = np.asarray(value, dtype=float).ravel()
        if array.size != 2 or not np.isfinite(array).all() or array[0] > array[1]:
            raise ValueError(f"Invalid R selection range: {name}.")
        return tuple((array * multiplier).tolist())

    def ranges(count_name: str, prefix: str, multiplier: float = 1.):
        count = int(np.asarray(source.get(count_name, 0)).item())
        if count < 0 or count > 100:
            raise ValueError(f"Invalid R mask count: {count_name}.")
        return [value for i in range(1, count + 1)
                if (value := pair(f"{prefix}{i}", multiplier)) is not None]

    dimensions = source.get("matDims")
    return {
        "project_tag": str(source.get("projectTag", "")),
        "matrix_dimensions": None if dimensions is None else
            tuple(np.asarray(dimensions, dtype=int).ravel().tolist()),
        "delay_range": pair("keepDlRange", scale),
        "wavelength_range": pair("keepWlRange"),
        "baseline_ranges": ranges("nMasksBaseline", "keepBaselineMask", scale),
        "excluded_delays": ranges("nMasksDl", "keepDlMask", scale),
        "excluded_wavelengths": ranges("nMasksWl", "keepWlMask"),
    }
