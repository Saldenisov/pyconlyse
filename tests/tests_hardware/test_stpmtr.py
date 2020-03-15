from devices.service_devices.stepmotors.stpmtr_emulate import StpMtrCtrl_emulate
from utilities.data.datastructures.mes_independent.devices_dataclass import FuncActivateOutput, FuncPowerOutput
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import FuncActivateAxisOutput

from tests.tests_hardware.fixtures import stpmtr_emulate

import pytest


def test_func_stpmtr_emulate(stpmtr_emulate: StpMtrCtrl_emulate):
    stpmtr_emulate.start()

    available_functions = []

    # Testing Power function
    # power On
    res: FuncPowerOutput = stpmtr_emulate.power(True)
    assert type(res) == FuncPowerOutput
    assert res.func_success
    assert res.device_id == stpmtr_emulate.id
    assert res.device_status.power
    
    # Testing Activate function
    # activate
    res: FuncActivateOutput = stpmtr_emulate.activate(True)
    assert type(res) == FuncActivateOutput
    assert res.func_success
    assert res.device_id == stpmtr_emulate.id
    assert res.device_status.active
    # activate
    res: FuncActivateOutput = stpmtr_emulate.activate(True)
    assert res.func_success
    assert res.device_status.active
    # disactivate
    res: FuncActivateOutput = stpmtr_emulate.activate(False)
    assert res.func_success
    assert not res.device_status.active
    # disactivate for second time
    res: FuncActivateOutput = stpmtr_emulate.activate(False)
    assert not res.func_success
    assert not res.device_status.active
    # power off
    res: FuncPowerOutput = stpmtr_emulate.power(False)
    assert res.func_success
    assert not res.device_status.power
    # activate
    res: FuncActivateOutput = stpmtr_emulate.activate(True)
    assert not res.func_success
    assert not res.device_status.active

    res: FuncPowerOutput = stpmtr_emulate.power(True)
    res: FuncActivateOutput = stpmtr_emulate.activate(True)

    # Activate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(1, True)
    assert res.func_success
    essentials = stpmtr_emulate.axes_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert res.comments == f'Axes status: {status}. '
    # Disactivate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(1, False)
    assert res.func_success
    essentials = stpmtr_emulate.axes_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert res.comments == f'Axes status: {status}. '

    # Disactivate controller
    res: FuncActivateOutput = stpmtr_emulate.activate(False)
    # Activate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(1, True)
    assert not res.func_success
    #Activate controller
    res: FuncActivateOutput = stpmtr_emulate.activate(True)
    # Activate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(1, True)
    # Disactivate controller
    res: FuncActivateOutput = stpmtr_emulate.activate(False)

    stpmtr_emulate.stop()
