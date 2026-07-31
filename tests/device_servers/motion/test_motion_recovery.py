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
    tango.DeviceProxy = object
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
from DeviceServers.motion.owis import DS_OWIS_Aggregator as aggregator_module
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


def test_standa_usb_loss_schedules_passive_recovery_after_threshold():
    device = _make_standa()
    device.usb_status_failure_threshold = 1
    standa_module.lib = types.SimpleNamespace(get_status=lambda *_args, **_kwargs: -1)

    result = device.get_controller_status_local()

    assert "USB connection lost" in result
    assert device.get_state() == standa_module.DevState.FAULT
    assert device._device_id_internal == -1
    assert device._standa_handle_open is False
    assert device._next_fault_recovery_at > 0


def test_standa_transient_usb_failure_does_not_fault_or_reconnect():
    device = _make_standa()
    device.usb_status_failure_threshold = 3
    device._standa_handle_open = True
    calls = []
    standa_module.lib = types.SimpleNamespace(get_status=lambda *_args, **_kwargs: -1)
    device._attempt_recover_connection = lambda: calls.append(True) or True

    result = device.get_controller_status_local()

    assert result == 0
    assert device.get_state() == standa_module.DevState.ON
    assert device._status_check_fault == 1
    assert calls == []


def test_standa_busy_shared_transport_skips_status_sample():
    device = _make_standa()
    device._standa_handle_open = True

    class BusyLock:
        def __enter__(self):
            raise standa_module.StandaTransportBusyError("held by another server")

        def __exit__(self, *_args):
            return False

    device._transport_lock = lambda: BusyLock()

    assert device.get_controller_status_local() == 0
    assert device._status_check_fault == 0
    assert device.get_state() == standa_module.DevState.ON


def test_standa_recovery_discovers_transport_without_axis_initialisation():
    device = _make_standa()
    calls = []

    def discover():
        calls.append("find")
        device._device_id_internal = 7
        device._uri = b"uri"

    device.find_device = discover
    device.turn_on_local = lambda: (_ for _ in ()).throw(
        AssertionError("recovery must not initialise or stop an axis")
    )

    assert device._attempt_recover_connection() is True
    assert calls == ["find"]
    assert device.get_state() == standa_module.DevState.STANDBY
    assert device._status_check_fault == 0


def test_standa_usb_loss_during_motion_blocks_automatic_recovery():
    device = _make_standa()
    device._standa_handle_open = True
    device.usb_status_failure_threshold = 1
    device.set_state(standa_module.DevState.MOVING)
    calls = []
    standa_module.lib = types.SimpleNamespace(get_status=lambda *_args, **_kwargs: -1)
    device.find_device = lambda: calls.append("find")

    result = device.get_controller_status_local()

    assert "during motion" in result
    assert device.get_state() == standa_module.DevState.FAULT
    assert device._standa_auto_recovery_blocked is True
    assert device._next_fault_recovery_at == float("inf")
    assert device._attempt_recover_connection() is False
    assert calls == []


def test_standa_discovery_closes_probe_handle_without_turning_axis_off():
    device = _make_standa()
    device.set_state(standa_module.DevState.OFF)
    device._standa_handle_open = False
    closed = []

    def get_serial(_handle, serial_ptr):
        serial_ptr._obj.value = int(device.device_id)
        return standa_module.Result.Ok

    standa_module.lib = types.SimpleNamespace(
        set_bindy_key=lambda _path: None,
        enumerate_devices=lambda *_args: object(),
        get_device_count=lambda _enum: 1,
        get_device_name=lambda _enum, _index: b"xi-net://controller",
        open_device=lambda _uri: 7,
        get_serial_number=get_serial,
        close_device=lambda _handle: closed.append(True) or 0,
    )

    device.find_device()

    assert device._uri == b"xi-net://controller"
    assert device._device_id_internal == 0
    assert device._standa_handle_open is False
    assert closed == [True]


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


def test_owis_recovery_probes_transport_without_axis_initialisation():
    device = _make_owis()
    calls = []
    device.recovery_connect_attempts = 1
    device.recovery_attempt_delay_seconds = 0.1
    device._disconnect_ps90 = lambda _control_unit: calls.append("disconnect") or (0, "")

    def find_device():
        calls.append("find")
        device._device_id_internal = 2

    device.find_device = find_device
    device.turn_on_local = lambda: (_ for _ in ()).throw(AssertionError("must not initialise axes"))

    assert device._attempt_recover_connection() is True
    assert calls == ["disconnect", "find"]
    assert device.get_state() == owis_module.DevState.STANDBY


def test_owis_unpowered_controller_is_off_without_connection_or_recovery():
    device = _make_owis()
    device._read_power_dependency_state = lambda: (
        False,
        "power PDU manip/V0/PDU_VO output 2",
    )
    device.find_device = lambda: (_ for _ in ()).throw(AssertionError("must not connect"))
    device._disconnect_ps90 = lambda *_args: (_ for _ in ()).throw(
        AssertionError("must not recover")
    )

    result = device.turn_on_local()

    assert "power is OFF" in result
    assert device.get_state() == owis_module.DevState.OFF
    assert "PDU_VO output 2" in device._controller_connection_status
    assert device.hardware_connection_state() == "POWER_OFF"
    assert device.initialization_state() == "NOT_REQUESTED"
    assert device._attempt_recover_connection() is False


def test_owis_reads_configured_netio_power_dependency(monkeypatch):
    device = _make_owis()
    device.power_dependency_device = "manip/V0/PDU_VO"
    device.power_dependency_output_id = 2

    class Attribute:
        def __init__(self, value):
            self.value = value

    class PduProxy:
        def set_timeout_millis(self, _timeout):
            return None

        def state(self):
            return owis_module.DevState.ON

        def read_attribute(self, name):
            return Attribute({"ids": [1, 2, 3], "states": [1, 0, 1]}[name])

    monkeypatch.setattr(owis_module, "DeviceProxy", lambda _name: PduProxy())

    powered, detail = device._read_power_dependency_state()

    assert powered is False
    assert detail == "power PDU manip/V0/PDU_VO output 2"


def test_owis_aggregator_does_not_activate_faulted_backend_during_health_check(
    monkeypatch,
):
    commands = []

    class BackendProxy:
        def set_timeout_millis(self, _timeout):
            return None

        def ping(self):
            return None

        def state(self):
            return aggregator_module.DevState.FAULT

        def command_inout(self, command):
            commands.append(command)

        def read_attribute(self, name):
            assert name == "controller_connection_status"
            return types.SimpleNamespace(
                value="OWIS controller power is OFF (power PDU manip/V0/PDU_VO output 2)"
            )

    device = types.SimpleNamespace(
        backend_timeout_ms=3000,
        _backend_proxies={"three": None},
        _backend_alive={"three": False},
        _backend_reason={"three": ""},
        device_name="OWIS Aggregator",
        _backend_name=lambda _kind: "manip/general/DS_OWIS_PS90_IP",
        info=lambda *_args, **_kwargs: None,
    )
    device._backend_is_ready = aggregator_module.DS_OWIS_Aggregator._backend_is_ready
    device._backend_connection_detail = lambda proxy: (
        aggregator_module.DS_OWIS_Aggregator._backend_connection_detail(device, proxy)
    )
    monkeypatch.setattr(aggregator_module, "DeviceProxy", lambda _name: BackendProxy())

    ok, reason = aggregator_module.DS_OWIS_Aggregator._connect_backend(
        device, "three"
    )

    assert ok is False
    assert "may be unpowered" in reason
    assert "power is OFF" in reason
    assert commands == []


def test_owis_aggregator_keeps_read_only_recovery_polling_when_off():
    allowed_states = aggregator_module.DS_OWIS_Aggregator.RULES[
        "get_controller_status"
    ]
    assert aggregator_module.DevState.OFF in allowed_states
    assert aggregator_module.DevState.STANDBY in allowed_states


def test_owis_aggregator_marks_unpowered_backend_as_hardware_power_off():
    state = {"value": aggregator_module.DevState.INIT}
    lifecycle = {}
    device = types.SimpleNamespace(
        _device_id_internal=-1,
        _uri=b"",
        _refresh_backends=lambda **_kwargs: False,
        _unpowered_backend_reason=lambda: "backend three power PDU output 2 is OFF",
        _set_off_for_unpowered_backend=lambda _reason: None,
        set_state=lambda value: state.__setitem__("value", value),
        set_hardware_lifecycle=lambda connection, initialization, detail: lifecycle.update(
            connection=connection.value,
            initialization=initialization.value,
            detail=detail,
        ),
        check_func_allowance=lambda _func: 1,
    )
    device.find_device = lambda: None

    aggregator_module.DS_OWIS_Aggregator.find_device(device)

    assert state["value"] == aggregator_module.DevState.INIT
    assert lifecycle == {
        "connection": "POWER_OFF",
        "initialization": "NOT_REQUESTED",
        "detail": "backend three power PDU output 2 is OFF",
    }


def test_owis_aggregator_treats_unpowered_backend_as_successful_status_poll():
    events = []
    device = types.SimpleNamespace(
        _refresh_backends=lambda **_kwargs: False,
        _unpowered_backend_reason=lambda: "backend three power PDU output 2 is OFF",
        set_hardware_lifecycle=lambda *args: events.append(("lifecycle", args)),
        _set_off_for_unpowered_backend=lambda reason: events.append(("off", reason)),
    )

    result = aggregator_module.DS_OWIS_Aggregator.get_controller_status_local(device)

    assert result == 0
    assert events[0][0] == "lifecycle"
    assert events[0][1][0].value == "POWER_OFF"
    assert events[0][1][1].value == "NOT_REQUESTED"
    assert events[1] == ("off", "backend three power PDU output 2 is OFF")


def test_owis_aggregator_clears_fault_diagnostics_for_expected_power_off():
    events = []
    device = types.SimpleNamespace(
        _mark_hardware_power_off=lambda message: events.append(message) or message,
    )

    message = aggregator_module.DS_OWIS_Aggregator._set_off_for_unpowered_backend(
        device, "backend 'three' is intentionally OFF"
    )

    assert message == "OWIS aggregator is OFF because backend 'three' is intentionally OFF"
    assert events == [message]


def test_owis_aggregator_logs_expected_power_off_as_information():
    logs = []
    device = types.SimpleNamespace(
        device_name="OWIS Aggregator",
        _backend_alive={"three": True},
        _backend_proxies={"three": object()},
        _backend_reason={"three": ""},
        info=lambda message, *_args: logs.append(("info", message)),
        error=lambda message: logs.append(("error", message)),
    )

    aggregator_module.DS_OWIS_Aggregator._mark_backend_down(
        device, "three", "OWIS controller power is OFF (PDU output 2)"
    )

    assert device._backend_alive["three"] is False
    assert device._backend_proxies["three"] is None
    assert logs == [
        (
            "info",
            "OWIS Aggregator: backend 'three' is down: "
            "OWIS controller power is OFF (PDU output 2)",
        )
    ]


def _make_owis_delay_line_stub(monkeypatch):
    monkeypatch.setattr(ctypes, "WinDLL", lambda _path: object(), raising=False)
    module_name = "DeviceServers.motion.owis.DS_OWIS_delay_line"
    sys.modules.pop(module_name, None)
    module = __import__(module_name, fromlist=["DS_Owis_delay_line"])
    state = {"value": module.DevState.ON}
    device = types.SimpleNamespace(
        control_unit_id=1,
        _device_id_internal=2,
        keep_on=False,
        _position=0.0,
        device_name="Device owis-1 OWIS",
        set_state=lambda value: state.__setitem__("value", value),
        get_state=lambda: state["value"],
        info_stream=lambda *_args, **_kwargs: None,
    )
    device.on_off_motor = lambda on=False: module.DS_Owis_delay_line.on_off_motor(
        device, on
    )
    return module, device, state


def test_owis_delay_line_status_and_read_position_have_explicit_results(monkeypatch):
    module, device, state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device._get_axis_state_ps90 = lambda *_args: (3, "")
    assert cls.get_controller_status_local(device) == 0
    assert state["value"] == module.DevState.ON

    device._get_axis_state_ps90 = lambda *_args: (0, "axis inactive")
    assert "not active" in cls.get_controller_status_local(device)
    assert state["value"] == module.DevState.FAULT

    device._get_pos_ex_ps90 = lambda *_args: (12.5, "")
    assert cls.read_position_local(device) == 0
    assert device._position == 12.5

    device._get_pos_ex_ps90 = lambda *_args: (False, "read failed")
    assert "read failed" in cls.read_position_local(device)


def test_owis_delay_line_power_contracts_return_zero_only_on_success(monkeypatch):
    module, device, _state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device._motor_init_ps90 = lambda *_args: (True, "")
    device._set_target_mode_ps90 = lambda *_args: (True, "")
    device._motor_off_ps90 = lambda *_args: (True, "")
    assert cls.turn_on_local(device) == 0

    device._set_target_mode_ps90 = lambda *_args: (False, "mode failed")
    assert "mode failed" in cls.turn_on_local(device)

    device._stop_axis_ps90 = lambda *_args: (True, "")
    device._motor_off_ps90 = lambda *_args: (True, "")
    assert cls.turn_off_local(device) == 0

    device._stop_axis_ps90 = lambda *_args: (False, "stop failed")
    assert "stop failed" in cls.turn_off_local(device)


def test_owis_delay_line_motion_contracts_return_zero_only_on_success(monkeypatch):
    module, device, _state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device._set_target_ex_ps90 = lambda *_args: (True, "")
    device._go_target_ps90 = lambda *_args: (True, "")
    assert cls.move_axis_local(device, 3.25) == 0

    device._set_target_ex_ps90 = lambda *_args: (False, "target failed")
    assert "target failed" in cls.move_axis_local(device, 3.25)

    device._stop_axis_ps90 = lambda *_args: (True, "")
    device._motor_off_ps90 = lambda *_args: (True, "")
    assert cls.stop_movement_local(device) == 0

    device._stop_axis_ps90 = lambda *_args: (False, "stop failed")
    assert "stop failed" in cls.stop_movement_local(device)


def test_owis_delay_line_write_position_propagates_move_result(monkeypatch):
    module, device, _state = _make_owis_delay_line_stub(monkeypatch)
    cls = module.DS_Owis_delay_line

    device.move_axis = lambda position: 0 if position == 1.0 else "move rejected"

    assert cls.write_position_local(device, 1.0) == 0
    assert cls.write_position_local(device, 2.0) == "move rejected"
