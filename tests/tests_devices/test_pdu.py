from devices.service_devices.pdu import *
from tests.fixtures.services import *
from devices.service_devices.pdu.pdu_dataclass import *
from time import sleep
one_service = [pdu_netio_test_non_fixture()]
#all_services = []
test_param = one_service


@pytest.mark.parametrize('pdu', test_param)
def test_func_stpmtr(pdu: PDUController):
    pdu.start()

    ACTIVATE = FuncActivateInput(flag=True)
    ACTIVATE_DEVICE_FOUR = FuncActivateDeviceInput(4, 1)
    GETPDUOUTPUTS = FuncGetPDUStateInput(4)
    DEACTIVATE = FuncActivateInput(flag=False)
    POWER_ON = FuncPowerInput(flag=True)
    POWER_OFF = FuncPowerInput(flag=False)

    # Power on
    res: FuncPowerOutput = pdu.power(POWER_ON)
    assert res.func_success
    assert res.controller_status.power
    # Activate
    res: FuncActivateOutput = pdu.activate(ACTIVATE)
    assert res.func_success
    assert res.controller_status.active
    # Deactivate
    res: FuncActivateOutput = pdu.activate(DEACTIVATE)
    assert res.func_success
    assert not res.controller_status.active
    # Activate
    res: FuncActivateOutput = pdu.activate(ACTIVATE)
    assert res.func_success
    assert res.controller_status.active
    # Power off when active
    res: FuncPowerOutput = pdu.power(POWER_OFF)
    assert not res.func_success
    assert res.controller_status.power
    # Activate PDU number 4
    res: FuncActivateDeviceOutput = pdu.activate_device(ACTIVATE_DEVICE_FOUR)
    assert res.func_success
    assert res.device.device_id_seq == 4
    # Get PDU4 outputs status
    res: FuncGetPDUStateOutput = pdu.get_pdu_state(GETPDUOUTPUTS)
    assert res.func_success
    assert res.pdu.outputs[4].state == 0
    # Set PDU4 output status
    new_state: PDUOutput = pdu.pdus[4].outputs[3]
    new_state.state = 1
    SETPDUOUTPUTS = FuncSetPDUStateInput(4, 3, new_state)
    res: FuncSetPDUStateOutput = pdu.set_pdu_state(SETPDUOUTPUTS)
    assert res.func_success
    assert res.pdu.outputs[3].state == 1
    sleep(0.5)
    new_state.state = 0
    SETPDUOUTPUTS = FuncSetPDUStateInput(4, 3, new_state)
    res: FuncSetPDUStateOutput = pdu.set_pdu_state(SETPDUOUTPUTS)



    pdu.stop()