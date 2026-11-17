"""Compatibility imports for the VD2 Web timing API."""

from DeviceServers.instruments.dg645.vd2_timing import (
    TimingProfile, apply_timing, timing_for_range, verify_timing,
)

__all__ = ["TimingProfile", "apply_timing", "timing_for_range", "verify_timing"]
