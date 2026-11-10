"""Reference reduction for VD2 frames with independent beam-state tags.

No hardware or file I/O. Callers retain the original frames, beam tags, and
exclusion reasons for replay. Image order is never used to infer beam state.
"""
from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class TaggedFrame:
    camera_sequence: int
    accelerator_cycle: int
    beam_on: bool
    image: np.ndarray
    probe_intensity: float | None = None


@dataclass(frozen=True)
class BeamPair:
    absorption: TaggedFrame
    base: TaggedFrame


@dataclass(frozen=True)
class PairedOD:
    od: np.ndarray
    roi_mod: float | None
    # Each item is (ABS camera sequence, BASE camera sequence).
    used: tuple[tuple[int, int], ...]
    unmatched: tuple[int, ...]
    valid_count: np.ndarray


def pair_tagged_frames(frames: Iterable[TaggedFrame]):
    """Group by verified cycle and beam state, reporting incomplete cycles."""
    pairs, incomplete = [], []
    current_cycle = None
    previous_sequence = None
    cycle_frames = []

    def close_cycle():
        if len(cycle_frames) == 2 and cycle_frames[0].beam_on != cycle_frames[1].beam_on:
            first, second = cycle_frames
            pairs.append(BeamPair(first, second) if first.beam_on else BeamPair(second, first))
        elif cycle_frames:
            incomplete.append(current_cycle)

    for frame in frames:
        if type(frame.beam_on) is not bool:
            raise ValueError("Frame requires a verified Boolean beam state")
        if previous_sequence is not None and frame.camera_sequence <= previous_sequence:
            raise ValueError("Camera sequence must increase")
        if current_cycle is not None and frame.accelerator_cycle < current_cycle:
            raise ValueError("Accelerator cycle must increase between pairs")
        if frame.accelerator_cycle != current_cycle:
            close_cycle()
            current_cycle = frame.accelerator_cycle
            cycle_frames.clear()
        cycle_frames.append(frame)
        previous_sequence = frame.camera_sequence
    close_cycle()
    return tuple(pairs), tuple(incomplete)


def _match_base(index, cycles, absorption_probe, base_probe, max_cycle_gap, max_mismatch):
    if not math.isfinite(absorption_probe[index]) or absorption_probe[index] <= 0:
        return None
    begin = np.searchsorted(cycles, cycles[index] - max_cycle_gap)
    end = np.searchsorted(cycles, cycles[index] + max_cycle_gap, side="right")
    eligible = np.arange(begin, end)
    valid = np.isfinite(base_probe[eligible]) & (base_probe[eligible] > 0)
    eligible = eligible[valid]
    if not eligible.size:
        return None
    mismatch = np.abs(np.log(base_probe[eligible]) - math.log(absorption_probe[index]))
    order = np.lexsort((eligible, np.abs(cycles[eligible] - cycles[index]), mismatch))
    best = order[0]
    return int(eligible[best]) if mismatch[best] <= math.log1p(max_mismatch) else None


def reduce_paired_od(
    pairs: Iterable[BeamPair],
    background,
    roi,
    *,
    method="mean_pair_od",
    excluded_cycles=(),
    max_cycle_gap=None,
    max_relative_mismatch=None,
):
    """Reduce verified pairs using a previously measured mean BRUIT image.

    The ROI value is the arithmetic mean of per-pixel OD on the selected mask.
    It is unavailable if any ROI pixel lacks valid inputs. Matched intensity is
    an independent probe metric, e.g. a lamp monitor or pre-beam image region.
    """
    if method not in {"od_of_means", "mean_pair_od", "matched_base"}:
        raise ValueError("Unknown VD2 paired reduction")
    if method == "matched_base" and (
        type(max_cycle_gap) is not int or max_cycle_gap < 0
        or max_relative_mismatch is None or not math.isfinite(max_relative_mismatch)
        or max_relative_mismatch < 0
    ):
        raise ValueError("Matching requires finite intensity and cycle-distance limits")

    background = np.asarray(background, dtype=np.float64)
    roi = np.asarray(roi)
    if background.ndim != 2 or roi.shape != background.shape or roi.dtype != bool or not roi.any():
        raise ValueError("ROI must be a nonempty Boolean mask matching the BRUIT image")
    excluded = set(excluded_cycles)
    selected = []
    previous_cycle = None
    for pair in pairs:
        absorption, base = pair.absorption, pair.base
        cycle = absorption.accelerator_cycle
        if (base.accelerator_cycle != cycle or absorption.beam_on is not True
                or base.beam_on is not False or absorption.camera_sequence == base.camera_sequence
                or (previous_cycle is not None and cycle <= previous_cycle)):
            raise ValueError("Expected ordered and uniquely tagged beam pairs")
        previous_cycle = cycle
        if np.shape(absorption.image) != background.shape or np.shape(base.image) != background.shape:
            raise ValueError("Frame geometry does not match BRUIT")
        if cycle not in excluded:
            selected.append(pair)

    if method == "matched_base":
        cycles = np.asarray([pair.absorption.accelerator_cycle for pair in selected], dtype=np.int64)
        absorption_probe = np.asarray([pair.absorption.probe_intensity for pair in selected], dtype=float)
        base_probe = np.asarray([pair.base.probe_intensity for pair in selected], dtype=float)

    first_sum = np.zeros(background.shape)
    base_sum = np.zeros(background.shape)
    count = np.zeros(background.shape, dtype=np.int64)
    used, unmatched = [], []
    for index, pair in enumerate(selected):
        absorption = pair.absorption
        base_index = index
        if method == "matched_base":
            base_index = _match_base(index, cycles, absorption_probe, base_probe, max_cycle_gap, max_relative_mismatch)
            if base_index is None:
                unmatched.append(absorption.camera_sequence)
                continue
        base = selected[base_index].base
        absorption_counts = np.asarray(absorption.image, dtype=float) - background
        base_counts = np.asarray(base.image, dtype=float) - background
        valid = (np.isfinite(absorption_counts) & np.isfinite(base_counts)
                 & (absorption_counts > 0) & (base_counts > 0))
        if not valid.any():
            unmatched.append(absorption.camera_sequence)
            continue
        used.append((absorption.camera_sequence, base.camera_sequence))
        count[valid] += 1
        if method == "od_of_means":
            first_sum[valid] += absorption_counts[valid]
            base_sum[valid] += base_counts[valid]
        else:
            first_sum[valid] += np.log10(base_counts[valid]) - np.log10(absorption_counts[valid])

    od = np.full(background.shape, np.nan)
    valid = count > 0
    if method == "od_of_means":
        # Both sums use the same subset at each pixel, so the counts cancel.
        od[valid] = np.log10(base_sum[valid]) - np.log10(first_sum[valid])
    else:
        od[valid] = first_sum[valid] / count[valid]
    roi_mod = float(1000 * np.mean(od[roi])) if np.isfinite(od[roi]).all() else None
    return PairedOD(od, roi_mod, tuple(used), tuple(unmatched), count)
