"""Band-integrated OD kinetics with shot matching and blockwise uncertainty."""
from dataclasses import dataclass
import math

import numpy as np

from vd2_paired_analysis import BLOCK_PAIRS, MIN_BLOCKS


METHODS = ("od_of_means", "mean_pair_od", "lamp_matched", "sam_od_of_means", "sam_matched")


@dataclass(frozen=True)
class SpectralBand:
    center_nm: float
    half_width_nm: float
    monitor_rows: int

    @classmethod
    def from_payload(cls, payload):
        if not isinstance(payload, dict) or set(payload) != set(cls.__dataclass_fields__):
            raise ValueError("Select a wavelength, half-width, and number of lamp-reference rows")
        center, half, rows = (payload[key] for key in cls.__dataclass_fields__)
        if (any(type(value) not in (int, float) or not math.isfinite(value) for value in (center, half))
                or not 0 < half < center <= 3000 or type(rows) is not int or not 1 <= rows <= 4096):
            raise ValueError("Invalid wavelength band or lamp-reference rows")
        return cls(float(center), float(half), rows)

    def columns(self, axis):
        axis = np.asarray(axis, dtype=float)
        low, high = self.center_nm - self.half_width_nm, self.center_nm + self.half_width_nm
        if low < axis.min() or high > axis.max():
            raise ValueError("Selected wavelength band is outside the calibrated detector")
        columns = (low <= axis) & (axis <= high)
        if not columns.any():
            raise ValueError("Selected wavelength band contains no detector columns")
        return columns


def _sam(traces, percent):
    """Use the same mean time trace, angle and surface rules as Data Treatment."""
    reference = traces.mean(axis=0)
    norm = np.linalg.norm(traces, axis=1) * np.linalg.norm(reference)
    with np.errstate(divide="ignore", invalid="ignore"):
        cosine = (traces @ reference) / norm
        angle = np.degrees(np.arccos(np.clip(cosine, -1, 1)))
        surface = 100 * np.abs(traces.sum(axis=1) / reference.sum() - 1)
    return (angle <= 1) & (surface < percent)


def _match(abs_ids, base_ids, probe_a, probe_b):
    # Bounded search avoids quadratic memory and excludes distant intensity matches.
    matches = []
    for i in abs_ids:
        start, end = np.searchsorted(base_ids, (i - 20, i + 21))
        candidates = base_ids[start:end]
        candidates = candidates[np.isfinite(probe_b[candidates])]
        if not np.isfinite(probe_a[i]) or not len(candidates):
            return None
        closest = np.lexsort((np.abs(candidates - i), np.abs(probe_b[candidates] - probe_a[i])))[0]
        matches.append(candidates[closest])
    return np.asarray(matches, dtype=int)


class KineticAnalysis:
    """Compute one OD value per delay and stop on the largest pointwise SE."""

    def __init__(self, background, wavelengths, timedelays, band, method, surface_percent, dark_blocks=()):
        self.columns = band.columns(wavelengths)
        if band.monitor_rows >= background.shape[1]:
            raise ValueError("Lamp-reference rows occupy the entire camera image")
        self.rows = slice(band.monitor_rows, None)
        self.time = timedelays[self.rows]
        self.background = background
        self.band_background = background[self.columns, self.rows].sum(axis=0)
        self.probe_background = background[:, :band.monitor_rows].sum()
        self.monitor_rows = band.monitor_rows
        self.method = method
        self.surface_percent = surface_percent
        self.dark_blocks = tuple(dark[self.columns, self.rows].sum(axis=0) for dark in dark_blocks)
        self._a = []
        self._b = []
        self.values = self.errors = None
        self.estimate_mod = self.error_mod = None
        self.pairs_used = 0

    def _features(self, image):
        band = image[self.columns, self.rows].sum(axis=0, dtype=float) - self.band_background
        probe = image[:, :self.monitor_rows].sum(dtype=float) - self.probe_background
        trace = image.mean(axis=0, dtype=float)
        return band, math.log(probe) if probe > 0 else np.nan, trace

    def add(self, absorption, base):
        self._a.append(self._features(absorption))
        self._b.append(self._features(base))
        return len(self._a) % BLOCK_PAIRS == 0

    def _estimate(self, a, b, probe_a, probe_b, trace_a, trace_b):
        i = j = np.arange(len(a))
        if self.method.startswith("sam_"):
            i = np.flatnonzero(_sam(trace_a, self.surface_percent))
            j = np.flatnonzero(_sam(trace_b, self.surface_percent))
        if not len(i) or not len(j):
            return None
        if self.method in ("lamp_matched", "sam_matched"):
            j = _match(i, j, probe_a, probe_b)
            if j is None:
                return None
        absorption, base = a[i], b[j]
        means = self.method in ("od_of_means", "sam_od_of_means", "sam_matched")
        if means:
            absorption = absorption.mean(axis=0, keepdims=True)
            base = base.mean(axis=0, keepdims=True)
        if np.any(absorption <= 0) or np.any(base <= 0):
            return None
        values = 1000 * np.log10(base / absorption).mean(axis=0)
        gradient = 1000 / math.log(10) * (1 / absorption - 1 / base).mean(axis=0)
        return values, gradient, min(len(i), len(j))

    def calculate(self):
        self.values = self.errors = self.estimate_mod = self.error_mod = None
        self.pairs_used = 0
        if not self._a:
            return
        a, b = (np.asarray([row[0] for row in role]) for role in (self._a, self._b))
        probe_a, probe_b = (np.asarray([row[1] for row in role]) for role in (self._a, self._b))
        trace_a, trace_b = (np.asarray([row[2] for row in role]) for role in (self._a, self._b))
        features = (a, b, probe_a, probe_b, trace_a, trace_b)
        whole = self._estimate(*features)
        if whole is None:
            return
        self.values, gradient, self.pairs_used = whole
        self.estimate_mod = float(self.values.mean())
        count = len(a) // BLOCK_PAIRS
        if count < MIN_BLOCKS or len(self.dark_blocks) < 4:
            return
        blocks = []
        for start in range(0, count * BLOCK_PAIRS, BLOCK_PAIRS):
            estimate = self._estimate(*(x[start:start + BLOCK_PAIRS] for x in features))
            if estimate is None:
                return
            blocks.append(estimate[0])
        blocks = np.asarray(blocks)
        longer = blocks[:2 * (count // 2)].reshape(-1, 2, blocks.shape[-1]).mean(axis=1)
        short_error = blocks.std(axis=0, ddof=1) / math.sqrt(count)
        long_error = longer.std(axis=0, ddof=1) / math.sqrt(len(longer))
        dark_error = np.asarray(self.dark_blocks).std(axis=0, ddof=1) / math.sqrt(len(self.dark_blocks))
        self.errors = np.hypot(np.maximum(short_error, long_error), gradient * dark_error)
        self.error_mod = float(self.errors.max())
