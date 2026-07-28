from threading import RLock

from tests.device_servers.base._test_support import _install_tango_stub

_install_tango_stub()

from DeviceServers.base import general as general_module
from DeviceServers.cameras.basler import DS_Basler_camera as basler_module


class FakeThread:
    def __init__(self, *args, **kwargs):
        self.daemon = False

    def start(self):
        return None


class FakeCamera:
    def __init__(self, serial="BASLER-001"):
        self.serial = serial
        self.open_calls = 0
        self.start_grabbing_calls = 0
        self.stop_grabbing_calls = 0
        self._open = False
        self._grabbing = False
        self.DeviceUserID = type("UserId", (), {"GetValue": lambda self: "Basler"})()

    def IsOpen(self):
        return self._open

    def Open(self):
        self.open_calls += 1
        self._open = True

    def Close(self):
        self._open = False

    def IsGrabbing(self):
        return self._grabbing

    def StartGrabbing(self, strategy):
        self.start_grabbing_calls += 1
        self._grabbing = True

    def StopGrabbing(self):
        self.stop_grabbing_calls += 1
        self._grabbing = False

    def GetDeviceInfo(self):
        info = type("Info", (), {})()
        info.GetSerialNumber = lambda: self.serial
        return info


class FakeFactory:
    def __init__(self, discovered, camera):
        self.discovered = discovered
        self.camera = camera

    def EnumerateDevices(self):
        return [self.discovered]

    def CreateDevice(self, device):
        assert device is self.discovered
        return device


class FakePylon:
    GrabStrategy_LatestImageOnly = "latest"
    GrabStrategy_OneByOne = "one-by-one"

    def __init__(self, factory):
        self._factory = factory
        self.TlFactory = type(
            "TlFactory", (), {"GetInstance": staticmethod(lambda: factory)}
        )

    @staticmethod
    def ImageFormatConverter():
        return object()

    def InstantCamera(self, device):
        assert device is self._factory.discovered
        return self._factory.camera


def make_device():
    device = object.__new__(basler_module.DS_Basler_camera)
    device._state = general_module.DevState.OFF
    device._lifecycle_lock = RLock()
    device._name = "test/basler"
    device.device_id = "basler-1"
    device.friendly_name = "Basler"
    device.archive_state = {}
    device.previous_archive_state = {}
    device.camera = None
    device.converter = None
    device.device = None
    device.latestimage = True
    device.grabbing_thread = None
    device.info = lambda *args, **kwargs: None
    device.error = lambda *args, **kwargs: None
    device.fix_state = lambda: None
    device.check_func_allowance = lambda _func: 1
    device.set_param_after_init_local = lambda: setattr(
        device, "settings_calls", getattr(device, "settings_calls", 0) + 1
    ) or 0
    return device


def test_find_device_creates_passive_camera_without_opening(monkeypatch):
    device = make_device()
    discovered = type(
        "Device", (), {"GetSerialNumber": lambda self: "BASLER-001"}
    )()
    camera = FakeCamera()
    factory = FakeFactory(discovered, camera)
    monkeypatch.setattr(basler_module, "pylon", FakePylon(factory))
    device.serial_number = "BASLER-001"

    result = device.find_device()

    assert result == (1, b"BASLER-001")
    assert device.camera is camera
    assert camera.open_calls == 0
    assert camera.start_grabbing_calls == 0
    assert device.get_state() == general_module.DevState.OFF


def test_init_device_does_not_start_grabbing_for_an_open_camera(monkeypatch):
    device = make_device()
    camera = FakeCamera()
    camera._open = True
    monkeypatch.setattr(
        basler_module.DS_CAMERA_CCD,
        "init_device",
        lambda self: setattr(self, "camera", camera),
    )
    device.register_variables_for_archive = lambda: None

    device.init_device()

    assert camera.start_grabbing_calls == 0


def test_explicit_turn_on_opens_once_applies_settings_and_grabs_only_on_command(
    monkeypatch,
):
    device = make_device()
    camera = FakeCamera()
    discovered = type(
        "Device", (), {"GetSerialNumber": lambda self: "BASLER-001"}
    )()
    factory = FakeFactory(discovered, camera)
    monkeypatch.setattr(basler_module, "pylon", FakePylon(factory))
    monkeypatch.setattr(basler_module, "Thread", FakeThread)
    device.camera = camera

    device.turn_on()

    assert camera.open_calls == 1
    assert device.settings_calls == 1
    assert camera.start_grabbing_calls == 0
    assert device.get_state() == general_module.DevState.ON

    assert device.start_grabbing_local() == 0
    assert camera.start_grabbing_calls == 1
