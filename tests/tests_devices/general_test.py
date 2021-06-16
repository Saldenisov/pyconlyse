from devices.devices import Device
from devices.datastruct_for_messaging import *

ACTIVATE = FuncActivateInput(flag=True)
DEACTIVATE = FuncActivateInput(flag=False)
POWER_ON = FuncPowerInput(flag=True)
POWER_OFF = FuncPowerInput(flag=False)


def activate(device: Device, success_expected=True):
    res: FuncActivateOutput = device.activate(ACTIVATE)
    assert res.func_success == success_expected
    if success_expected:
        assert res.controller_status.active


def deactivate(device: Device, success_expected=True):
    res: FuncActivateOutput = device.activate(DEACTIVATE)
    assert res.func_success == success_expected
    if success_expected:
        assert not res.controller_status.active


def power_on(device: Device, success_expected=True):
    # Power on
    res: FuncPowerOutput = device.power(POWER_ON)
    assert res.func_success == success_expected
    if success_expected:
        assert res.controller_status.power


def power_off(device: Device, success_expected=True):
    # Power on
    res: FuncPowerOutput = device.power(POWER_OFF)
    assert res.func_success == success_expected
    if success_expected:
        assert not res.controller_status.power