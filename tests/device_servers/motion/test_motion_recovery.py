import ctypes
import sys
import types
from pathlib import Path


def _install_tango_stub():
    if "tango" in sys.modules and "tango.server" in sys.modules:
        return

    tango = types.ModuleType("tango")
    server = types.ModuleType("tango.server")

    class AttrWriteType:
        READ = 0
        READ_WRITE = 1

    class DevState:
        OFF = 0
        ON = 1
        FAULT = 2
        STANDBY = 3
        MOVING = 4
        RUNNING = 5
        INIT = 6

    class DispLevel:
        OPERATOR = 0
        EXPERT = 1

    def _identity_decorator(*args, **kwargs):
        if args and callable(args[0]) and len(args) == 1 and not kwargs:
            return args[0]

        def decorator(func):
            return func

        return decorator

    def device_property(**kwargs):
        return kwargs.get("default_value")

    class Device:
        def init_device(self):
            return None

        def set_state(self, state):
            self._state = state

        def get_state(self):
            return getattr(self, "_state", DevState.OFF)

        def get_name(self):
            return getattr(self, "_name", "test/device")

        def info_stream(self, *args, **kwargs):
            return None

        def warn_stream(self, *args, **kwargs):
            return None

        def error_stream(self, *args, **kwargs):
            return None

        def debug_stream(self, *args, **kwargs):
            return None

    tango.AttrWriteType = AttrWriteType
    tango.DevFloat = float
    tango.DevState = DevState
    tango.DispLevel = DispLevel
    server.AttrWriteType = AttrWriteType
    server.attribute = _identity_decorator
    server.command = _identity_decorator
    server.device_property = device_property
    server.pipe = _identity_decorator
    server.Device = Device

    sys.modules["tango"] = tango
    sys.modules["tango.server"] = server


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_install_tango_stub()

from DeviceServers.motion.owis import DS_OWIS_PS90 as owis_module
from DeviceServers.motion.standa import DS_Standa_Motor as standa_module


def _make_standa():
    device = standa_module.DS_Standa_Motor()
    device.device_id = "101"
    device.friendly_name = "Standa"
    device._state = standa_module.DevState.ON
    device._name = "standa/test"
    device._device_id_internal = 7
    device._uri = b"uri"
    device._status_check_fault = 0
    device._temperature = None
    device._power_current = 0
    device._power_voltage = 0
    device._power_status = ""
    return device


def _make_owis():
    device = owis_module.DS_OWIS_PS90()
    device.device_id = "owis-1"
    device.friendly_name = "OWIS"
    device._state = owis_module.DevState.ON
    device._name = "owis/test"
    device._device_id_internal = 1
    device._uri = b"uri"
    device._status_check_fault = 0
    device.control_unit_id = 1
    device._delay_lines_parameters = {
        1: {"position": 0.0, "state": owis_module.DevState.ON},
        2: {"position": 0.0, "state": owis_module.DevState.ON},
    }
    return device


def test_standa_status_success_resets_fault_counter(monkeypatch):
    device = _make_standa()

    class Status(ctypes.Structure):
        _fields_ = [
            ("CurT", ctypes.c_int),
            ("Ipwr", ctypes.c_int),
            ("Upwr", ctypes.c_int),
            ("PWRSts", ctypes.c_int),
        ]

    monkeypatch.setattr(standa_module, "status_t", Status)
    monkeypatch.setattr(
        standa_module,
        "lib",
        types.SimpleNamespace(
            get_status=lambda _dev_id, status_ptr: _fill_standa_status(status_ptr)
        ),
    )

    device._status_check_fault = 4
    result = device.get_controller_status_local()

    assert result == 0
    assert device._status_check_fault == 0
    assert device._temperature == 24.5
    assert device._power_current == 12
    assert device._power_voltage == 3.3
    assert device._power_status == device.POWER_STATES[3]


def test_standa_status_failure_triggers_recovery_after_threshold():
    device = _make_standa()
    calls = []

    monkeypatch_status = ctypes.c_int
    standa_module.status_t = monkeypatch_status
    standa_module.lib = types.SimpleNamespace(get_status=lambda *_args, **_kwargs: -1)
    device._attempt_recover_connection = lambda: calls.append(True) or True
    device._status_check_fault = device.recovery_fault_threshold

    result = device.get_controller_status_local()

    assert result == 0
    assert calls == [True]
    assert device._status_check_fault == 0


def _fill_standa_status(status_ptr):
    status = status_ptr._obj
    status.CurT = 245
    status.Ipwr = 12
    status.Upwr = 330
    status.PWRSts = 3
    return standa_module.Result.Ok


def test_owis_status_success_resets_fault_counter():
    device = _make_owis()
    status_calls = []
    position_calls = []

    device._get_serial_number_ps90 = lambda _control_unit: 12345
    device.get_status_axis_local = lambda axis: status_calls.append(axis) or 0
    device.read_position_axis_local = lambda axis: position_calls.append(axis) or 0
    device._status_check_fault = 2

    result = device.get_controller_status_local()

    assert result == 0
    assert device._status_check_fault == 0
    assert status_calls == [1, 2]
    assert position_calls == [1, 2]


def test_owis_status_failure_triggers_recovery_after_threshold():
    device = _make_owis()
    calls = []

    device._get_serial_number_ps90 = lambda _control_unit: -1
    device._attempt_recover_connection = lambda: calls.append(True) or True
    device._status_check_fault = device.recovery_fault_threshold

    result = device.get_controller_status_local()

    assert result == 0
    assert calls == [True]
    assert device._status_check_fault == 0
