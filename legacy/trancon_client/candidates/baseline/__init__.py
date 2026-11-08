"""Unreleased BG_corrSD Aver candidate; do not use for Web V0 treatment.

The source's indexed background tunnel subtracts one scalar per OD row and
can truncate the delay axis. Native screenshots must resolve this before
choosing whether to preserve or correct that behavior.
"""

from numbers import Real

from .bg_corrsd import bg_corrsd


def candidate(data, lower_pixel, upper_pixel):
    """Constrain source input domain without changing its numeric wiring."""
    if (not isinstance(data, list) or not data or not isinstance(data[0], list)
            or not data[0] or any(not isinstance(row, list) or len(row) != len(data[0]) for row in data)):
        raise ValueError("Candidate requires a nonempty rectangular list of OD rows")
    if any(isinstance(value, bool) or not isinstance(value, Real) for row in data for value in row):
        raise ValueError("Candidate OD entries must be real numeric scalars")
    if any(isinstance(index, bool) or not isinstance(index, int)
           or not 0 <= index < len(data) for index in (lower_pixel, upper_pixel)):
        raise ValueError("Delay pixels must be in-range integer indices")
    if lower_pixel == upper_pixel == len(data) - 1:
        raise ValueError("Equal last-pixel bounds require native edge qualification")
    return bg_corrsd(data=data, lower_pixel=lower_pixel, upper_pixel=upper_pixel,
                     baseline_mode=0).data_corrected
