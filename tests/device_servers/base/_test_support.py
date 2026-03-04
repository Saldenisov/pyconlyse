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


def _install_taurus_stub():
    if "taurus" in sys.modules:
        return

    taurus = types.ModuleType("taurus")

    class MockDevice:
        def __init__(self, *args, **kwargs):
            self.state = 1

        def archive_it(self, data):
            return None

    taurus.Device = MockDevice
    sys.modules["taurus"] = taurus


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_install_tango_stub()
_install_taurus_stub()

from DeviceServers.base import camera as camera_module
from DeviceServers.base import general as general_module
from DeviceServers.base import motor as motor_module
from DeviceServers.base import pdu as pdu_module

__all__ = [
    "camera_module",
    "general_module",
    "motor_module",
    "pdu_module",
]
