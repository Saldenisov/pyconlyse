"""Streaming VD2 OD from sums of individually corrected 10 Hz pairs."""
import math

import numpy as np

from vd2_paired_analysis import BLOCK_PAIRS, MIN_BLOCKS


METHOD = "pair_cubic_pool"
PRECISION_AXES = ("kinetics", "spectrum", "both")
TRACE_UPDATE_PAIRS = 5


def _od(absorption, base):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where((absorption > 0) & (base > 0), 1000 * np.log10(base / absorption), np.nan)


def _fit_gain(design, absorption, base):
    valid = (absorption > 0) & (base > 0) & np.isfinite(absorption) & np.isfinite(base)
    if valid.sum() < 4:
        raise ValueError("Lamp-reference window needs positive counts at four or more calibrated wavelengths")
    x = design[valid]
    y = np.log10(absorption[valid] / base[valid])
    coefficients = np.linalg.lstsq(x, y, rcond=None)[0]
    for _ in range(4):
        residual = y - x @ coefficients
        median = np.median(residual)
        scale = 1.4826 * np.median(np.abs(residual - median))
        if scale < 1e-12:
            break
        weight = np.maximum(1 - ((residual - median) / (4.685 * scale)) ** 2, 0)
        if np.count_nonzero(weight) < 4:
            break
        coefficients = np.linalg.lstsq(x * weight[:, None], y * weight, rcond=None)[0]
    with np.errstate(over="ignore", under="ignore"):
        gain = np.power(10.0, design @ coefficients)
    if not np.isfinite(gain).all() or np.any(gain <= 0):
        raise ValueError("Lamp-reference window produced an invalid spectral gain")
    return gain


class SpectralPairAnalysis:
    """Accumulate two detector maps and keep only ROI traces for block SE."""

    def __init__(self, background, wavelengths, delays, band, delay_range=None,
                 precision_axis="kinetics", calibrated_columns=None):
        if calibrated_columns is None:
            calibrated_columns = (0, len(wavelengths) - 1)
        first, last = sorted(calibrated_columns)
        self.calibrated = slice(first, last + 1)
        wave = np.asarray(wavelengths, dtype=float)[self.calibrated]
        if len(wave) < 4 or not np.isfinite(wave).all() or not (
            np.all(np.diff(wave) > 0) or np.all(np.diff(wave) < 0)
        ):
            raise ValueError("Spectral correction requires at least four monotonic calibrated wavelengths")
        self.columns = band.columns(wave)
        self.wavelengths = wave[self.columns]
        self.monitor_rows = band.monitor_rows
        delays = np.asarray(delays, dtype=float)
        post_reference = delays[band.monitor_rows:]
        if not len(post_reference) or not np.isfinite(delays).all():
            raise ValueError("No calibrated delays remain after the lamp-reference rows")
        self.rows = np.arange(len(delays)) >= band.monitor_rows
        if delay_range is not None:
            low, high = delay_range
            if low < post_reference.min() or high > post_reference.max():
                raise ValueError("Select a delay range inside the camera time axis after the lamp-reference rows")
            self.rows &= (delays >= low) & (delays <= high)
        self.time = delays[self.rows]
        if not len(self.time):
            raise ValueError("Selected delay range contains no detector rows")
        self.precision_axis = precision_axis
        self._design = np.polynomial.polynomial.polyvander(2 * (wave - wave.min()) / np.ptp(wave) - 1, 3)
        self._shape = background.shape
        self._background = background[self.calibrated]
        self._total = np.zeros((2, *self._background.shape), dtype=float)
        self._block = np.zeros((2, len(self.wavelengths), len(self.time)), dtype=float)
        self._previous_block = None
        self._short = []
        self._long = []
        self._errors_dirty = False
        self.pairs_used = 0
        self.values = self.errors = self.spectrum = self.spectrum_errors = None
        self.estimate_mod = self.error_mod = self.kinetics_error_mod = self.spectrum_error_mod = None

    def _traces(self, sums):
        absorption, base = sums
        kinetics = _od(absorption.sum(axis=0), base.sum(axis=0))
        spectrum = _od(absorption, base).mean(axis=1)
        return kinetics, spectrum

    def add(self, absorption, base):
        ref = slice(self.monitor_rows)
        a = absorption[self.calibrated] - self._background
        b = base[self.calibrated] - self._background
        gain = _fit_gain(self._design, a[:, ref].sum(axis=1), b[:, ref].sum(axis=1))
        b *= gain[:, None]
        self._total[0] += a
        self._total[1] += b
        bounds = np.ix_(self.columns, self.rows)
        self._block[0] += a[bounds]
        self._block[1] += b[bounds]
        self.pairs_used += 1
        if self.pairs_used % BLOCK_PAIRS:
            return False
        self._short.append(self._traces(self._block))
        if self._previous_block is None:
            self._previous_block = self._block.copy()
        else:
            self._long.append(self._traces(self._previous_block + self._block))
            self._previous_block = None
        self._block.fill(0)
        self._errors_dirty = True
        return True

    def calculate(self):
        if not self.pairs_used:
            return
        self.values, self.spectrum = self._traces(self._total[:, self.columns][:, :, self.rows])
        self.estimate_mod = float(self.values.mean()) if np.isfinite(self.values).all() else None
        if self._errors_dirty and len(self._short) >= MIN_BLOCKS:
            # Independent contiguous 20/40-pair blocks. The shared BRUIT is fixed.
            short = (np.std(trace, axis=0, ddof=1) / math.sqrt(len(trace)) for trace in zip(*self._short))
            long = (np.std(trace, axis=0, ddof=1) / math.sqrt(len(trace)) for trace in zip(*self._long))
            self.errors, self.spectrum_errors = (np.maximum(a, b) for a, b in zip(short, long))
            self._errors_dirty = False
        self.kinetics_error_mod = self._maximum_error(self.values, self.errors)
        self.spectrum_error_mod = self._maximum_error(self.spectrum, self.spectrum_errors)
        errors = {"kinetics": self.kinetics_error_mod, "spectrum": self.spectrum_error_mod}
        selected = tuple(errors.values()) if self.precision_axis == "both" else (errors[self.precision_axis],)
        self.error_mod = max(selected) if all(value is not None for value in selected) else None

    @staticmethod
    def _maximum_error(values, errors):
        if errors is not None and np.isfinite(values).all() and np.isfinite(errors).all():
            return float(errors.max())
        return None

    def corrected_map(self):
        """Return OD in detector coordinates, matching the ordinary H5 map."""
        result = np.full(self._shape, np.nan)
        result[self.calibrated] = _od(*self._total) / 1000
        return result
