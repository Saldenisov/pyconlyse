from DeviceServers.base.hardware_lifecycle import (
    HardwareConnectionState,
    InitializationState,
    lifecycle_value,
)


def test_hardware_lifecycle_values_are_stable_public_strings():
    assert HardwareConnectionState.POWER_OFF.value == "POWER_OFF"
    assert InitializationState.NOT_REQUESTED.value == "NOT_REQUESTED"


def test_hardware_lifecycle_rejects_unknown_values():
    assert (
        lifecycle_value("not-a-state", HardwareConnectionState, HardwareConnectionState.UNKNOWN)
        == "UNKNOWN"
    )
    assert (
        lifecycle_value(None, InitializationState, InitializationState.UNKNOWN)
        == "UNKNOWN"
    )
