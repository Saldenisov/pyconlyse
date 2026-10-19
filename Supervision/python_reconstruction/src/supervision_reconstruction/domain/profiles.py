"""Hardware-free profile-buffer calculation from ``1_SUP_PROFILS XY.vi``.

The Image/IMAQ extraction is deliberately outside this module because its
terminal layout was unresolved by lvkit.  This module starts with the already
extracted row and column samples and reconstructs the evidenced buffering,
integral threshold, and averaging operations.
"""

from dataclasses import dataclass
from typing import Sequence, Tuple


PROFILE_INTEGRAL_THRESHOLD = 1000.0

Profile = Tuple[float, ...]
Buffer = Tuple[Profile, ...]


@dataclass(frozen=True)
class ProfileBuffers:
    """Independent X and Y circular buffers returned by the legacy VI."""

    x: Buffer
    y: Buffer


@dataclass(frozen=True)
class ProfileUpdate:
    """Updated buffers, averaged profiles, and filter decisions."""

    buffers: ProfileBuffers
    profile_x: Profile
    profile_y: Profile
    x_integral: float
    y_integral: float
    x_accepted: bool
    y_accepted: bool
    slot: int


def trapezoidal_integral(values: Sequence[float], dt: float = 1.0) -> float:
    """One-dimensional trapezoidal integration with the VI's visible ``dt=1``."""

    if len(values) < 2:
        return 0.0
    return dt * sum((left + right) / 2.0 for left, right in zip(values, values[1:]))


def _as_profile(values: Sequence[float]) -> Profile:
    return tuple(float(value) for value in values)


def _validate_buffer(buffer: Buffer, average_count: int, profile_length: int) -> None:
    if average_count <= 0:
        raise ValueError("average_count must be positive")
    if len(buffer) != average_count:
        raise ValueError("buffer length must equal average_count")
    if any(len(profile) != profile_length for profile in buffer):
        raise ValueError("all buffered profiles must match the input profile length")


def _mean_profiles(buffer: Buffer, average_count: int) -> Profile:
    if not buffer:
        return ()
    return tuple(
        sum(profile[index] for profile in buffer) / average_count
        for index in range(len(buffer[0]))
    )


def _replace_slot(buffer: Buffer, slot: int, value: Profile, accepted: bool) -> Buffer:
    if not accepted:
        return buffer
    updated = list(buffer)
    updated[slot] = value
    return tuple(updated)


def update_profile_buffers(
    iteration: int,
    average_count: int,
    buffers: ProfileBuffers,
    x_samples: Sequence[float],
    y_samples: Sequence[float],
    threshold: float = PROFILE_INTEGRAL_THRESHOLD,
) -> ProfileUpdate:
    """Reconstruct the profile VI after row/column extraction.

    The quotient/remainder node selects ``iteration % average_count``.  Each
    sample replaces only its own buffer slot when its trapezoidal integral is
    strictly greater than 1000.  Both output sums are always divided by
    ``average_count`` rather than by the number of accepted samples.
    """

    if iteration < 0:
        raise ValueError("iteration must be non-negative")
    x_profile = _as_profile(x_samples)
    y_profile = _as_profile(y_samples)
    _validate_buffer(buffers.x, average_count, len(x_profile))
    _validate_buffer(buffers.y, average_count, len(y_profile))

    x_integral = trapezoidal_integral(x_profile)
    y_integral = trapezoidal_integral(y_profile)
    x_accepted = x_integral > threshold
    y_accepted = y_integral > threshold
    slot = iteration % average_count
    x_buffer = _replace_slot(buffers.x, slot, x_profile, x_accepted)
    y_buffer = _replace_slot(buffers.y, slot, y_profile, y_accepted)
    updated = ProfileBuffers(x=x_buffer, y=y_buffer)
    return ProfileUpdate(
        buffers=updated,
        profile_x=_mean_profiles(x_buffer, average_count),
        profile_y=_mean_profiles(y_buffer, average_count),
        x_integral=x_integral,
        y_integral=y_integral,
        x_accepted=x_accepted,
        y_accepted=y_accepted,
        slot=slot,
    )
