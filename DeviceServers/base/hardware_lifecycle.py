"""Shared, transport-agnostic hardware lifecycle vocabulary.

Tango ``DevState`` remains the public compatibility state.  These values carry
the independent facts needed by clients and aggregators: whether hardware can
be reached and whether it was initialised for operation.
"""

from __future__ import annotations

from enum import Enum


class HardwareConnectionState(str, Enum):
    """Physical power/transport condition observed by a device server."""

    UNKNOWN = "UNKNOWN"
    POWER_OFF = "POWER_OFF"
    POWER_STATUS_UNAVAILABLE = "POWER_STATUS_UNAVAILABLE"
    CONNECTING = "CONNECTING"
    DISCONNECTED = "DISCONNECTED"
    CONNECTED = "CONNECTED"
    READY = "READY"


class InitializationState(str, Enum):
    """Readiness of device-specific operational initialisation."""

    UNKNOWN = "UNKNOWN"
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


def lifecycle_value(value, enum_type, default):
    """Return a stable public value without allowing arbitrary strings."""
    try:
        return enum_type(value).value
    except (TypeError, ValueError):
        return default.value
