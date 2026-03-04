import sys
import types
from pathlib import Path

import pytest


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

from DeviceServers.base import general as general_module
from DeviceServers.base import gpio as gpio_module


class DummyGeneral(general_module.DS_General):
    def __init__(self):
        self.orders = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = general_module.DevState.OFF
        self._name = "test/device"
        self.archive = types.SimpleNamespace(state=1, archive_it=lambda data: None)

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "dummy"

    def init_device(self):
        return super().init_device()

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "dummy://device"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0


class DummyGPIO(gpio_module.DS_GPIO):
    def __init__(self):
        self.orders = {}
        self._blocking_pins = {}
        self._state = general_module.DevState.ON
        self._name = "test/gpio"

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "gpio"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "gpio://device"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        return 0

    def turn_off_local(self):
        return 0

    def generate_pulses_local(self, order):
        return None

    def set_pin_state_local(self, pin_id_value):
        return 0

    def value_from_pin(self, pin_id):
        return 0

    def get_pin_state_local(self, pin_id):
        return 0


@pytest.fixture(autouse=True)
def restore_global_settings():
    saved = general_module.GLOBAL_SETTINGS.copy()
    yield
    general_module.GLOBAL_SETTINGS.clear()
    general_module.GLOBAL_SETTINGS.update(saved)


def test_device_name_falls_back_when_properties_are_missing():
    device = DummyGeneral()

    assert device.device_name == "Device Unknown DummyGeneral"


def test_form_archive_data_preserves_explicit_zero_timestamp():
    device = DummyGeneral()

    archive_data = device.form_archive_data(5, "State", time_stamp=0)

    assert archive_data.data_timestamp == 0


def test_stop_order_returns_minus_one_for_unknown_order():
    device = DummyGeneral()

    assert device.stop_order("missing") == -1


def test_stop_order_marks_existing_order_as_done():
    device = DummyGeneral()
    order = general_module.GeneralOrderInfo(
        order_done=False, order_timestamp=1, ready_to_delete=False
    )
    device.orders["job-1"] = order

    assert device.stop_order("job-1") == 0
    assert order.order_done is True


def test_set_global_variable_can_disable_archive_immediately():
    device = DummyGeneral()

    result = device.set_global_variable(["DISABLE_ARCHIVE", "true"])

    assert result == "OK: DISABLE_ARCHIVE set to True"
    assert general_module.GLOBAL_SETTINGS["DISABLE_ARCHIVE"] is True
    assert device.archive.state == 0


def test_gpio_give_order_local_returns_minus_one_for_missing_order():
    device = DummyGPIO()

    assert device.give_order_local("missing") == -1


def test_gpio_give_order_local_releases_pin_and_order():
    device = DummyGPIO()
    order = types.SimpleNamespace(pin=3, pulses_done=7, ready_to_delete=False)
    device.orders["pulse-job"] = order
    device._blocking_pins[3] = "pulse-job"

    assert device.give_order_local("pulse-job") == 7
    assert order.ready_to_delete is True
    assert "pulse-job" not in device.orders
    assert 3 not in device._blocking_pins
