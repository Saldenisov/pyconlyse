from __future__ import division

import math


def channel_last_samples(samples_by_channel, expected_channels, expected_samples):
    """Select the last raw value per finite channel block; never average.

    The block shape and every raw value are checked before returning any
    selected values. This changes only the Python projection, not acquisition
    timing or trigger setup. It is an explicit policy, not the VI mean.
    """
    if (type(expected_channels) is not int or expected_channels <= 0
            or type(expected_samples) is not int or expected_samples <= 0):
        raise ValueError("Exact positive channel and sample counts required")
    if (not isinstance(samples_by_channel, (list, tuple))
            or len(samples_by_channel) != expected_channels):
        raise ValueError("Complete analog channel block required")
    result = []
    for row in samples_by_channel:
        if not isinstance(row, (list, tuple)) or len(row) != expected_samples:
            raise ValueError("Complete finite samples required for every channel")
        for value in row:
            try:
                valid = type(value) in (int, float) and math.isfinite(value)
            except (OverflowError, ValueError):
                valid = False
            if not valid:
                raise ValueError("Finite numeric raw analog samples required")
        result.append(float(row[-1]))
    return result


def channel_means(samples_by_channel, expected_channels=None, expected_samples=None):
    rows = list(samples_by_channel)
    if expected_channels is not None and len(rows) != expected_channels:
        raise ValueError("expected {0} channels, got {1}".format(expected_channels, len(rows)))
    result = []
    for index, row in enumerate(rows):
        values = list(row)
        if expected_samples is not None and len(values) != expected_samples:
            raise ValueError(
                "channel {0}: expected {1} samples, got {2}".format(
                    index, expected_samples, len(values)
                )
            )
        if not values:
            raise ValueError("channel {0} has no samples".format(index))
        result.append(sum(float(value) for value in values) / len(values))
    return result


def linear_calibration(value, scale, offset):
    return float(value) * float(scale) + float(offset)


def dephaser_voltage(value):
    x = float(value)
    return (8e-9) * x ** 4 - (7e-7) * x ** 3 - (3e-5) * x ** 2 - 0.0181 * x + 2.1775


def attenuator_voltage(attenuation_db):
    x = float(attenuation_db)
    acos_argument = 10 ** (-x / 20.0)
    if acos_argument < -1.0 or acos_argument > 1.0:
        raise ValueError("attenuator acos argument outside [-1, 1]")
    angle = 57.3 * math.acos(acos_argument)
    return (-4e-6) * angle ** 3 + 0.0006 * angle ** 2 - 0.0624 * angle + 3.8587


def microseconds_to_20mhz_ticks(value_us):
    value = float(value_us)
    if not math.isfinite(value) or value < 0:
        raise ValueError("microseconds must be finite and non-negative")
    ticks = value * 20.0
    rounded = int(round(ticks))
    if abs(ticks - rounded) > 1e-9:
        raise ValueError("microseconds must resolve to an integer 20 MHz tick count")
    return rounded
