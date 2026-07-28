from threading import RLock

import pytest

from tests.device_servers.base._test_support import _install_tango_stub

_install_tango_stub()

from DeviceServers.base import general as general_module
from DeviceServers.cameras.avantes import DS_AVANTES_CCD as avantes_module


class FakeThread:
    def __init__(self, *args, **kwargs):
        self.daemon = False

    def start(self):
        return None


class FakeCamera:
    def __init__(self):
        self.high_res_calls = 0
        self.disconnect_calls = 0

    def use_high_res_adc(self, enabled):
        assert enabled is True
        self.high_res_calls += 1

    def get_lambda(self):
        return [400.0, 500.0, 600.0]

    def get_num_pixels(self):
        return 3

    def disconnect(self):
        self.disconnect_calls += 1


class FakeRecord:
    def __init__(self, camera):
        self.camera = camera
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        return self.camera


def make_device():
    device = object.__new__(avantes_module.DS_AVANTES_CCD)
    device._state = general_module.DevState.OFF
    device._lifecycle_lock = RLock()
    device._name = "test/avantes"
    device.device_id = "AVS-001"
    device.friendly_name = "Avantes"
    device.serial_number_real = "AVS-001"
    device.dll_path = "fake.dll"
    device.archive_state = {}
    device.previous_archive_state = {}
    device.camera = None
    device.record = None
    device.width = 0
    device.wavelengths = "[400.0, 500.0, 600.0]"
    device.status_real = 0
    device.abort = True
    device.timeoutt = 1
    device.info = lambda *args, **kwargs: None
    device.error = lambda *args, **kwargs: None
    device.fix_state = lambda: None
    device.check_func_allowance = lambda _func: 1
    device.set_param_after_init_local = lambda: setattr(
        device, "settings_calls", getattr(device, "settings_calls", 0) + 1
    ) or 0
    return device


def test_init_parses_legacy_wavelengths_without_eval(monkeypatch):
    device = make_device()
    monkeypatch.setattr(avantes_module.DS_CAMERA_CCD, "init_device", lambda self: None)
    device.register_variables_for_archive = lambda: None

    device.init_device()

    assert device.wavelengths == [400.0, 500.0, 600.0]


def test_init_rejects_executable_wavelengths(monkeypatch):
    device = make_device()
    device.wavelengths = "__import__('os').system('false')"
    monkeypatch.setattr(avantes_module.DS_CAMERA_CCD, "init_device", lambda self: None)
    device.register_variables_for_archive = lambda: None

    with pytest.raises(general_module.ConfigurationError):
        device.init_device()


def test_find_device_creates_passive_record_without_sdk_connection(monkeypatch):
    device = make_device()
    created = []

    class PassiveRecord:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.connect_calls = 0
            created.append(self)

        def connect(self):
            self.connect_calls += 1
            raise AssertionError("find_device must not connect the Avantes SDK")

    monkeypatch.setattr(avantes_module, "EquipmentRecord", PassiveRecord)

    result = device.find_device()

    assert result == (1, b"AVS-001")
    assert device.record is created[0]
    assert device.record.connect_calls == 0
    assert device.camera is None
    assert device.get_state() == general_module.DevState.OFF


def test_turn_off_is_safe_without_a_connected_camera():
    device = make_device()

    assert device.turn_off_local() == 0
    assert device.get_state() == general_module.DevState.OFF


def test_explicit_turn_on_connects_once_applies_settings_and_grabs_only_on_command(
    monkeypatch,
):
    device = make_device()
    camera = FakeCamera()
    record = FakeRecord(camera)
    device.record = record
    monkeypatch.setattr(avantes_module, "Thread", FakeThread)

    device.turn_on()

    assert record.connect_calls == 1
    assert camera.high_res_calls == 1
    assert device.width == 3
    assert device.wavelengths == [400.0, 500.0, 600.0]
    assert device.settings_calls == 1
    assert device.abort is True
    assert device.get_state() == general_module.DevState.ON

    assert device.start_grabbing_local() == 0
    assert device.abort is False
