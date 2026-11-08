"""Shot-level correction for legacy direct-line RAW/ZIP and Pyconlyse arrays.

Only NumPy and the Python standard library are required. No web framework,
hardware access, file mutation, interpolation, or intensity clipping is used.
"""

import io
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import BinaryIO, Optional, Sequence, Tuple, Union
from zipfile import ZipFile

import numpy as np

RAW_GROUPS = ("BG1", "Ir1", "Is1", "BG2", "Ir2", "Is2")
DISK_TO_CANONICAL = (0, 2, 3, 1, 4, 5)


@dataclass(frozen=True)
class CorrectionConfig:
    detection_band_nm: Tuple[float, float] = (450.0, 750.0)
    min_signal_counts: float = 50.0
    averaging: str = "mean_od"
    ratio_policy: str = "legacy_absolute"
    background_mode: str = "detector"

    def __post_init__(self):
        lo, hi = self.detection_band_nm
        if not np.isfinite([lo, hi]).all() or lo >= hi:
            raise ValueError("detection_band_nm must be a finite increasing pair")
        if not np.isfinite(self.min_signal_counts) or self.min_signal_counts < 0:
            raise ValueError("min_signal_counts must be finite and non-negative")
        if self.averaging not in ("mean_od", "od_from_mean_spectra"):
            raise ValueError("Unknown averaging mode")
        if self.ratio_policy not in ("legacy_absolute", "positive"):
            raise ValueError("Unknown ratio policy")
        if self.background_mode not in ("detector", "state"):
            raise ValueError("Unknown background mode")


@dataclass
class RawScan:
    wavelengths_nm: np.ndarray
    delays_ps: np.ndarray
    blocks: Tuple[np.ndarray, ...]  # each block: (6, shots, wavelengths)
    source_name: str = ""


@dataclass
class BlockCorrection:
    od: np.ndarray
    shot_od: np.ndarray
    valid_shots: np.ndarray
    reasons: Tuple[Tuple[str, ...], ...]
    signal_counts: np.ndarray  # shot, four corrected channels
    pixel_counts: np.ndarray

    @property
    def valid_shot_count(self):
        return int(self.valid_shots.sum())


@dataclass(frozen=True)
class PairedOutlierConfig:
    detection_band_nm: Tuple[float, float] = (450.0, 750.0)
    min_excursion_od: float = 0.020
    sigma_multiplier: float = 6.0
    min_spectral_support: float = 0.60
    min_good_repeats: int = 3

    def __post_init__(self):
        lo, hi = self.detection_band_nm
        if not np.isfinite([lo, hi]).all() or lo >= hi:
            raise ValueError("Paired outlier band must be finite and increasing")
        if (
            not np.isfinite([self.min_excursion_od, self.sigma_multiplier]).all()
            or min(self.min_excursion_od, self.sigma_multiplier) <= 0
        ):
            raise ValueError("Paired outlier thresholds must be finite and positive")
        if not 0 < self.min_spectral_support <= 1 or self.min_good_repeats < 3:
            raise ValueError(
                "Require spectral support (0,1] and at least three agreeing repeats"
            )


@dataclass
class PairedOutlierDetection:
    excluded_shots: np.ndarray
    spectral_support: np.ndarray
    eligible: bool


def detect_paired_od_outliers(block: BlockCorrection, wavelengths_nm, config=None):
    """Identify finite paired-OD outliers only against a stable repeat majority.

    A slot is rejected only if it exceeds both 0.020 OD and six robust scales
    at >=60% of the broad detection band. At least three good repeats and a
    strict majority must remain. Two-shot scans cannot establish a consensus.
    These are empirical OD outliers, not verified missing laser pulses.
    """
    config = config or PairedOutlierConfig()
    w = np.asarray(wavelengths_nm, dtype=float)
    if w.ndim != 1 or not np.isfinite(w).all() or block.shot_od.shape[1] != len(w):
        raise ValueError("Wavelength vector must match paired-shot OD")
    lo, hi = config.detection_band_nm
    band = (w >= lo) & (w <= hi)
    if band.sum() < 3:
        raise ValueError("Paired outlier band needs at least three wavelengths")
    rejected = np.zeros(len(block.valid_shots), dtype=bool)
    support = np.zeros(len(block.valid_shots), dtype=float)
    indices = np.flatnonzero(
        block.valid_shots & np.isfinite(block.shot_od[:, band]).all(axis=1)
    )
    if len(indices) < config.min_good_repeats + 1:
        return PairedOutlierDetection(rejected, support, False)
    values = block.shot_od[indices][:, band]
    center = np.median(values, axis=0)
    deviations = np.abs(values - center)
    scale = 1.4826 * np.median(deviations, axis=0)
    cut = np.maximum(config.min_excursion_od, config.sigma_multiplier * scale)
    support[indices] = np.mean(deviations > cut, axis=1)
    proposed = support[indices] >= config.min_spectral_support
    remaining = len(indices) - int(proposed.sum())
    if remaining >= config.min_good_repeats and remaining > len(indices) / 2:
        rejected[indices[proposed]] = True
    return PairedOutlierDetection(rejected, support, True)


@dataclass
class ScanCorrection:
    wavelengths_nm: np.ndarray
    delays_ps: np.ndarray
    od: np.ndarray  # wavelength, delay; failed delays remain NaN
    valid_shot_counts: np.ndarray
    pixel_counts: np.ndarray
    blocks: Tuple[BlockCorrection, ...]
    config: CorrectionConfig

    def to_payload(self):
        """Web-ready payload: unavailable OD values are JSON null, never NaN."""
        values = self.od.astype(object)
        values[~np.isfinite(self.od)] = None
        return {
            "wavelength_nm": self.wavelengths_nm.tolist(),
            "delay_ps": self.delays_ps.tolist(),
            "od": values.tolist(),
            "od_orientation": "wavelength_by_delay",
            "valid_shot_counts": self.valid_shot_counts.tolist(),
            "pixel_counts": self.pixel_counts.tolist(),
            "audit": self.audit(),
        }

    def audit(self):
        return {
            "config": asdict(self.config),
            "raw_group_order": list(RAW_GROUPS),
            "delays": [
                {
                    "delay_index_zero_based": i,
                    "delay_ps": float(delay),
                    "stored_shots": len(block.valid_shots),
                    "valid_shots": block.valid_shot_count,
                    "rejected_shots_one_based": (
                        np.flatnonzero(~block.valid_shots) + 1
                    ).tolist(),
                    "rejection_reasons": [list(x) for x in block.reasons],
                    "status": "unrecoverable"
                    if block.valid_shot_count == 0
                    else "reduced_shot_count"
                    if not block.valid_shots.all()
                    else "complete",
                }
                for i, (delay, block) in enumerate(zip(self.delays_ps, self.blocks))
            ],
        }


def parse_legacy_raw(payload: Union[str, bytes], source_name="") -> RawScan:
    """Parse S_delay/E_ blocks; permit different shot counts between delays.

    Disk group order is BG_reference, BG_sample, reference_off, sample_off,
    reference_on, sample_on. Rows are grouped by channel, not interleaved by shot.
    Numeric spectra outside a delay block and incomplete blocks are errors.
    """
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8-sig")
    lines = payload.lstrip("\ufeff").splitlines()
    if not lines:
        raise ValueError("Empty RAW file")

    def numeric(line, number):
        try:
            return np.asarray([float(x) for x in line.split()], dtype=np.float64)
        except ValueError as exc:
            raise ValueError("Non-numeric RAW row at line %d" % number) from exc

    wavelengths = numeric(lines[0], 1)
    if (
        wavelengths.size == 0
        or not np.isfinite(wavelengths).all()
        or not (np.diff(wavelengths) > 0).all()
    ):
        raise ValueError("RAW wavelengths must be finite and strictly increasing")
    delay, rows, blocks, delays = None, [], [], []
    for number, text in enumerate(lines[1:], 2):
        text = text.strip()
        if not text:
            continue
        if text.startswith("S_"):
            if delay is not None:
                raise ValueError("Nested delay block at line %d" % number)
            delay = float(text[2:])
            if not np.isfinite(delay):
                raise ValueError("Non-finite RAW delay")
            rows = []
        elif text == "E_":
            if delay is None or not rows or len(rows) % 6:
                raise ValueError("Incomplete six-channel block at line %d" % number)
            disk = np.asarray(rows).reshape(6, len(rows) // 6, wavelengths.size)
            blocks.append(disk[list(DISK_TO_CANONICAL)].copy())
            delays.append(delay)
            delay, rows = None, []
        else:
            if delay is None:
                raise ValueError("Spectrum outside delay block at line %d" % number)
            row = numeric(text, number)
            if row.size != wavelengths.size:
                raise ValueError("RAW spectrum width mismatch at line %d" % number)
            rows.append(row)
    if delay is not None:
        raise ValueError("Unclosed RAW delay block")
    if not blocks:
        raise ValueError("No RAW delay blocks")
    return RawScan(wavelengths, np.asarray(delays), tuple(blocks), source_name)


def load_legacy_zip(
    source: Union[str, Path, bytes, BinaryIO], raw_member=None
) -> RawScan:
    """Accept a path or uploaded ZIP bytes/stream; do not extract archive files."""
    stream = io.BytesIO(source) if isinstance(source, bytes) else source
    with ZipFile(stream) as archive:
        candidates = [x for x in archive.namelist() if x.lower().endswith(".raw")]
        if raw_member is None:
            if len(candidates) != 1:
                raise ValueError(
                    "Specify raw_member when ZIP does not contain exactly one RAW file"
                )
            raw_member = candidates[0]
        if raw_member not in candidates:
            raise ValueError("Selected RAW member does not exist")
        return parse_legacy_raw(archive.read(raw_member), source_name=raw_member)


def _corrected_signals(raw, background_mode):
    bg1, ir1, is1, bg2, ir2, is2 = raw
    if background_mode == "detector":
        # The September legacy files use one background per detector.
        return np.asarray([ir1 - bg1, is1 - bg2, ir2 - bg1, is2 - bg2])
    # Explicit adapter for a producer with one shared background per pulse state.
    return np.asarray([ir1 - bg1, is1 - bg1, ir2 - bg2, is2 - bg2])


def _optical_density(signals, ratio_policy):
    r_off, s_off, r_on, s_on = signals
    valid = np.isfinite(signals).all(axis=0) & (signals != 0).all(axis=0)
    if ratio_policy == "positive":
        valid &= (signals > 0).all(axis=0)
    od = np.full(r_off.shape, np.nan)
    # Sum of logarithms avoids overflow/underflow of the intermediate ratio.
    with np.errstate(divide="ignore", invalid="ignore"):
        value = (
            np.log10(np.abs(s_off))
            - np.log10(np.abs(r_off))
            - np.log10(np.abs(s_on))
            + np.log10(np.abs(r_on))
        )
    valid &= np.isfinite(value)
    od[valid] = value[valid]
    return od


def correct_block(
    raw,
    wavelengths_nm,
    config=None,
    pulse_present=None,
    excluded_shots=None,
    exclusion_reason="caller_excluded",
) -> BlockCorrection:
    """Reject a whole paired shot before averaging; never replace it with zero.

    Input group order is RAW_GROUPS. pulse_present, when available, is a Boolean
    vector supplied by the acquisition pulse monitor. Detector spectra alone
    cannot identify a missing pump pulse when the probe remains normal.
    """
    config = config or CorrectionConfig()
    raw = np.asarray(raw, dtype=np.float64)  # avoids unsigned subtraction
    wavelengths = np.asarray(wavelengths_nm, dtype=np.float64)
    if (
        raw.ndim != 3
        or raw.shape[0] != 6
        or raw.shape[2] != wavelengths.size
        or raw.shape[1] < 1
    ):
        raise ValueError("Expected raw shape (6, shots, wavelengths)")
    if wavelengths.ndim != 1 or not np.isfinite(wavelengths).all():
        raise ValueError("Expected a finite wavelength vector")
    lo, hi = config.detection_band_nm
    band = (wavelengths >= lo) & (wavelengths <= hi)
    if band.sum() < 3:
        raise ValueError("Detection band must contain at least three pixels")
    signals = _corrected_signals(raw, config.background_mode)
    # Use a broad band to distinguish absent probe from legitimate near-zero OD.
    # Median is not a criterion for transient amplitude or spectral outliers.
    finite_shots = np.isfinite(raw).all(axis=(0, 2))
    strength = np.full((raw.shape[1], 4), np.nan)
    strength[finite_shots] = np.median(
        signals[:, finite_shots, :][:, :, band], axis=2
    ).T
    empty = (raw == 0).all(axis=(0, 2))
    reasons = [[] for _ in range(raw.shape[1])]
    channel_names = ("reference_off", "sample_off", "reference_on", "sample_on")
    if pulse_present is not None:
        pulse_present = np.asarray(pulse_present)
        if pulse_present.dtype != np.bool_ or pulse_present.shape != (raw.shape[1],):
            raise ValueError(
                "pulse_present must be a Boolean vector with one entry per shot"
            )
    if excluded_shots is not None:
        excluded_shots = np.asarray(excluded_shots)
        if excluded_shots.dtype != np.bool_ or excluded_shots.shape != (raw.shape[1],):
            raise ValueError(
                "excluded_shots must be a Boolean vector with one entry per shot"
            )
        if not isinstance(exclusion_reason, str) or not exclusion_reason:
            raise ValueError("Exclusion reason must be a nonempty string")
    for shot in range(raw.shape[1]):
        if not finite_shots[shot]:
            reasons[shot].append("nonfinite_raw")
        elif empty[shot]:
            reasons[shot].append("zero_filled_slot")
        else:
            reasons[shot].extend(
                "low_signal:" + name
                for name, value in zip(channel_names, strength[shot])
                if value <= config.min_signal_counts
            )
        if pulse_present is not None and not pulse_present[shot]:
            reasons[shot].append("pulse_monitor_absent")
        if excluded_shots is not None and excluded_shots[shot]:
            reasons[shot].append(exclusion_reason)
    keep = np.asarray([not x for x in reasons], dtype=bool)
    shot_od = np.full((raw.shape[1], wavelengths.size), np.nan)
    if keep.any():
        shot_od[keep] = _optical_density(signals[:, keep, :], config.ratio_policy)
    pixel_counts = np.isfinite(shot_od).sum(axis=0).astype(np.int32)
    od = np.full(wavelengths.size, np.nan)
    if config.averaging == "mean_od":
        np.divide(
            np.where(np.isfinite(shot_od), shot_od, 0.0).sum(axis=0),
            pixel_counts,
            out=od,
            where=pixel_counts > 0,
        )
    elif keep.any():
        # Use the same paired subset at each pixel for all four channels.
        good_pixels = np.isfinite(shot_od[keep])
        sums = np.where(good_pixels[None, :, :], signals[:, keep, :], 0.0).sum(axis=1)
        means = np.full(sums.shape, np.nan)
        np.divide(
            sums, pixel_counts[None, :], out=means, where=pixel_counts[None, :] > 0
        )
        od = _optical_density(means, config.ratio_policy)
    return BlockCorrection(
        od, shot_od, keep, tuple(tuple(x) for x in reasons), strength, pixel_counts
    )


def correct_scan(
    scan: RawScan, config=None, pulse_present: Optional[Sequence[np.ndarray]] = None
) -> ScanCorrection:
    config = config or CorrectionConfig()
    if len(scan.blocks) != len(scan.delays_ps):
        raise ValueError("Number of RAW blocks does not match delays")
    if pulse_present is not None and len(pulse_present) != len(scan.blocks):
        raise ValueError("Number of pulse monitor vectors does not match delays")
    blocks = tuple(
        correct_block(
            raw,
            scan.wavelengths_nm,
            config,
            None if pulse_present is None else pulse_present[i],
        )
        for i, raw in enumerate(scan.blocks)
    )
    return ScanCorrection(
        scan.wavelengths_nm.copy(),
        scan.delays_ps.copy(),
        np.stack([x.od for x in blocks], axis=1),
        np.asarray([x.valid_shot_count for x in blocks], dtype=np.int32),
        np.stack([x.pixel_counts for x in blocks], axis=1),
        blocks,
        config,
    )


def write_dat(path, wavelengths_nm, delays_ps, od):
    """Write the original DAT orientation: wavelength rows, delay columns."""
    wavelengths, delays, od = (
        np.asarray(wavelengths_nm),
        np.asarray(delays_ps),
        np.asarray(od),
    )
    if od.shape != (len(wavelengths), len(delays)):
        raise ValueError("OD shape does not match DAT axes")
    if np.isinf(od).any():
        raise ValueError("Infinity cannot be exported as a corrected measurement")
    matrix = np.empty((len(wavelengths) + 1, len(delays) + 1))
    matrix[0, 0], matrix[0, 1:], matrix[1:, 0], matrix[1:, 1:] = (
        0.0,
        delays,
        wavelengths,
        od,
    )
    np.savetxt(path, matrix, delimiter="\t", fmt="%.10g")
