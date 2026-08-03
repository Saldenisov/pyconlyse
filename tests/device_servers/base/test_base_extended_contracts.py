"""Software-only regression contracts for base device-server behavior."""

from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest
from _test_support import camera_module, general_module, motor_module


class DummyGeneral(general_module.DS_General):
    def __init__(self):
        self._state = general_module.DevState.ON
        self._name = "test/extended-general"
        self.device_id = "extended-general"
        self.friendly_name = "Extended general"
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._status_result = 0
        self.status_calls = 0
        self.archive_records = []
        self.archive = SimpleNamespace(state=1, archive_it=self.archive_records.append)

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "extended-general"

    def register_variables_for_archive(self):
        self.archive_state["State"] = (self.get_state, "int8")

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "test://extended-general"

    def get_controller_status_local(self):
        self.status_calls += 1
        return self._status_result

    def turn_on_local(self):
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0


class DummyCameraCCD(camera_module.DS_CAMERA_CCD):
    def __init__(self):
        self._state = general_module.DevState.ON
        self._name = "test/extended-camera"
        self.device_id = "extended-camera"
        self.friendly_name = "Extended camera"
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self.archive = SimpleNamespace(state=0, archive_it=lambda _data: None)
        self.wavelengths = np.array([400, 500], dtype=np.uint16)
        self.last_image = np.array([1, 2], dtype=np.uint16)
        self.time_stamp_deque = deque(maxlen=10)
        self.data_deque = deque(maxlen=10)
        self.latestimage = True
        self.CG_position = {"X": 0, "Y": 0}
        self.camera_name = "Extended CCD"
        self.start_result = 0
        self.stop_result = 0
        self.turn_on_result = 0
        self.start_calls = 0
        self.stop_calls = 0
        self.turn_on_calls = 0
        self.param_calls = 0
        self._grabbing = False

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "extended-camera"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "test://extended-camera"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        self.turn_on_calls += 1
        if self.turn_on_result == 0:
            self.set_state(general_module.DevState.ON)
        return self.turn_on_result

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0

    def get_camera_friendly_name(self):
        return self.camera_name

    def set_camera_friendly_name(self, value):
        self.camera_name = value

    def set_param_after_init_local(self):
        self.param_calls += 1
        return 0

    def start_grabbing_local(self):
        self.start_calls += 1
        if self.start_result == 0:
            self._grabbing = True
        return self.start_result

    def stop_grabbing_local(self):
        self.stop_calls += 1
        if self.stop_result == 0:
            self._grabbing = False
        return self.stop_result

    def grabbing_local(self):
        return self._grabbing

    def get_image(self):
        return self.last_image


class DummyMultiAxis(motor_module.DS_MOTORIZED_MULTI_AXES):
    def __init__(self):
        self._state = general_module.DevState.ON
        self._name = "test/extended-multi-axis"
        self.device_id = "extended-multi-axis"
        self.friendly_name = "Extended multi-axis"
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._delay_lines_parameters = {
            1: {
                "state": general_module.DevState.ON,
                "position": 1.0,
                "limit_min": 0.0,
                "limit_max": 2.0,
                "device_name": "axis-1",
                "friendly_name": "Axis 1",
            }
        }
        self.move_calls = []

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "extended-multi-axis"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "test://extended-multi-axis"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        return 0

    def turn_off_local(self):
        return 0

    def init_axis_local(self, axis):
        return 0

    def get_status_axis_local(self, axis):
        return 0

    def define_position_axis_local(self, args):
        return 0

    def read_position_axis_local(self, axis):
        return 0

    def set_param_axis_local(self, axis):
        return 0

    def turn_on_axis_local(self, axis):
        return 0

    def turn_off_axis_local(self, axis):
        return 0

    def move_axis_local(self, args):
        self.move_calls.append(args)
        return 0

    def stop_axis_local(self, axis):
        return 0


@pytest.fixture(autouse=True)
def restore_global_settings():
    saved = general_module.GLOBAL_SETTINGS.copy()
    yield
    general_module.GLOBAL_SETTINGS.clear()
    general_module.GLOBAL_SETTINGS.update(saved)


def test_archive_state_emits_only_changes_and_refreshes_snapshot(monkeypatch):
    device = DummyGeneral()
    emitted = []
    monkeypatch.setattr(device, "write_to_archive", emitted.append)
    device.register_variables_for_archive()
    device.fix_state()

    device.send_state_archive()
    device.set_state(general_module.DevState.FAULT)
    device.send_state_archive()

    assert len(emitted) == 1
    assert device.previous_archive_state == {"State": general_module.DevState.FAULT}


def test_failed_recovery_keeps_fault_and_records_backend_error():
    device = DummyGeneral()
    device._status_result = "controller unavailable"
    device.set_state(general_module.DevState.FAULT)

    assert device.recover() == "Recovery failed: controller unavailable"
    assert device.get_state() == general_module.DevState.FAULT
    assert device.fault_recovery_status() == (
        "attempts=0; last_error=controller unavailable"
    )


def test_structured_config_rejects_nested_non_data_values_with_path():
    with pytest.raises(general_module.ConfigurationError, match=r"parameters\['bad'\]"):
        general_module.parse_structured_config({"bad": {1, 2}})


def test_unsetting_global_archive_disable_uses_configured_timeout(monkeypatch):
    device = DummyGeneral()
    calls = []
    monkeypatch.setattr(
        device,
        "_init_archive_connection",
        lambda timeout_seconds: calls.append(timeout_seconds),
    )
    general_module.GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] = 17

    assert device.set_global_variable(["DISABLE_ARCHIVE", "false"]) == (
        "OK: DISABLE_ARCHIVE set to False"
    )
    assert calls == [17]


def test_camera_start_failure_is_reported_without_claiming_success():
    device = DummyCameraCCD()
    device.start_result = "camera busy"

    device.start_grabbing()

    assert device.start_calls == 1
    assert device.grabbing is False
    assert device.last_error() == "camera busy"


def test_camera_failed_turn_on_does_not_apply_configuration():
    device = DummyCameraCCD()
    device.set_state(general_module.DevState.OFF)
    device.turn_on_result = "power-on failed"

    device.turn_on()

    assert device.turn_on_calls == 1
    assert device.param_calls == 0
    assert device.get_state() == general_module.DevState.OFF
    assert device.last_error() == "power-on failed"


def test_camera_stopped_order_remains_unchanged_while_samples_continue():
    device = DummyCameraCCD()
    device.register_order_local("stopped", [2])
    original = device.orders["stopped"].order_array.copy()
    device.orders["stopped"].order_done = True

    device.treat_orders(np.array([[11, 12]], dtype=np.uint16))

    assert np.array_equal(device.orders["stopped"].order_array, original)
    assert len(device.data_deque) == 1
    assert len(device.time_stamp_deque) == 1


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ([True, 1.0], "axis id must be an integer"),
        ([1, True], "position must be numeric"),
        ([1], "move_axis expects"),
    ],
)
def test_multi_axis_move_rejects_invalid_input_before_local_call(args, message):
    device = DummyMultiAxis()

    assert message in device.move_axis(args)
    assert device.move_calls == []


def test_multi_axis_unknown_axis_read_returns_nan_without_local_access():
    device = DummyMultiAxis()

    assert np.isnan(device.read_position_axis(2))
    assert "unknown axis 2" in device.last_error()
