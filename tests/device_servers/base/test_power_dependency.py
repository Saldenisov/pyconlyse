from pathlib import Path
from types import SimpleNamespace

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(BASE_DIR))

from _test_support import general_module
from DeviceServers.base.power_dependency import read_power_dependency_state


class PowerDummy(general_module.DS_General):
    def __init__(self):
        self._state = general_module.DevState.OFF
        self._name = "test/power-dummy"
        self.device_id = "power-dummy"
        self.friendly_name = "PowerDummy"
        self.always_on = 0
        self.archive_enabled = 0
        self.power_dependency_device = "manip/test/PDU"
        self.power_dependency_output_id = 2
        self.power_dependency_auto_probe = 1
        self.power_on_settle_seconds = 0.0
        self.power_dependency_poll_interval_s = 60.0
        self.find_calls = 0
        self.probe_calls = 0
        self.turn_on_calls = 0
        self.release_calls = 0

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "power dummy"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self.find_calls += 1
        self._device_id_internal = 1
        self._uri = b"power://dummy"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        self.turn_on_calls += 1
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0

    def release_power_dependency_local(self):
        self.release_calls += 1

    def probe_powered_hardware(self):
        self.probe_calls += 1
        self._device_id_internal = 1
        self._uri = b"power://dummy"
        return 0


def test_power_reader_uses_only_pdu_attribute_reads():
    calls = []

    class PduProxy:
        def set_timeout_millis(self, value):
            calls.append(("timeout", value))

        def read_attribute(self, name):
            calls.append(("read", name))
            return SimpleNamespace(value={"ids": [1, 2], "states": [0, 1]}[name])

    state = read_power_dependency_state("manip/test/PDU", 2, lambda _: PduProxy())

    assert state.configured is True
    assert state.powered is True
    assert calls == [("timeout", 3000), ("read", "ids"), ("read", "states")]


def test_unpowered_dependency_skips_discovery_and_active_turn_on(monkeypatch):
    device = PowerDummy()
    state = general_module.PowerDependencyState(
        True, False, "power PDU manip/test/PDU output 2 is OFF"
    )
    monkeypatch.setattr(device, "_read_power_dependency_state", lambda: state)

    device.init_device()
    device.turn_on()

    assert device.find_calls == 0
    assert device.turn_on_calls == 0
    assert device.get_state() == general_module.DevState.OFF
    assert device.release_calls == 1
    assert "intentionally skipped" in device.power_dependency_status()
    device.delete_device()


def test_power_restore_waits_then_runs_safe_probe_without_turn_on(monkeypatch):
    device = PowerDummy()
    off = general_module.PowerDependencyState(True, False, "PDU output is OFF")
    on = general_module.PowerDependencyState(True, True, "PDU output is ON")
    monkeypatch.setattr(device, "_read_power_dependency_state", lambda: on)

    device._power_dependency_observed = False
    device._power_dependency_state = off
    device._power_probe_pending = False
    device._power_probe_due_at = 0.0
    device._power_dependency_status = ""
    device._lifecycle_lock = __import__("threading").RLock()

    device._apply_power_dependency_state(off)
    device._apply_power_dependency_state(on)
    device._run_power_dependency_probe_if_due()

    assert device.probe_calls == 1
    assert device.turn_on_calls == 0
    assert device.get_state() == general_module.DevState.STANDBY
    assert "safe probe succeeded" in device.power_dependency_status()


def test_unavailable_pdu_faults_once_without_hardware_access(monkeypatch):
    device = PowerDummy()
    state = general_module.PowerDependencyState(
        True, None, "cannot read power PDU manip/test/PDU output 2: timeout"
    )
    monkeypatch.setattr(device, "_read_power_dependency_state", lambda: state)

    device.init_device()

    assert device.find_calls == 0
    assert device.turn_on_calls == 0
    assert device.get_state() == general_module.DevState.FAULT
    assert "Power dependency is unavailable" in device.power_dependency_status()
    device.delete_device()
