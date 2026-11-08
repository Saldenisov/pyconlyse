"""Scoped import-only SDK stand-ins for fake-device unit tests.

Transport construction fails loudly unless a test explicitly replaces it.
No native driver package is imported, installed or initialized.
"""
from contextlib import contextmanager
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


def unavailable(*_args, **_kwargs):
    raise AssertionError("A fake-device test attempted to construct an SDK transport")


@contextmanager
def avantes_imports():
    package, equipment, exceptions = (ModuleType(name) for name in ("msl", "msl.equipment", "msl.equipment.exceptions"))
    equipment.Backend = SimpleNamespace(MSL="MSL")
    equipment.ConnectionRecord = lambda **kwargs: SimpleNamespace(**kwargs)
    equipment.EquipmentRecord = unavailable
    exceptions.AvantesError = type("AvantesError", (Exception,), {})
    package.equipment = equipment
    equipment.exceptions = exceptions
    with patch.dict("sys.modules", {"msl": package, "msl.equipment": equipment, "msl.equipment.exceptions": exceptions}):
        yield


@contextmanager
def daqmx_imports():
    package, constants, system = (ModuleType(name) for name in ("nidaqmx", "nidaqmx.constants", "nidaqmx.system"))
    package.Task = unavailable
    constants.AcquisitionType = SimpleNamespace(FINITE="FINITE")
    constants.CurrentShuntResistorLocation = SimpleNamespace(LET_DRIVER_CHOOSE="DEFAULT", INTERNAL="INTERNAL", EXTERNAL="EXTERNAL")
    constants.Edge = SimpleNamespace(RISING="RISING")
    constants.TerminalConfiguration = SimpleNamespace(DEFAULT="DEFAULT", RSE="RSE", NRSE="NRSE", DIFF="DIFF")
    system.Device = unavailable
    system.System = SimpleNamespace(local=unavailable)
    package.constants, package.system = constants, system
    with patch.dict("sys.modules", {"nidaqmx": package, "nidaqmx.constants": constants, "nidaqmx.system": system}):
        yield


@contextmanager
def scpi_imports():
    module = ModuleType("easy_scpi")
    module.Instrument = unavailable
    with patch.dict("sys.modules", {"easy_scpi": module}):
        yield
