"""Unreleased TRANCON cleaning candidates; native diagram verification pending.

The helper accepts [delay, wavelength] DBL data and returns [wavelength, delay].
The caller composition reproduces CursorKinGraphMove's return transpose.
Its input must already have the SGL precision of get_data_exp's stored map.
"""

import math
import struct
from numbers import Real
from typing import NamedTuple

from .calc_clean_kinetics import calc_clean_kinetics
from .clean_kinetics_sd import clean_kinetics_sd


class ExperimentCleaningResult(NamedTuple):
    data: list[list[float]]
    timedelays: list[float]
    kinetics: list[float]


def _matrix(data):
    if (not isinstance(data, list) or not data or not isinstance(data[0], list)
            or not data[0] or any(not isinstance(row, list) or len(row) != len(data[0]) for row in data)):
        raise ValueError("Candidate requires a nonempty rectangular list of OD rows")
    if any(isinstance(x, bool) or not isinstance(x, Real) for row in data for x in row):
        raise ValueError("Candidate OD entries must be real numeric scalars")


def _pixels(value, size, name):
    if (not isinstance(value, (tuple, list)) or len(value) != 2
            or any(isinstance(x, bool) or not isinstance(x, int) for x in value)
            or not 0 <= value[0] <= value[1] < size):
        raise ValueError(f"{name} must be an ordered inclusive pair of in-range integer pixels")
    return tuple(value)


def candidate(data, kinetics, timedelays, delay_pixels, od_bounds, mode="approx"):
    """Literal helper result; transpose is deliberately retained at this boundary."""
    _matrix(data)
    if (not isinstance(kinetics, list) or len(kinetics) != len(data)
            or any(isinstance(x, bool) or not isinstance(x, Real) for x in kinetics)):
        raise ValueError("Kinetics must have one real numeric entry per delay")
    if (not isinstance(timedelays, list) or len(timedelays) != len(data)
            or any(isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x)
                   for x in timedelays)):
        raise ValueError("Time delays must have one finite real entry per OD row")
    pixels = _pixels(delay_pixels, len(data), "Delay interval")
    if (not isinstance(od_bounds, (tuple, list)) or len(od_bounds) != 2
            or any(isinstance(x, bool) or not isinstance(x, Real) or not math.isfinite(x)
                   for x in od_bounds) or od_bounds[0] > od_bounds[1]):
        raise ValueError("OD bounds must be an ordered finite pair")
    if not isinstance(mode, str) or mode not in {"delete", "approx"}:
        raise ValueError("Clean mode must be delete or approx")
    return clean_kinetics_sd(tdpixels=pixels, bounds=tuple(od_bounds), data=data,
                             kinetics=kinetics, timedelays=list(timedelays),
                             clean_mode=0 if mode == "delete" else 1)


def selection_candidate(data, wavelength_pixels):
    """Calc_clean numeric projection on an already-SGL map.

    At least two columns are required: source node 151 sizes the accumulator
    from column index 1. No implicit DBL-to-SGL rounding is performed.
    """
    _matrix(data)
    if len(data[0]) < 2:
        raise ValueError("Caller candidate requires at least two wavelength columns")
    for row in data:
        for value in row:
            try:
                sgl = struct.unpack("f", struct.pack("f", value))[0]
            except (OverflowError, struct.error):
                raise ValueError("Caller candidate requires OD already represented as SGL") from None
            if not (math.isnan(value) and math.isnan(sgl)) and value != sgl:
                raise ValueError("Caller candidate requires OD already represented as SGL")
    lower, upper = _pixels(wavelength_pixels, len(data[0]), "Wavelength interval")
    return calc_clean_kinetics(data=data, wavelength_min=lower, wavelength_max=upper).kinetics


def experiment_candidate(data, timedelays, wavelength_pixels, delay_pixels, od_bounds, mode="approx"):
    """Pure numeric composition; no preview/apply writes to the experiment class."""
    kinetics = selection_candidate(data, wavelength_pixels)
    cleaned = candidate(data, kinetics, timedelays, delay_pixels, od_bounds, mode)
    return ExperimentCleaningResult([list(row) for row in zip(*cleaned.data_out)],
                                    list(cleaned.timedelays_out), kinetics)
