from devices.service_devices.stepmotors.stpmtr_emulate import StpMtrCtrl_emulate
from utilities.data.datastructures.mes_independent import CmdStruct
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

from tests.fixtures.services import stpmtr_emulate


def test_func_stpmtr_emulate(stpmtr_emulate: StpMtrCtrl_emulate):
    stpmtr_emulate.start()

    available_functions_names = ['activate', 'power', 'get_controller_state', 'activate_axis', 'get_pos', 'move_axis_to',
                                 'stop_axis']
    ACTIVATE = FuncActivateInput(device_id=stpmtr_emulate.id, flag=True)
    DEACTIVATE = FuncActivateInput(device_id=stpmtr_emulate.id, flag=False)
    ACTIVATE_AXIS1 = FuncActivateAxisInput(axis_id=1, device_id=stpmtr_emulate.id, flag=True)
    DEACTIVATE_AXIS1 = FuncActivateAxisInput(axis_id=1, device_id=stpmtr_emulate.id, flag=False)
    GET_POS_AXIS1 = FuncGetPosInput(axis_id=1, device_id=stpmtr_emulate.id)
    GET_CONTOLLER_STATE = FuncGetStpMtrControllerStateInput(device_id=stpmtr_emulate.id)
    MOVE_AXIS1_absolute_ten = FuncMoveAxisToInput(axis_id=1, device_id=stpmtr_emulate.id, pos=10, how=absolute)
    MOVE_AXIS1_absolute_hundred = FuncMoveAxisToInput(axis_id=1, device_id=stpmtr_emulate.id, pos=100, how=absolute)
    MOVE_AXIS1_relative_ten = FuncMoveAxisToInput(axis_id=1, device_id=stpmtr_emulate.id, pos=10, how=relative)
    MOVE_AXIS1_relative_negative_ten = FuncMoveAxisToInput(axis_id=1, device_id=stpmtr_emulate.id, pos=-10, how=relative)
    STOP_AXIS1 = FuncStopAxisInput(device_id=stpmtr_emulate.id, axis_id=1)
    POWER_ON = FuncPowerInput(device_id=stpmtr_emulate.id, flag=True)
    POWER_ON_NO_ID = FuncPowerInput(device_id='', flag=True)
    POWER_OFF = FuncPowerInput(device_id=stpmtr_emulate.id, flag=False)
    # Testing Power function
    # power On with wrong ID
    res: FuncPowerOutput = stpmtr_emulate.power(POWER_ON_NO_ID)
    assert type(res) == FuncPowerOutput
    assert not res.func_success
    # power On
    res: FuncPowerOutput = stpmtr_emulate.power(POWER_ON)
    assert type(res) == FuncPowerOutput
    assert res.func_success
    assert res.device_id == stpmtr_emulate.id
    assert res.device_status.power
    # power off when device is active
    res: FuncActivateOutput = stpmtr_emulate.activate(ACTIVATE)
    assert res.func_success
    res: FuncPowerOutput = stpmtr_emulate.power(POWER_OFF)
    assert not res.func_success
    assert 'Cannot switch power off when device is activated.' in res.comments
    
    # Testing Activate function
    # activate
    res: FuncActivateOutput = stpmtr_emulate.activate(ACTIVATE)
    assert type(res) == FuncActivateOutput
    assert res.func_success
    assert res.device_id == stpmtr_emulate.id
    assert res.device_status.active
    # activate for a second time
    res: FuncActivateOutput = stpmtr_emulate.activate(ACTIVATE)
    assert res.func_success
    assert res.device_status.active
    # deactivate
    res: FuncActivateOutput = stpmtr_emulate.activate(DEACTIVATE)
    assert res.func_success
    assert not res.device_status.active
    # deactivate for a second time
    res: FuncActivateOutput = stpmtr_emulate.activate(DEACTIVATE)
    assert not res.func_success
    assert not res.device_status.active
    # power off
    res: FuncPowerOutput = stpmtr_emulate.power(POWER_OFF)
    assert res.func_success
    assert not res.device_status.power
    # activate when device power is Off
    res: FuncActivateOutput = stpmtr_emulate.activate(ACTIVATE)
    assert not res.func_success
    assert not res.device_status.active

    # Test Activate axis, for example with id=1
    res: FuncPowerOutput = stpmtr_emulate.power(POWER_ON)  # power is On
    res: FuncActivateOutput = stpmtr_emulate.activate(ACTIVATE)  # activate device
    # activate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(ACTIVATE_AXIS1)
    assert res.func_success
    essentials = stpmtr_emulate.axes_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert res.comments == f'Axes status: {status}. '
    # deactivate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(DEACTIVATE_AXIS1)
    assert res.func_success
    essentials = stpmtr_emulate.axes_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert res.comments == f'Axes status: {status}. '

    # deactivate controller
    res: FuncActivateOutput = stpmtr_emulate.activate(DEACTIVATE)
    # activate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(DEACTIVATE_AXIS1)
    assert not res.func_success
    # activate controller
    res: FuncActivateOutput = stpmtr_emulate.activate(ACTIVATE)
    # activate axis 1
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(ACTIVATE_AXIS1)
    # set axis 1 status to 1
    axis_one = stpmtr_emulate.axes[1]
    axis_one.status = 1
    # deactivate controller when all axis are not running
    res: FuncActivateOutput = stpmtr_emulate.activate(DEACTIVATE)
    assert res.func_success
    assert not stpmtr_emulate.device_status.active
    assert not stpmtr_emulate.device_status.connected
    # activate controller and activate axis 1, set it status to 2
    res: FuncActivateOutput = stpmtr_emulate.activate(ACTIVATE)
    res: FuncActivateAxisOutput = stpmtr_emulate.activate_axis(ACTIVATE_AXIS1)
    stpmtr_emulate.axes[1].status = 2
    # deactivate controller when Not all axis are not running
    res: FuncActivateOutput = stpmtr_emulate.activate(DEACTIVATE)
    assert not res.func_success
    assert stpmtr_emulate.device_status.active
    assert stpmtr_emulate.device_status.connected
    assert stpmtr_emulate.device_status.power

    # Test StopAxis function
    # axis 1 status has been set to 2 already.
    # stop axis 1
    res: FuncStopAxisOutput = stpmtr_emulate.stop_axis(STOP_AXIS1)
    assert res.func_success
    assert res.comments == f'Axis {1} was stopped by user.'
    assert res.axes == stpmtr_emulate.axes_essentials
    # stop axis 1 again
    res: FuncStopAxisOutput = stpmtr_emulate.stop_axis(STOP_AXIS1)
    assert res.func_success
    assert res.comments == f'Axis id={1}, name={stpmtr_emulate.axes[1].name} was already stopped.'

    # Test Move_axis1
    # Move axis 1 to pos=10
    res: FuncMoveAxisToOutput = stpmtr_emulate.move_axis_to(MOVE_AXIS1_absolute_ten)
    assert res.func_success
    assert res.axes[1].position == 10
    assert res.comments == f'Movement of Axis with id={1} was finished.'
    # Move axis 1 -10 steps
    res: FuncMoveAxisToOutput = stpmtr_emulate.move_axis_to(MOVE_AXIS1_relative_negative_ten)
    assert res.func_success
    assert res.axes[1].position == 0
    # Move axis 1 to pos=100 and stop it immediately

    def move() -> FuncMoveAxisToOutput:
        print('inside move')
        res: FuncMoveAxisToOutput = stpmtr_emulate.move_axis_to(MOVE_AXIS1_absolute_hundred)
        return res

    def stop() -> FuncStopAxisOutput:
        print('inside stop')
        from time import sleep
        sleep(1)
        res: FuncStopAxisOutput = stpmtr_emulate.stop_axis(STOP_AXIS1)
        return res

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_move = executor.submit(move)
        future_stop = executor.submit(stop)
        res_move: FuncMoveAxisToOutput = future_move.result()
        res_stop: FuncStopAxisOutput = future_stop.result()

    assert not res_move.func_success
    assert res_move.comments == f'Movement of Axis with id={1} was interrupted'
    assert res_move.axes[1].position > 0
    assert res_stop.func_success
    assert res_stop.comments == f'Axis {1} was stopped by user.'
    # move to 10
    res: FuncMoveAxisToOutput = stpmtr_emulate.move_axis_to(MOVE_AXIS1_absolute_ten)

    # Test get_pos
    res: FuncGetPosOutput = stpmtr_emulate.get_pos(GET_POS_AXIS1)
    assert res.func_success
    assert type(res.axes[1]) == AxisStpMtrEssentials
    assert res.axes[1].position == 10
    assert res.axes[2].position == 0
    assert res.comments == ''

    # Test get_contoller_state
    res: FuncGetStpMtrControllerStateOutput = stpmtr_emulate.get_controller_state(GET_CONTOLLER_STATE)
    assert res.func_success
    assert type(res.axes[1]) == AxisStpMtr

    # Test available function
    res = stpmtr_emulate.available_public_functions()
    assert type(res[0]) == CmdStruct
    assert len(res) == 7

    # Test available functions names
    res = stpmtr_emulate.available_public_functions_names
    acc = [True if name in available_functions_names else False for name in res]
    assert all(acc)

    # stop stpmtr_emulate device
    stpmtr_emulate.stop()
