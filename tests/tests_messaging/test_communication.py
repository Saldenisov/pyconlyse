from time import sleep
from collections import OrderedDict as od
from devices.devices import Server
from devices.virtualdevices.clients import SuperUser
from devices.service_devices.stepmotors.stpmtr_emulate import StpMtrCtrl_emulate
from tests.fixtures import server, superuser, stpmtr_emulate
from tests.tests_messaging.auxil import start_devices, stop_devices
from utilities.data.datastructures.mes_independent.devices_dataclass import (FuncActivateInput, FuncActivateOutput,
                                                                             FuncPowerInput, FuncPowerOutput)
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import (AxisStpMtr, AxisStpMtrEssentials,
                                                                            FuncActivateAxisInput,
                                                                            FuncActivateAxisOutput, FuncMoveAxisToInput,
                                                                            FuncMoveAxisToOutput, FuncGetPosInput,
                                                                            FuncGetPosOutput,
                                                                            FuncGetStpMtrControllerStateInput,
                                                                            FuncGetStpMtrControllerStateOutput,
                                                                            FuncStopAxisInput, FuncStopAxisOutput,
                                                                            relative, absolute)

def test_superuser_server_stpmtr_emulate(server: Server, superuser:SuperUser, stpmtr_emulate: StpMtrCtrl_emulate):

    devices = od()
    devices['server'] = server
    devices['superuser'] = superuser
    devices['stpmtr_emulate'] = stpmtr_emulate

    start_devices(devices)

    sleep(5)

    # Verify Server status
    assert server.device_status.active
    assert stpmtr_emulate.id in server.services_running
    assert superuser.id in server.clients_running

    # Verify SuperUser status
    assert superuser.device_status.active
    assert server.id in superuser.connections

    # Verify Stpmtr_emulate
    # Give power and activate service_device
    stpmtr_emulate.power(FuncPowerInput(stpmtr_emulate.id,True))
    stpmtr_emulate.activate(FuncActivateInput(stpmtr_emulate.id, True))
    assert stpmtr_emulate.device_status.power
    assert stpmtr_emulate.device_status.active
    assert server.id in stpmtr_emulate.connections

    # !SuperUser-Server-Stpmtr_emulate are connected!


    # Testing receiving
    # pyqtslot is connected

    stop_devices(devices)

