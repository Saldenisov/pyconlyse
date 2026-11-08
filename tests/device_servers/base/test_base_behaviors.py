import sys
from collections import deque
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import numpy as np
import pytest

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from _test_support import (
    DS_Motor,
    camera_module,
    general_module,
    motor_module,
    pdu_module,
)


class DummyGeneral(general_module.DS_General):
    def __init__(self):
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self.locking_client_token = ""
        self.locked_client = False
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = general_module.DevState.OFF
        self._name = "test/device"
        self.device_id = "dev-1"
        self.friendly_name = "General"
        self.always_on = 0
        self.archive_enabled = 1
        self.archive_records = []
        self.archive = SimpleNamespace(state=1, archive_it=self.archive_records.append)
        self.controller_status_calls = 0
        self.turn_on_calls = 0
        self.turn_off_calls = 0

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "dummy"

    def init_device(self):
        return super().init_device()

    def register_variables_for_archive(self):
        self.archive_state["State"] = (self.get_state, "int8")

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "dummy://device"

    def get_controller_status_local(self):
        self.controller_status_calls += 1
        return 0

    def turn_on_local(self):
        self.turn_on_calls += 1
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.turn_off_calls += 1
        self.set_state(general_module.DevState.OFF)
        return 0


class DummyPDU(pdu_module.DS_PDU):
    def __init__(self):
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = general_module.DevState.ON
        self._name = "test/pdu"
        self.device_id = "pdu-1"
        self.friendly_name = "PDU"
        self.always_on = 0
        self._names = ["A", "B"]
        self._ids = [1, 2]
        self._states = [0, 1]
        self._outputs = {}
        self.set_calls = []
        self.timed_calls = []
        self.next_set_result = 0

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "pdu"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "pdu://device"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0

    def get_channels_state_local(self):
        return 0

    def set_channels_states_local(self, outputs):
        self.set_calls.append(list(outputs))
        return self.next_set_result

    def _time_call(self, name, func, *args):
        self.timed_calls.append(name)
        return func(*args)


class DummyMonoMotor(motor_module.DS_MOTORIZED_MONO_AXIS):
    def __init__(self):
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = general_module.DevState.ON
        self._name = "test/motor"
        self.device_id = "motor-1"
        self.friendly_name = "Motor"
        self.always_on = 0
        self.limit_min = 0.0
        self.limit_max = 10.0
        self.real_pos = 5.0
        self.preset_positions = [1.0, 2.5]
        self._position = 5.0
        self._prev_pos = 5.0
        self._power_status = "PWR_NORM"
        self.last_written = None
        self.last_moved_to = None
        self.read_position_calls = 0
        self.stop_calls = 0
        self.stop_result = 0
        self.move_result = 0
        self.controller_status_calls = 0

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "motor"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "motor://device"

    def get_controller_status_local(self):
        self.controller_status_calls += 1
        return 0

    def turn_on_local(self):
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0

    def read_position_local(self):
        self.read_position_calls += 1
        return 0

    def write_position_local(self, pos):
        self.last_written = pos
        self._position = pos
        return 0

    def define_position_local(self, position):
        self._position = float(position)
        return 0

    def move_axis_local(self, pos):
        self.last_moved_to = pos
        self._position = pos
        return self.move_result

    def stop_movement_local(self):
        self.stop_calls += 1
        return self.stop_result


class BlockingDummyMonoMotor(DummyMonoMotor):
    def __init__(self):
        super().__init__()
        self.move_entered = Event()
        self.release_move = Event()
        self.stop_entered = Event()
        self.release_stop = Event()
        self.block_stop = False
        self.read_entered = Event()
        self.release_read = Event()
        self.block_read = False

    def move_axis_local(self, pos):
        self.last_moved_to = pos
        self.move_entered.set()
        assert self.release_move.wait(timeout=2.0)
        self._position = pos
        return 0

    def stop_movement_local(self):
        self.stop_calls += 1
        self.stop_entered.set()
        if self.block_stop:
            assert self.release_stop.wait(timeout=2.0)
        return self.stop_result

    def read_position_local(self):
        self.read_position_calls += 1
        self.read_entered.set()
        if self.block_read:
            assert self.release_read.wait(timeout=2.0)
        return 0


class DummyMultiMotor(motor_module.DS_MOTORIZED_MULTI_AXES):
    def __init__(self):
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = general_module.DevState.ON
        self._name = "test/multi_motor"
        self.device_id = "multi-1"
        self.friendly_name = "MultiMotor"
        self.always_on = 0
        self._delay_lines_parameters = {
            1: {
                "state": general_module.DevState.ON,
                "position": 1.5,
                "device_name": "axis-1",
                "friendly_name": "Axis 1",
                "limit_min": -10.0,
                "limit_max": 10.0,
            },
            2: {
                "state": general_module.DevState.STANDBY,
                "position": 3.0,
                "device_name": "axis-2",
                "friendly_name": "Axis 2",
                "limit_min": -10.0,
                "limit_max": 10.0,
            },
        }
        self.move_calls = []

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "multi-motor"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "multi-motor://device"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0

    def init_axis_local(self, axis):
        return 0

    def get_status_axis_local(self, axis):
        return 0

    def define_position_axis_local(self, args):
        axis, position = args
        self._delay_lines_parameters[axis]["position"] = position
        return 0

    def read_position_axis_local(self, axis):
        return 0

    def set_param_axis_local(self, args):
        return 0

    def turn_on_axis_local(self, axis):
        self._delay_lines_parameters[axis]["state"] = general_module.DevState.ON
        return 0

    def turn_off_axis_local(self, axis):
        self._delay_lines_parameters[axis]["state"] = general_module.DevState.OFF
        return 0

    def move_axis_local(self, args):
        axis, position = args
        self.move_calls.append([axis, position])
        self._delay_lines_parameters[axis]["position"] = position
        return 0

    def stop_axis_local(self, args):
        return 0


class BlockingDummyMultiMotor(DummyMultiMotor):
    def __init__(self):
        super().__init__()
        self.move_entered = Event()
        self.release_move = Event()
        self.stop_calls = 0
        self.stop_result = 0
        self.read_position_calls = []
        self.stop_entered = Event()
        self.release_stop = Event()
        self.block_stop = False
        self.read_entered = Event()
        self.release_read = Event()
        self.block_read = False

    def move_axis_local(self, args):
        axis, position = args
        self.move_calls.append([axis, position])
        if axis == 1:
            self.move_entered.set()
            assert self.release_move.wait(timeout=2.0)
        self._delay_lines_parameters[axis]["position"] = position
        return 0

    def read_position_axis_local(self, axis):
        self.read_position_calls.append(axis)
        self.read_entered.set()
        if self.block_read:
            assert self.release_read.wait(timeout=2.0)
        return 0

    def stop_axis_local(self, axis):
        self.stop_calls += 1
        self.stop_entered.set()
        if self.block_stop:
            assert self.release_stop.wait(timeout=2.0)
        return self.stop_result


class DummyCamera(camera_module.DS_CAMERA):
    def __init__(self):
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = general_module.DevState.ON
        self._name = "test/camera"
        self.device_id = "cam-1"
        self.friendly_name = "Camera"
        self.always_on = 0
        self.archive = SimpleNamespace(state=0, archive_it=lambda data: None)
        self.wavelengths = np.array([100, 200, 300], dtype=np.uint16)
        self.last_image = np.array([10, 11, 12], dtype=np.uint16)
        self.dll_path = Path("/tmp/fake.dll")
        self._dll_lock = True

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "camera"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "camera://device"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0


class DummyCameraCCD(camera_module.DS_CAMERA_CCD):
    def __init__(self):
        self.orders = {}
        self.previous_archive_state = {}
        self.archive_state = {}
        self._comment = "..."
        self._error = "..."
        self._n = 0
        self._state = general_module.DevState.ON
        self._name = "test/camera_ccd"
        self.device_id = "ccd-1"
        self.friendly_name = "CCD"
        self.always_on = 0
        self.archive = SimpleNamespace(state=0, archive_it=lambda data: None)
        self.wavelengths = np.array([400, 500, 600], dtype=np.uint16)
        self.last_image = np.array([1, 2, 3], dtype=np.uint16)
        self.time_stamp_deque = deque(maxlen=1000)
        self.data_deque = deque(maxlen=1000)
        self.n_average = 1
        self.n_kinetics = 1
        self.latestimage = True
        self.CG_position = {"X": 0, "Y": 0}
        self.camera_name = "CCD A"
        self.exposure_value = 0.1
        self.exposure_writes = []
        self.param_after_init_calls = 0
        self.turn_on_calls = 0
        self.start_calls = 0
        self.stop_calls = 0
        self._grabbing = False
        self.image_reads = 0

    @property
    def _version_(self):
        return "1.0"

    @property
    def _model_(self):
        return "ccd"

    def register_variables_for_archive(self):
        return None

    def find_device(self):
        self._device_id_internal = 1
        self._uri = "ccd://device"

    def get_controller_status_local(self):
        return 0

    def turn_on_local(self):
        self.turn_on_calls += 1
        self.set_state(general_module.DevState.ON)
        return 0

    def turn_off_local(self):
        self.set_state(general_module.DevState.OFF)
        return 0

    def get_camera_friendly_name(self):
        return self.camera_name

    def set_camera_friendly_name(self, value):
        self.camera_name = value

    def get_exposure_time(self):
        return self.exposure_value

    def set_exposure_time(self, value):
        self.exposure_writes.append(value)
        self.exposure_value = value

    def set_param_after_init_local(self):
        self.param_after_init_calls += 1
        return 0

    def start_grabbing_local(self):
        self.start_calls += 1
        self._grabbing = True
        return 0

    def stop_grabbing_local(self):
        self.stop_calls += 1
        self._grabbing = False
        return 0

    def grabbing_local(self):
        return self._grabbing

    def get_image(self):
        self.image_reads += 1
        return self.last_image


DummyCameraCCD.__abstractmethods__ = frozenset()


@pytest.fixture(autouse=True)
def restore_global_settings():
    saved = general_module.GLOBAL_SETTINGS.copy()
    yield
    general_module.GLOBAL_SETTINGS.clear()
    general_module.GLOBAL_SETTINGS.update(saved)


def test_str_to_bool_handles_common_values():
    assert general_module._str_to_bool("true") is True
    assert general_module._str_to_bool("On") is True
    assert general_module._str_to_bool("0") is False
    assert general_module._str_to_bool("no") is False


def test_read_info_ds_reports_metadata():
    device = DummyGeneral()

    name, payload = device.read_info_ds()

    assert name == "info_ds"
    assert payload["manufacturer"] == "DummyGeneral"
    assert payload["model"] == "dummy"
    assert payload["version_number"] == "1.0"
    assert payload["device_id"] == "dev-1"


def test_check_func_allowance_accepts_allowed_state():
    device = DummyGeneral()

    assert device.check_func_allowance(device.turn_on) == 1


def test_check_func_allowance_rejects_unknown_function():
    device = DummyGeneral()

    def missing_rule():
        return None

    assert device.check_func_allowance(missing_rule) == -1
    assert "not in RULES" in device.last_error()


def test_faulted_device_runs_health_check_and_recovers_on_success():
    device = DummyGeneral()
    device.set_state(general_module.DevState.FAULT)

    device.get_controller_status()

    assert device.controller_status_calls == 1
    assert device.get_state() == general_module.DevState.ON
    assert device.fault_recovery_status() == "attempts=0; last_error="


def test_fault_recovery_respects_cooldown():
    device = DummyGeneral()
    device.set_state(general_module.DevState.FAULT)
    device._next_fault_recovery_at = 10**12

    device.get_controller_status()

    assert device.controller_status_calls == 0


def test_always_on_does_not_reinitialize_running_device():
    device = DummyGeneral()
    device.always_on = 1
    device.set_state(general_module.DevState.RUNNING)

    device.get_controller_status()

    assert device.controller_status_calls == 1
    assert device.turn_on_calls == 0


def test_status_polling_never_powers_an_off_device_even_when_always_on():
    device = DummyGeneral()
    device.always_on = 1
    device.set_state(general_module.DevState.OFF)

    device.get_controller_status()

    assert device.controller_status_calls == 0
    assert device.turn_on_calls == 0


def test_turn_on_and_off_are_idempotent_without_backend_calls():
    device = DummyGeneral()
    device.set_state(general_module.DevState.ON)

    device.turn_on()
    assert device.turn_on_calls == 0

    device.set_state(general_module.DevState.OFF)
    device.turn_off()
    assert device.turn_off_calls == 0


def test_recover_runs_immediate_health_check_from_fault():
    device = DummyGeneral()
    device.set_state(general_module.DevState.FAULT)
    device._next_fault_recovery_at = 10**12

    assert device.recover() == "Recovered"
    assert device.controller_status_calls == 1
    assert device.get_state() == general_module.DevState.ON


def test_register_and_unregister_client_lock_toggle_flags():
    device = DummyGeneral()

    device.register_client_lock("client-1")
    assert device.locked_client is True
    assert device.locking_client_token == "client-1"

    device.unregister_client_lock()
    assert device.locked_client is False
    assert device.locking_client_token == ""


def test_get_and_list_global_variables_reflect_current_values():
    device = DummyGeneral()
    general_module.GLOBAL_SETTINGS["DISABLE_ARCHIVE"] = True
    general_module.GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] = 12

    assert device.get_global_variable("disable_archive") == "True"
    listed = device.list_global_variables()
    assert "DISABLE_ARCHIVE=True" in listed
    assert "ARCHIVE_TIMEOUT_SECONDS=12" in listed


def test_set_global_variable_rejects_invalid_inputs():
    device = DummyGeneral()

    assert "Provide ['name','value']" in device.set_global_variable(["ONLY_ONE"])
    assert "Unknown global variable" in device.set_global_variable(["MISSING", "1"])
    assert "expects integer value" in device.set_global_variable(
        ["ARCHIVE_TIMEOUT_SECONDS", "nope"]
    )


def test_save_and_reload_global_variables_round_trip(tmp_path, monkeypatch):
    device = DummyGeneral()
    config_path = tmp_path / "global_settings.json"
    monkeypatch.setenv(general_module.CONFIG_FILE_ENV, str(config_path))

    general_module.GLOBAL_SETTINGS["DISABLE_ARCHIVE"] = True
    general_module.GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] = 9

    save_result = device.save_global_variables()
    assert save_result == f"Saved to: {config_path}"

    general_module.GLOBAL_SETTINGS["DISABLE_ARCHIVE"] = False
    general_module.GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] = 1

    reload_result = device.reload_global_variables()

    assert str(config_path) in reload_result
    assert general_module.GLOBAL_SETTINGS["DISABLE_ARCHIVE"] is True
    assert general_module.GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] == 9


def test_reload_global_variables_prefers_environment_over_file(tmp_path, monkeypatch):
    device = DummyGeneral()
    config_path = tmp_path / "global_settings.json"
    config_path.write_text(
        '{"DISABLE_ARCHIVE": false, "ARCHIVE_TIMEOUT_SECONDS": 7}',
        encoding="utf-8",
    )
    monkeypatch.setenv(general_module.CONFIG_FILE_ENV, str(config_path))
    monkeypatch.setenv("DISABLE_ARCHIVE", "true")

    device.reload_global_variables()

    assert general_module.GLOBAL_SETTINGS["DISABLE_ARCHIVE"] is True
    assert general_module.GLOBAL_SETTINGS["ARCHIVE_TIMEOUT_SECONDS"] == 7


def test_write_to_archive_only_emits_when_archive_is_enabled():
    device = DummyGeneral()
    payload = device.form_archive_data(1, "State", time_stamp=123)

    device.write_to_archive(payload)
    assert len(device.archive_records) == 1

    device.archive.state = 0
    device.write_to_archive(payload)
    assert len(device.archive_records) == 1


def test_ds_motor_wrapper_exports_mono_axis_alias():
    assert DS_Motor is motor_module.DS_MOTORIZED_MONO_AXIS


def test_pdu_accessors_expose_internal_collections():
    device = DummyPDU()

    assert device.names() == ["A", "B"]
    assert device.ids() == [1, 2]
    assert device.states() == [0, 1]


# Keep the original pytest entry point and assertion diagnostics.
pytest.register_assert_rewrite(
    f"{__package__}._base_behaviors_pdu_set_channels_states_cases" if __package__ else "_base_behaviors_pdu_set_channels_states_cases",
)

if __package__:
    from ._base_behaviors_pdu_set_channels_states_cases import (
        test_pdu_set_channels_states_uses_timing_wrapper,
        test_pdu_set_channels_states_is_blocked_in_fault_state,
        test_motor_important_parameters_include_presets,
        test_motor_write_position_calls_local_within_limits,
        test_motor_write_position_rejects_out_of_range_values,
        test_motor_move_axis_rel_uses_current_position,
        test_motor_stop_movement_runs_local_handler,
        test_motor_stop_movement_records_backend_failure,
        test_motor_explicit_zero_backend_result_refreshes_readback,
        test_motor_move_returns_backend_and_validation_failures,
        test_motor_stop_does_not_wait_for_blocking_move,
        test_motor_rejects_concurrent_move_while_active_move_is_blocking,
        test_motor_rejects_new_move_while_stop_is_in_progress,
        test_motor_failed_stop_does_not_suppress_blocking_move_readback,
        test_motor_waits_for_stop_that_starts_during_post_move_readback,
        test_multi_motor_accessors_render_axis_snapshots,
        test_multi_motor_move_axis_calls_local_when_allowed,
        test_multi_motor_absolute_move_alias_uses_array_command_contract,
        test_multi_motor_move_axis_returns_message_when_state_disallowed,
        test_multi_motor_move_axis_rejects_unknown_axis_and_out_of_range_position,
        test_multi_motor_stop_does_not_wait_for_blocking_move,
        test_multi_motor_rejects_same_axis_concurrent_move,
        test_multi_motor_allows_independent_move_on_different_axis,
        test_multi_motor_rejects_new_move_while_axis_stop_is_in_progress,
        test_multi_motor_failed_stop_does_not_suppress_post_move_readback,
        test_multi_motor_waits_for_stop_that_starts_during_readback,
        test_camera_register_order_and_give_order_use_uint16_arrays,
        test_camera_give_order_returns_last_image_for_unknown_order,
        test_camera_load_dll_uses_windll_and_unlocks,
        test_camera_ccd_device_friendly_name_reads_and_caches_value,
        test_camera_ccd_write_camera_friendly_name_delegates_to_backend,
        test_camera_ccd_write_exposure_time_updates_backend,
        test_camera_ccd_set_param_after_init_calls_local_handler,
        test_camera_ccd_init_does_not_power_or_configure_camera,
        test_camera_ccd_explicit_turn_on_applies_initial_parameters_once,
        test_camera_ccd_turn_on_applies_settings_when_discovery_already_is_on,
        test_camera_ccd_grab_mode_commands_toggle_latestimage_flag,
        test_camera_ccd_start_and_stop_grabbing_delegate_to_backend,
        test_camera_ccd_image_reads_from_backend,
        test_camera_ccd_treat_orders_appends_data_and_completes_order,
        test_camera_ccd_treat_orders_drops_stale_orders,
    )
else:
    from _base_behaviors_pdu_set_channels_states_cases import (
        test_pdu_set_channels_states_uses_timing_wrapper,
        test_pdu_set_channels_states_is_blocked_in_fault_state,
        test_motor_important_parameters_include_presets,
        test_motor_write_position_calls_local_within_limits,
        test_motor_write_position_rejects_out_of_range_values,
        test_motor_move_axis_rel_uses_current_position,
        test_motor_stop_movement_runs_local_handler,
        test_motor_stop_movement_records_backend_failure,
        test_motor_explicit_zero_backend_result_refreshes_readback,
        test_motor_move_returns_backend_and_validation_failures,
        test_motor_stop_does_not_wait_for_blocking_move,
        test_motor_rejects_concurrent_move_while_active_move_is_blocking,
        test_motor_rejects_new_move_while_stop_is_in_progress,
        test_motor_failed_stop_does_not_suppress_blocking_move_readback,
        test_motor_waits_for_stop_that_starts_during_post_move_readback,
        test_multi_motor_accessors_render_axis_snapshots,
        test_multi_motor_move_axis_calls_local_when_allowed,
        test_multi_motor_absolute_move_alias_uses_array_command_contract,
        test_multi_motor_move_axis_returns_message_when_state_disallowed,
        test_multi_motor_move_axis_rejects_unknown_axis_and_out_of_range_position,
        test_multi_motor_stop_does_not_wait_for_blocking_move,
        test_multi_motor_rejects_same_axis_concurrent_move,
        test_multi_motor_allows_independent_move_on_different_axis,
        test_multi_motor_rejects_new_move_while_axis_stop_is_in_progress,
        test_multi_motor_failed_stop_does_not_suppress_post_move_readback,
        test_multi_motor_waits_for_stop_that_starts_during_readback,
        test_camera_register_order_and_give_order_use_uint16_arrays,
        test_camera_give_order_returns_last_image_for_unknown_order,
        test_camera_load_dll_uses_windll_and_unlocks,
        test_camera_ccd_device_friendly_name_reads_and_caches_value,
        test_camera_ccd_write_camera_friendly_name_delegates_to_backend,
        test_camera_ccd_write_exposure_time_updates_backend,
        test_camera_ccd_set_param_after_init_calls_local_handler,
        test_camera_ccd_init_does_not_power_or_configure_camera,
        test_camera_ccd_explicit_turn_on_applies_initial_parameters_once,
        test_camera_ccd_turn_on_applies_settings_when_discovery_already_is_on,
        test_camera_ccd_grab_mode_commands_toggle_latestimage_flag,
        test_camera_ccd_start_and_stop_grabbing_delegate_to_backend,
        test_camera_ccd_image_reads_from_backend,
        test_camera_ccd_treat_orders_appends_data_and_completes_order,
        test_camera_ccd_treat_orders_drops_stale_orders,
    )
