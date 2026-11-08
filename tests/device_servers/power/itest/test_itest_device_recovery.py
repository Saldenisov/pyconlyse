"""Recovery contracts for the iTest Tango adapter without network access."""

from tango import DevState

from DeviceServers.base.general import DS_General
from DeviceServers.base.hardware_lifecycle import (
    HardwareConnectionState,
    InitializationState,
)
from tests.device_servers.base._driver_stubs import scpi_imports

with scpi_imports():
    from DeviceServers.power.iTest.DS_itest_psu import DS_iTest_PSU


class FakeDevice:
    def __init__(self, scpi=None):
        self._scpi = scpi
        self._device_id_internal = 1 if scpi else -1
        self._ids = [1]
        self._slot_count = 1
        self._states = [0]
        self._currents_meas = [0.0]
        self.states = []
        self.lifecycle = []
        self.errors = []
        self.reconnect = None

    def _log_max(self, *_args):
        pass

    def _log_normal(self, *_args):
        pass

    def error(self, message):
        self.errors.append(str(message))

    def push_change_event(self, *_args):
        pass

    def set_state(self, state):
        self.states.append(state)

    def set_hardware_lifecycle(self, connection, initialization, detail):
        self.lifecycle.append((connection, initialization, detail))

    def find_device(self):
        if self.reconnect is not None:
            self._scpi = self.reconnect
            self._device_id_internal = 1


class BrokenSCPI:
    def __init__(self):
        self.closed = False

    def read_all_states(self, _ids):
        raise RuntimeError("transport lost")

    def close(self):
        self.closed = True


def call_status(device):
    return DS_iTest_PSU.get_controller_status_local(device)


def test_uses_base_polled_status_command():
    assert DS_iTest_PSU.get_controller_status is DS_General.get_controller_status


def test_missing_transport_attempts_passive_reconnect():
    device = FakeDevice()
    device.reconnect = object()

    assert call_status(device) == 0
    assert device._scpi is device.reconnect
    assert device.states == []


def test_failed_passive_reconnect_stays_in_fault_for_next_poll():
    device = FakeDevice()

    assert call_status(device) == 1
    assert device._scpi is None
    assert device.states == [DevState.FAULT]


def test_read_failure_discards_transport_and_records_disconnect():
    transport = BrokenSCPI()
    device = FakeDevice(transport)

    assert call_status(device) == 1
    assert transport.closed is True
    assert device._scpi is None
    assert device._device_id_internal == -1
    assert device.states == [DevState.FAULT]
    assert device.lifecycle == [
        (
            HardwareConnectionState.DISCONNECTED,
            InitializationState.NOT_REQUESTED,
            "hardware status read failed: transport lost",
        )
    ]
