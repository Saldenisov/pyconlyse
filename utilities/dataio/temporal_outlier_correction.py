"""Auditable, per-wavelength correction of isolated temporal OD excursions.

This empirical correction does not recover a physical measurement. Detection
uses the original map; replacements are the arithmetic mean of adjacent delay
values. Missing measurements can be filled in a separate audited step. NumPy only.
"""

import warnings
from dataclasses import asdict, dataclass
from typing import Tuple

import numpy as np


@dataclass(frozen=True)
class OutlierConfig:
    min_excursion_od: float = 0.005
    min_fractional_excursion: float = 0.20
    sigma_multiplier: float = 4.0
    unstable_sigma_multiplier: float = 2.0
    max_neighbor_change_fraction: float = 0.5
    min_noise_samples: int = 8
    protected_delay_intervals_ps: Tuple[Tuple[float, float], ...] = ()

    def __post_init__(self):
        positive = (
            self.min_excursion_od,
            self.sigma_multiplier,
            self.unstable_sigma_multiplier,
            self.max_neighbor_change_fraction,
        )
        if not np.isfinite(positive).all() or min(positive) <= 0:
            raise ValueError("Outlier thresholds must be finite and positive")
        if self.unstable_sigma_multiplier > self.sigma_multiplier:
            raise ValueError("Unstable multiplier cannot exceed normal multiplier")
        if self.max_neighbor_change_fraction >= 1:
            raise ValueError("Neighbor change fraction must be less than one")
        if (
            not np.isfinite(self.min_fractional_excursion)
            or not 0 <= self.min_fractional_excursion < 1
        ):
            raise ValueError("Fractional excursion must be finite in [0,1)")
        if not isinstance(self.min_noise_samples, int) or self.min_noise_samples < 3:
            raise ValueError("At least three noise samples are required")
        for lo, hi in self.protected_delay_intervals_ps:
            if not np.isfinite([lo, hi]).all() or lo > hi:
                raise ValueError("Protected intervals must be finite increasing pairs")


@dataclass
class RepeatQuality:
    unstable_delay_mask: np.ndarray
    spread_od: np.ndarray
    neighbor_spread_od: np.ndarray
    valid_repeats: np.ndarray


@dataclass
class OutlierCorrection:
    od: np.ndarray
    original_od: np.ndarray
    corrected_mask: np.ndarray
    candidate_mask: np.ndarray
    residual_od: np.ndarray
    threshold_od: np.ndarray
    noise_scale_od: np.ndarray
    config: OutlierConfig

    def audit(self):
        return {
            "config": asdict(self.config),
            "corrected_cells": int(self.corrected_mask.sum()),
            "candidate_cells": int(self.candidate_mask.sum()),
            "replacement": "arithmetic mean of original adjacent delay values",
            "missing_value_policy": "preserve NaN; do not bridge gaps",
            "detection_uses_original_values": True,
            "baseline_zero_correction": False,
        }


def detect_unstable_repeats(
    shot_od_blocks,
    wavelengths_nm,
    detection_band_nm=(450.0, 750.0),
    min_spread_od=0.010,
    spread_ratio=2.5,
    neighbor_radius=5,
    min_neighbors=3,
):
    """Flag elevated replicate scatter; this is not a missing-pump detector.

    Each input block contains paired-shot OD, shape (shots, wavelengths), with
    rejected slots represented by NaN. Spread is the median, across the detection
    band, of within-delay sample standard deviation. Compare with the median
    spread at nearby delays. A flag only lowers the temporal detection threshold;
    it never forces replacement of an otherwise smooth point.
    """
    w = np.asarray(wavelengths_nm, dtype=float)
    lo, hi = detection_band_nm
    if (
        w.ndim != 1
        or not np.isfinite(w).all()
        or not np.isfinite([lo, hi]).all()
        or lo >= hi
    ):
        raise ValueError("Expected finite wavelength vector and increasing band")
    band = (w >= lo) & (w <= hi)
    if band.sum() < 3:
        raise ValueError("Detection band needs at least three wavelengths")
    if (
        not np.isfinite([min_spread_od, spread_ratio]).all()
        or min_spread_od <= 0
        or spread_ratio <= 1
    ):
        raise ValueError("Repeat thresholds must be finite and positive; ratio > 1")
    if neighbor_radius < 1 or min_neighbors < 1:
        raise ValueError("Neighbor limits must be positive")
    spread = np.full(len(shot_od_blocks), np.nan)
    repeats = np.zeros(len(shot_od_blocks), dtype=int)
    for i, block in enumerate(shot_od_blocks):
        block = np.asarray(block, dtype=float)
        if block.ndim != 2 or block.shape[1] != len(w):
            raise ValueError("Shot OD block must have shape (shots, wavelengths)")
        finite = np.isfinite(block[:, band]).all(axis=1)
        repeats[i] = int(finite.sum())
        if repeats[i] < 2:
            continue
        spread[i] = float(np.median(np.std(block[finite][:, band], axis=0, ddof=1)))
    baseline = np.full_like(spread, np.nan)
    for j in range(len(spread)):
        neighbors = spread[
            max(0, j - neighbor_radius) : min(len(spread), j + neighbor_radius + 1)
        ].copy()
        neighbors[j - max(0, j - neighbor_radius)] = np.nan
        finite = neighbors[np.isfinite(neighbors)]
        if len(finite) >= min_neighbors:
            baseline[j] = np.median(finite)
    unstable = (
        np.isfinite(spread)
        & np.isfinite(baseline)
        & (spread > np.maximum(min_spread_od, spread_ratio * baseline))
    )
    return RepeatQuality(unstable, spread, baseline, repeats)


def correct_temporal_outliers(delays_ps, od, config=None, unstable_delay_mask=None):
    """Correct isolated excursions independently in every wavelength row.

    Detection requires a local extremum, a return to the neighboring level,
    residual > max(absolute OD threshold, multiplier * residual MAD), enough
    finite noise samples, and finite neighboring points. Interpolation for
    detection respects unequal delay spacing; the requested replacement is an
    unweighted neighboring-point mean. Adjacent candidates are left unchanged.
    First and final points cannot be detected by this two-sided rule.
    """
    config = config or OutlierConfig()
    t = np.asarray(delays_ps, dtype=float)
    original = np.asarray(od, dtype=float).copy()
    if t.ndim != 1 or not np.isfinite(t).all() or not (np.diff(t) > 0).all():
        raise ValueError("Delays must be finite and strictly increasing")
    if original.ndim != 2 or original.shape[1] != len(t):
        raise ValueError("Expected OD shape (wavelengths, delays)")
    original[~np.isfinite(original)] = np.nan
    corrected = original.copy()
    candidate = np.zeros_like(original, dtype=bool)
    changed = candidate.copy()
    residual = np.full_like(original, np.nan)
    threshold = np.full_like(original, np.nan)
    scale = np.full(original.shape[0], np.nan)
    if unstable_delay_mask is None:
        unstable = np.zeros(len(t), dtype=bool)
    else:
        unstable = np.asarray(unstable_delay_mask)
        if unstable.dtype != np.bool_ or unstable.shape != t.shape:
            raise ValueError(
                "Unstable delay mask must be Boolean with one entry per delay"
            )
    if len(t) < config.min_noise_samples + 2:
        return OutlierCorrection(
            corrected, original, changed, candidate, residual, threshold, scale, config
        )
    weight = (t[1:-1] - t[:-2]) / (t[2:] - t[:-2])
    prediction = original[:, :-2] * (1 - weight) + original[:, 2:] * weight
    r = original[:, 1:-1] - prediction
    valid = np.isfinite(r)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        center = np.nanmedian(r, axis=1)
        scale = 1.4826 * np.nanmedian(np.abs(r - center[:, None]), axis=1)
    enough = valid.sum(axis=1) >= config.min_noise_samples
    scale[~enough] = np.nan
    multiplier = np.where(
        unstable[1:-1], config.unstable_sigma_multiplier, config.sigma_multiplier
    )
    neighboring_level = np.maximum(np.abs(original[:, :-2]), np.abs(original[:, 2:]))
    cutoff = np.maximum(
        np.maximum(config.min_excursion_od, scale[:, None] * multiplier),
        config.min_fractional_excursion * neighboring_level,
    )
    left_difference = original[:, 1:-1] - original[:, :-2]
    right_difference = original[:, 1:-1] - original[:, 2:]
    extrema = ((left_difference > 0) & (right_difference > 0)) | (
        (left_difference < 0) & (right_difference < 0)
    )
    returns = np.abs(
        original[:, 2:] - original[:, :-2]
    ) < config.max_neighbor_change_fraction * np.abs(r)
    candidate[:, 1:-1] = (
        valid & enough[:, None] & extrema & returns & (np.abs(r) > cutoff)
    )
    residual[:, 1:-1], threshold[:, 1:-1] = r, cutoff
    for lo, hi in config.protected_delay_intervals_ps:
        candidate[:, (t >= lo) & (t <= hi)] = False
    # Consecutive extrema suggest oscillation/instability rather than one
    # isolated corrupt point. Never cascade detection through replacements.
    adjacent = np.zeros_like(candidate)
    adjacent[:, 1:] |= candidate[:, 1:] & candidate[:, :-1]
    adjacent[:, :-1] |= candidate[:, 1:] & candidate[:, :-1]
    eligible = candidate & ~adjacent
    for j in range(1, len(t) - 1):
        finite_neighbors = np.isfinite(original[:, [j - 1, j + 1]]).all(axis=1)
        keep = eligible[:, j] & finite_neighbors
        corrected[keep, j] = 0.5 * (original[keep, j - 1] + original[keep, j + 1])
        changed[keep, j] = True
    return OutlierCorrection(
        corrected, original, changed, candidate, residual, threshold, scale, config
    )


@dataclass
class MissingPointCorrection:
    od: np.ndarray
    filled_mask: np.ndarray
    method: (
        np.ndarray
    )  # 0 unchanged, 1 two-sided mean, 2 boundary fallback, 3 unavailable
    left_index: np.ndarray
    right_index: np.ndarray


def fill_missing_neighbors(delays_ps, od, edge_policy="two_nearest_mean"):
    """Fill missing OD using adjacent finite measurements without deleting delays.

    An isolated interior gap uses exactly (y[j-1]+y[j+1])/2, including on an
    unequal time grid. For a missing run, the closest original finite points
    bracketing the run are used. At a boundary, two_nearest_mean averages the two
    nearest original finite points; nearest copies one. No finite evidence leaves
    NaN. Filling never uses another invented value as a source.
    """
    t = np.asarray(delays_ps, dtype=float)
    original = np.asarray(od, dtype=float).copy()
    if t.ndim != 1 or not np.isfinite(t).all() or not (np.diff(t) > 0).all():
        raise ValueError("Delays must be finite and strictly increasing")
    if original.ndim != 2 or original.shape[1] != len(t):
        raise ValueError("Expected OD shape (wavelengths, delays)")
    if edge_policy not in ("two_nearest_mean", "nearest", "preserve"):
        raise ValueError("Unknown boundary policy")
    original[~np.isfinite(original)] = np.nan
    result = original.copy()
    filled = np.zeros_like(original, dtype=bool)
    method = np.zeros_like(original, dtype=np.uint8)
    left = np.full(original.shape, -1, dtype=int)
    right = left.copy()
    for row in range(len(original)):
        available = np.flatnonzero(np.isfinite(original[row]))
        for j in np.flatnonzero(~np.isfinite(original[row])):
            earlier = available[available < j]
            later = available[available > j]
            if earlier.size and later.size:
                a, b = int(earlier[-1]), int(later[0])
                result[row, j] = 0.5 * (original[row, a] + original[row, b])
                left[row, j], right[row, j], method[row, j] = a, b, 1
            elif available.size and edge_policy != "preserve":
                ordered = available[
                    np.argsort(np.abs(t[available] - t[j]), kind="stable")
                ]
                a = int(ordered[0])
                b = (
                    int(ordered[1])
                    if edge_policy == "two_nearest_mean" and len(ordered) >= 2
                    else a
                )
                result[row, j] = 0.5 * (original[row, a] + original[row, b])
                left[row, j], right[row, j], method[row, j] = a, b, 2
            else:
                method[row, j] = 3
            filled[row, j] = np.isfinite(result[row, j])
    return MissingPointCorrection(result, filled, method, left, right)
