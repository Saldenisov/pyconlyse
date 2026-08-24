"""Keep test-only Tango and Taurus modules local to each collected test file."""

from __future__ import annotations

import os
import sys
import types
from contextlib import contextmanager
from typing import Iterator, MutableMapping

import pytest

from tests._tango_stub import install_tango_stub


_ISOLATED_MODULE_PREFIXES = (
    "tango",
    "taurus",
    "DeviceServers",
)

_INERT_TANGO_HOST = "127.0.0.1:1"
_TANGO_ENVIRONMENT_KEYS = ("TANGO_HOST", "PYCONLYSE_TANGO_HOST")


class _ModuleSetitemAdapter:
    """Small ``monkeypatch``-compatible adapter for collection-time stubs."""

    def setitem(self, mapping: MutableMapping[str, object], key: str, value: object):
        mapping[key] = value


class _InertDatabase:
    """Database placeholder that cannot open a network connection."""

    def __getattr__(self, name: str):
        raise RuntimeError(
            "Tango Database access is unavailable while collecting software-only tests "
            f"(attempted {name})"
        )


class _InertTaurusDevice:
    """Taurus placeholder that cannot create a real device connection."""

    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("Taurus Device access is unavailable while collecting tests")


def _install_inert_taurus_stub() -> None:
    """Install importable Taurus package shells without a Qt or Tango backend."""
    package_names = (
        "taurus",
        "taurus.core",
        "taurus.core.tango",
        "taurus.external",
        "taurus.external.qt",
        "taurus.qt",
        "taurus.qt.qtgui",
        "taurus.qt.qtgui.application",
        "taurus.qt.qtgui.base",
        "taurus.qt.qtgui.button",
        "taurus.qt.qtgui.input",
    )
    modules = {name: types.ModuleType(name) for name in package_names}
    for name, module in modules.items():
        if name in {
            "taurus",
            "taurus.core",
            "taurus.external",
            "taurus.qt",
            "taurus.qt.qtgui",
        }:
            module.__path__ = []
        sys.modules[name] = module

    taurus = modules["taurus"]
    taurus.core = modules["taurus.core"]
    taurus.external = modules["taurus.external"]
    taurus.qt = modules["taurus.qt"]
    taurus.Device = _InertTaurusDevice
    modules["taurus.core"].tango = modules["taurus.core.tango"]
    modules["taurus.external"].qt = modules["taurus.external.qt"]
    modules["taurus.qt"].qtgui = modules["taurus.qt.qtgui"]
    modules["taurus.qt.qtgui"].application = modules["taurus.qt.qtgui.application"]
    modules["taurus.qt.qtgui"].base = modules["taurus.qt.qtgui.base"]
    modules["taurus.qt.qtgui"].button = modules["taurus.qt.qtgui.button"]
    modules["taurus.qt.qtgui"].input = modules["taurus.qt.qtgui.input"]


def _install_collection_protocol_stubs() -> None:
    """Install protocol shells that are safe to import during collection only."""
    tango = install_tango_stub(_ModuleSetitemAdapter())
    tango.Database = _InertDatabase
    _install_inert_taurus_stub()
    sys.modules["taurus.core.tango"].DevState = tango.DevState


def _is_isolated_module(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in _ISOLATED_MODULE_PREFIXES
    )


@contextmanager
def isolated_test_modules(*, install_protocol_stubs: bool = False) -> Iterator[None]:
    """Restore exact protocol-module and environment state after one module."""
    saved_modules = {
        name: module for name, module in sys.modules.items() if _is_isolated_module(name)
    }
    saved_environment = dict(os.environ)
    try:
        if install_protocol_stubs:
            for key in _TANGO_ENVIRONMENT_KEYS:
                os.environ[key] = _INERT_TANGO_HOST
            _install_collection_protocol_stubs()
        yield
    finally:
        for name in tuple(sys.modules):
            if _is_isolated_module(name) and name not in saved_modules:
                del sys.modules[name]
        sys.modules.update(saved_modules)
        os.environ.clear()
        os.environ.update(saved_environment)


class IsolatedPythonModule(pytest.Module):
    """Import each test module without leaking its protocol stubs globally."""

    def _getobj(self):
        with isolated_test_modules(install_protocol_stubs=True):
            return super()._getobj()


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makemodule(module_path, parent):
    """Use an isolated collector before pytest creates its default collector."""
    return IsolatedPythonModule.from_parent(parent, path=module_path)
