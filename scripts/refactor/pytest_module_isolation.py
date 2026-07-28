"""Keep test-only Tango and Taurus modules local to each collected test file."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Iterator

import pytest


_ISOLATED_MODULE_PREFIXES = (
    "tango",
    "taurus",
    "DeviceServers",
)


def _is_isolated_module(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in _ISOLATED_MODULE_PREFIXES
    )


@contextmanager
def isolated_test_modules() -> Iterator[None]:
    """Restore test-only protocol modules after importing one test module."""
    saved_modules = {
        name: module for name, module in sys.modules.items() if _is_isolated_module(name)
    }
    try:
        yield
    finally:
        for name in tuple(sys.modules):
            if _is_isolated_module(name) and name not in saved_modules:
                del sys.modules[name]
        sys.modules.update(saved_modules)


class IsolatedPythonModule(pytest.Module):
    """Import each test module without leaking its protocol stubs globally."""

    def _getobj(self):
        with isolated_test_modules():
            return super()._getobj()


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makemodule(module_path, parent):
    """Use an isolated collector before pytest creates its default collector."""
    return IsolatedPythonModule.from_parent(parent, path=module_path)
