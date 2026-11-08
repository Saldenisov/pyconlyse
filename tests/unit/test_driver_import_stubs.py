"""Test SDK import isolation and fail-closed transport construction."""
import importlib
import sys

import pytest

from tests.device_servers.base._driver_stubs import avantes_imports, daqmx_imports, scpi_imports


@pytest.mark.parametrize("context,name,transport", [
    (avantes_imports, "msl.equipment", "EquipmentRecord"),
    (daqmx_imports, "nidaqmx", "Task"),
    (scpi_imports, "easy_scpi", "Instrument"),
])
def test_driver_imports_restore_prior_modules_and_forbid_implicit_transport(context, name, transport):
    before = dict(sys.modules)
    with context():
        module = importlib.import_module(name)
        with pytest.raises(AssertionError, match="SDK transport"):
            getattr(module, transport)()
    assert sys.modules.get(name) is before.get(name)
