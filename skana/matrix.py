"""Import and preparation of spectrokinetic matrices.

Canonical layout: rows are delays, columns are wavelengths. ``wxd`` and
``dxw`` retain the historical R input labels.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import BinaryIO, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MatrixData:
    matrix: np.ndarray
    delay: np.ndarray
    wavelength: np.ndarray
    name: str = "matrix"
    orientation: str = "wxd"
    delay_id: np.ndarray | None = None
    time: np.ndarray | None = None

    def __post_init__(self) -> None:
        matrix = np.asarray(self.matrix, dtype=float)
        delay = np.asarray(self.delay, dtype=float)
        wavelength = np.asarray(self.wavelength, dtype=float)
        if matrix.ndim != 2 or delay.ndim != 1 or wavelength.ndim != 1:
            raise ValueError("Matrix must be 2D and axes must be 1D.")
        if matrix.shape != (delay.size, wavelength.size) or min(matrix.shape) < 2:
            raise ValueError("Matrix shape must match both axes and contain at least 2×2 values.")
        if not (np.isfinite(matrix).all() and np.isfinite(delay).all() and np.isfinite(wavelength).all()):
            raise ValueError("Matrix and axes must be finite.")
        if self.orientation not in {"wxd", "dxw"}:
            raise ValueError("orientation must be wxd or dxw.")
        ids = np.ones(delay.size, dtype=int) if self.delay_id is None else np.asarray(self.delay_id)
        if ids.shape != delay.shape:
            raise ValueError("delay_id must match delay axis.")
        time = delay if self.time is None else np.asarray(self.time, dtype=float)
        if time.shape != delay.shape or not np.isfinite(time).all():
            raise ValueError("Physical time must be finite and match delay axis.")
        object.__setattr__(self, "matrix", matrix.copy())
        object.__setattr__(self, "delay", delay.copy())
        object.__setattr__(self, "wavelength", wavelength.copy())
        object.__setattr__(self, "delay_id", ids.copy())
        object.__setattr__(self, "time", time.copy())


PRESETS = {
    "ELYSE (TSV)": ("\t", ".", "dxw"),
    "CSV": (",", ".", "wxd"),
    "Fluo": (";", ".", "wxd"),
    "Streak": (",", ".", "wxd"),
}


def _decode(source: bytes | str | BinaryIO) -> str:
    if hasattr(source, "read"):
        source = source.read()
    if isinstance(source, bytes):
        for encoding in ("utf-8-sig", "iso-8859-1"):
            try:
                return source.decode(encoding)
            except UnicodeDecodeError:
                pass
    return str(source)


def _infer_format(content: str) -> tuple[str, str]:
    lines = [line for line in content.splitlines() if line.strip()][:8]
    if len(lines) < 3:
        raise ValueError("Input needs a coordinate row and at least two data rows.")
    candidates = []
    for sep in ("\t", ";", ",", r"\s+"):
        for decimal in (".", ","):
            if sep == decimal:
                continue
            try:
                table = pd.read_csv(StringIO("\n".join(lines)), sep=sep, decimal=decimal,
                                    header=None, engine="python", dtype=str, on_bad_lines="skip")
                numeric = pd.to_numeric(table.iloc[1:, 1:].stack().astype(str).str.replace(decimal, ".", regex=False), errors="coerce")
                score = table.shape[1] * float(numeric.notna().mean()) if table.shape[1] >= 3 else 0
                candidates.append((score, sep, decimal))
            except (ValueError, AttributeError, pd.errors.ParserError):
                continue
    if not candidates or max(candidates)[0] < 2:
        raise ValueError("Could not detect a numeric matrix; choose a separator manually.")
    _, sep, decimal = max(candidates)
    return sep, decimal


def read_matrix(
    source: bytes | str | BinaryIO,
    *,
    name: str = "matrix",
    preset: str = "Auto",
    sep: str | None = None,
    decimal: str | None = None,
    orientation: str | None = None,
    compress_delay: int = 1,
    compress_wavelength: int = 1,
) -> MatrixData:
    """Read R-compatible corner-cell matrix from CSV/TSV/TXT/DAT.

    A text header row may precede the numeric coordinate row. Nonfinite signal
    values become zero, as in R ``getOneMatrix``; invalid axes are rejected.
    """
    content = _decode(source)
    if preset == "Auto":
        default_sep, default_decimal = _infer_format(content)
        default_orientation = "wxd"
    elif preset == "Other":
        default_sep, default_decimal, default_orientation = "\t", ".", "wxd"
    else:
        default_sep, default_decimal, default_orientation = PRESETS[preset]
    sep = sep or default_sep
    decimal = decimal or default_decimal
    orientation = orientation or default_orientation
    if sep not in {"\t", ";", ",", " ", r"\s+"} or decimal not in {".", ","}:
        raise ValueError("Unsupported separator or decimal mark.")
    read_sep = r"\s+" if sep == " " else sep
    rows = pd.read_csv(StringIO(content), sep=read_sep, header=None, decimal=decimal,
                       engine="python", dtype=str, skip_blank_lines=True)
    if rows.shape[0] < 3 or rows.shape[1] < 3:
        raise ValueError("Input needs a corner cell, two axis points, and a 2×2 matrix.")
    first = pd.to_numeric(rows.iloc[0, 0], errors="coerce")
    if pd.isna(first) and str(rows.iloc[0, 0]).strip() not in {"", "nan", "None"}:
        rows = rows.iloc[1:, :]
    numeric = rows.apply(lambda col: pd.to_numeric(col.str.replace(decimal, ".", regex=False), errors="coerce"))
    first_row = numeric.iloc[0, 1:].to_numpy(dtype=float)
    first_col = numeric.iloc[1:, 0].to_numpy(dtype=float)
    values = numeric.iloc[1:, 1:].to_numpy(dtype=float)
    if not np.isfinite(first_row).all() or not np.isfinite(first_col).all():
        raise ValueError("Coordinate axes must be numeric and finite.")
    values = np.where(np.isfinite(values), values, 0.0)
    if orientation == "dxw":
        delay, wavelength, values = first_row, first_col, values.T
    elif orientation == "wxd":
        delay, wavelength = first_col, first_row
    else:
        raise ValueError("orientation must be wxd or dxw.")
    d_order, w_order = np.argsort(delay), np.argsort(wavelength)
    result = MatrixData(values[np.ix_(d_order, w_order)], delay[d_order], wavelength[w_order], name, orientation)
    return compress(result, compress_delay, compress_wavelength)


def compress(data: MatrixData, delay_factor: int = 1, wavelength_factor: int = 1) -> MatrixData:
    """Average adjacent blocks, including incomplete final blocks as R does."""
    if int(delay_factor) != delay_factor or int(wavelength_factor) != wavelength_factor or min(delay_factor, wavelength_factor) < 1:
        raise ValueError("Compression factors must be positive integers.")
    fd, fw = int(delay_factor), int(wavelength_factor)
    d = np.array([data.delay[i:i + fd].mean() for i in range(0, data.delay.size, fd)])
    w = np.array([data.wavelength[j:j + fw].mean() for j in range(0, data.wavelength.size, fw)])
    m = np.array([[data.matrix[i:i + fd, j:j + fw].mean() for j in range(0, data.matrix.shape[1], fw)]
                  for i in range(0, data.matrix.shape[0], fd)])
    ids = np.array([data.delay_id[i] for i in range(0, data.delay.size, fd)])
    t = np.array([data.time[i:i + fd].mean() for i in range(0, data.time.size, fd)])
    return MatrixData(m, d, w, data.name, data.orientation, ids, t)


def postprocess_compress(data: MatrixData, delay_factor: int = 1,
                         wavelength_factor: int = 1) -> MatrixData:
    """R's second compression stage: averaged physical times, indexed display delays."""
    if delay_factor == 1 and wavelength_factor == 1:
        return data
    reduced = compress(data, delay_factor, wavelength_factor)
    return MatrixData(reduced.matrix, np.arange(1, reduced.delay.size + 1),
                      reduced.wavelength, reduced.name, reduced.orientation,
                      reduced.delay_id, reduced.time)


def transform_delay(delay: np.ndarray, mode: str) -> np.ndarray:
    delay = np.asarray(delay, dtype=float)
    if mode == "None":
        return delay.copy()
    if mode == "Index":
        return np.arange(1, delay.size + 1, dtype=float)
    if mode != "Log10":
        raise ValueError("Unknown delay transform.")
    positive = np.flatnonzero(delay > 0)
    if not positive.size:
        raise ValueError("Log10 transform requires a positive delay.")
    first = positive[0]
    out = delay.copy()
    if first:
        out[:first] = out[first] * np.arange(1, first + 1) / (first + 1)
    return np.log10(out)


def combine(items: Sequence[MatrixData], mode: str = "single", delay_transform: str = "None") -> MatrixData:
    if not items:
        raise ValueError("Select at least one matrix.")
    if mode == "single":
        if len(items) != 1:
            raise ValueError("Single mode requires one matrix.")
        m, d, w = items[0].matrix, items[0].delay, items[0].wavelength
        ids, time = items[0].delay_id, items[0].time
    elif mode == "average":
        ref = items[0]
        if any(not (np.array_equal(x.delay, ref.delay) and np.array_equal(x.wavelength, ref.wavelength)) for x in items[1:]):
            raise ValueError("Average requires identical delay and wavelength grids.")
        m, d, w = np.mean([x.matrix for x in items], axis=0), ref.delay, ref.wavelength
        ids, time = ref.delay_id, ref.time
    elif mode == "tile_delay":
        ref = items[0]
        if any(not np.array_equal(x.wavelength, ref.wavelength) for x in items[1:]):
            raise ValueError("Delay tiling requires identical wavelength grids.")
        m = np.vstack([x.matrix for x in items])
        d = np.arange(1, m.shape[0] + 1, dtype=float)
        w = ref.wavelength
        ids = np.concatenate([np.full(x.delay.size, i + 1) for i, x in enumerate(items)])
        time = np.concatenate([x.time for x in items])
        delay_transform = "None"
    elif mode == "tile_wavelength":
        ref = items[0]
        if any(not np.array_equal(x.delay, ref.delay) for x in items[1:]):
            raise ValueError("Wavelength tiling requires identical delay grids.")
        m = np.hstack([x.matrix for x in items])
        d = ref.delay
        w = np.concatenate([x.wavelength for x in items])
        order = np.argsort(w)
        m, w = m[:, order], w[order]
        ids, time = ref.delay_id, ref.time
    else:
        raise ValueError("Unknown combination mode.")
    return MatrixData(m, transform_delay(d, delay_transform), w, "+".join(x.name for x in items),
                      items[0].orientation if len({x.orientation for x in items}) == 1 else "wxd", ids, time)


def select(data: MatrixData, *, delay_range: tuple[float, float] | None = None,
           wavelength_range: tuple[float, float] | None = None,
           excluded_delays: Sequence[tuple[float, float]] = (),
           excluded_wavelengths: Sequence[tuple[float, float]] = (),
           delay_keep: np.ndarray | None = None,
           wavelength_keep: np.ndarray | None = None,
           intensity_range: tuple[float, float] | None = None) -> MatrixData:
    dmask = np.ones(data.delay.size, dtype=bool)
    wmask = np.ones(data.wavelength.size, dtype=bool)
    if delay_keep is not None:
        candidate = np.asarray(delay_keep, dtype=bool)
        if candidate.shape != dmask.shape:
            raise ValueError("delay_keep must match delay axis.")
        dmask &= candidate
    if wavelength_keep is not None:
        candidate = np.asarray(wavelength_keep, dtype=bool)
        if candidate.shape != wmask.shape:
            raise ValueError("wavelength_keep must match wavelength axis.")
        wmask &= candidate
    if delay_range is not None:
        dmask &= (data.delay >= delay_range[0]) & (data.delay <= delay_range[1])
    if wavelength_range is not None:
        wmask &= (data.wavelength >= wavelength_range[0]) & (data.wavelength <= wavelength_range[1])
    for low, high in excluded_delays:
        dmask &= ~((data.delay >= low) & (data.delay <= high))
    for low, high in excluded_wavelengths:
        wmask &= ~((data.wavelength >= low) & (data.wavelength <= high))
    result = data.matrix[np.ix_(dmask, wmask)]
    if intensity_range is not None:
        result = np.clip(result, *intensity_range)
    return MatrixData(result, data.delay[dmask], data.wavelength[wmask], data.name,
                      data.orientation, data.delay_id[dmask], data.time[dmask])


def suggest_signal_mask(data: MatrixData, axis: str, threshold_fraction: float = 0.05) -> np.ndarray:
    """Mark signal-bearing rows or columns using a robust RMS threshold.

    R uses variance changepoints for its experimental automatic masks; this
    independent heuristic makes a different, inspectable selection.
    """
    if axis not in {"delay", "wavelength"} or not 0 < threshold_fraction < 1:
        raise ValueError("axis must be delay or wavelength; threshold_fraction must be in (0, 1).")
    strength = np.sqrt(np.mean(data.matrix**2, axis=1 if axis == "delay" else 0))
    groups = ([np.flatnonzero(data.delay_id == exp) for exp in np.unique(data.delay_id)]
              if axis == "delay" else [np.arange(strength.size)])
    keep = np.zeros(strength.size, dtype=bool)
    for indices in groups:
        values = strength[indices]
        floor, peak = np.quantile(values, [0.1, 0.95])
        if peak <= floor:
            keep[indices] = True
            continue
        active = values >= floor + threshold_fraction * (peak - floor)
        if not active.any():
            active[np.argmax(values)] = True
        first, last = np.flatnonzero(active)[[0, -1]]
        first, last = max(0, first - 1), min(len(indices) - 1, last + 1)
        if last == first and len(indices) > 1:
            last = min(len(indices) - 1, first + 1)
        keep[indices[first:last + 1]] = True
    return keep


def suggest_baseline_intervals(data: MatrixData, threshold_fraction: float = 0.05) -> list[tuple[float, float]]:
    """Return leading quiet-time intervals before detected signal in each experiment."""
    keep = suggest_signal_mask(data, "delay", threshold_fraction)
    ranges = []
    for exp in np.unique(data.delay_id):
        indices = np.flatnonzero(data.delay_id == exp)
        active = np.flatnonzero(keep[indices])
        if active.size and active[0] >= 2:
            ranges.append((float(data.delay[indices[0]]),
                           float(data.delay[indices[active[0] - 1]])))
    return ranges


def baseline_correct(data: MatrixData, intervals: Sequence[tuple[float, float]]) -> MatrixData:
    """R-style baseline: mean per wavelength within each delay interval.

    Each mean is subtracted from that interval's start through the start of
    the next baseline interval (or the matrix end).
    """
    matrix = data.matrix.copy()
    ranges = sorted((float(low), float(high)) for low, high in intervals if high > low)
    for i, (low, high) in enumerate(ranges):
        baseline_rows = (data.delay >= low) & (data.delay <= high)
        if not baseline_rows.any():
            continue
        offset = matrix[baseline_rows].mean(axis=0)
        next_low = ranges[i + 1][0] if i + 1 < len(ranges) else np.inf
        target_rows = (data.delay >= low) & (data.delay < next_low)
        matrix[target_rows] -= offset
    return MatrixData(matrix, data.delay, data.wavelength, data.name,
                      data.orientation, data.delay_id, data.time)


def export_matrix(data: MatrixData, orientation: str | None = None) -> bytes:
    """Return R-compatible corner-cell CSV; orientation follows imported data by default."""
    orientation = orientation or data.orientation
    if orientation == "wxd":
        grid = np.block([[np.zeros((1, 1)), data.wavelength[None, :]],
                         [data.delay[:, None], data.matrix]])
    elif orientation == "dxw":
        grid = np.block([[np.zeros((1, 1)), data.delay[None, :]],
                         [data.wavelength[:, None], data.matrix.T]])
    else:
        raise ValueError("orientation must be wxd or dxw.")
    return pd.DataFrame(grid).to_csv(index=False, header=False).encode("utf-8")
