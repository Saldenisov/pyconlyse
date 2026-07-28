"""Minimal Tango surface for software-only tests.

Installed through pytest's ``monkeypatch`` fixture, so neither the stub nor
modules imported against it survive beyond the current test.
"""

from __future__ import annotations

import sys
import types


def install_tango_stub(monkeypatch) -> types.ModuleType:
    """Install a local Tango/Tango-server stub and return the Tango module."""
    tango = types.ModuleType("tango")
    server = types.ModuleType("tango.server")

    class AttrWriteType:
        READ = 0
        READ_WRITE = 1

    class DevState:
        OFF = "OFF"
        ON = "ON"
        FAULT = "FAULT"
        STANDBY = "STANDBY"
        MOVING = "MOVING"
        RUNNING = "RUNNING"
        INIT = "INIT"

    class DispLevel:
        OPERATOR = 0
        EXPERT = 1

    class DeviceProxy:
        def __init__(self, name=""):
            self.name = name

        def set_timeout_millis(self, _timeout):
            return None

    class Device:
        def init_device(self):
            return None

        def set_state(self, state):
            self._state = state

        def get_state(self):
            return getattr(self, "_state", DevState.OFF)

        def get_name(self):
            return getattr(self, "_name", "test/device")

        def info_stream(self, *_args, **_kwargs):
            return None

        warn_stream = info_stream
        error_stream = info_stream
        debug_stream = info_stream

    def decorator(*args, **_kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]

        def wrap(function):
            return function

        return wrap

    def device_property(**kwargs):
        return kwargs.get("default_value")

    tango.AttrWriteType = AttrWriteType
    tango.Database = lambda: None
    tango.DevBoolean = bool
    tango.DevFloat = float
    tango.DevState = DevState
    tango.DeviceProxy = DeviceProxy
    tango.DispLevel = DispLevel
    tango.server = server

    server.AttrWriteType = AttrWriteType
    server.Device = Device
    server.attribute = decorator
    server.command = decorator
    server.device_property = device_property
    server.pipe = decorator

    monkeypatch.setitem(sys.modules, "tango", tango)
    monkeypatch.setitem(sys.modules, "tango.server", server)
    return tango
