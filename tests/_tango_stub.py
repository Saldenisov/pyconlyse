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

    class _DevStateValue(int):
        """Inert int-like Tango state with Tango's readable string form."""

        def __new__(cls, value, name):
            instance = int.__new__(cls, value)
            instance.name = name
            return instance

        def __str__(self):
            return self.name

        def __repr__(self):
            return str(int(self))

        def __eq__(self, other):
            if isinstance(other, str):
                return self.name == other
            return int.__eq__(self, other)

        __hash__ = int.__hash__

    class DevState:
        OFF = _DevStateValue(0, "OFF")
        ON = _DevStateValue(1, "ON")
        FAULT = _DevStateValue(2, "FAULT")
        STANDBY = _DevStateValue(3, "STANDBY")
        MOVING = _DevStateValue(4, "MOVING")
        RUNNING = _DevStateValue(5, "RUNNING")
        INIT = _DevStateValue(6, "INIT")

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
