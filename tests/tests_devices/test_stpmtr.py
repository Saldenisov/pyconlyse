from devices.service_devices.stepmotors import (StpMtrCtrl_emulate, StpMtrCtrl_a4988_4axes, StpMtrController,
                                                StpMtrCtrl_Standa)
from datastructures.mes_independent.devices_dataclass import *
from datastructures.mes_independent.stpmtr_dataclass import *

from tests.fixtures.services import (stpmtr_emulate_test_non_fixture, stpmtr_a4988_4axes_test_non_fixture,
                                     stpmtr_Standa_test_non_fixture, stpmtr_TopDirect_test_non_fixture)

import pytest

one_service = [stpmtr_TopDirect_test_non_fixture()]
#all_services = [stpmtr_a4988_4axes_test_non_fixture(), stpmtr_emulate_test_non_fixture(), stpmtr_Standa_test_non_fixture(), stpmtr_TopDirect_test_non_fixture()]
test_param = one_service


@pytest.mark.parametrize('stpmtr', test_param)
def test_func_stpmtr(stpmtr: StpMtrController):
    stpmtr.start()
    available_functions_names = ['activate', 'power', 'get_controller_state', 'activate_axis', 'get_pos', 'move_axis_to',
                                 'stop_axis', 'service_info']
    ACTIVATE = FuncActivateInput(flag=True)
    DEACTIVATE = FuncActivateInput(flag=False)
    ACTIVATE_AXIS1 = FuncActivateAxisInput(axis_id=1, flag=True)
    DEACTIVATE_AXIS1 = FuncActivateAxisInput(axis_id=1,  flag=False)
    GET_POS_AXIS1 = FuncGetPosInput(axis_id=1)
    GET_CONTOLLER_STATE = FuncGetStpMtrControllerStateInput()
    if isinstance(stpmtr, StpMtrCtrl_Standa):
        mult = 10000
        sleep_time = 0.1
    else:
        mult = 1
        sleep_time = 1
    MOVE_AXIS1_absolute_ten = FuncMoveAxisToInput(axis_id=1, pos=10 * mult, how=absolute.__name__)
    MOVE_AXIS1_absolute_hundred = FuncMoveAxisToInput(axis_id=1,  pos=100 * mult, how=absolute.__name__)
    MOVE_AXIS1_relative_ten = FuncMoveAxisToInput(axis_id=1,  pos=10 * mult, how=relative.__name__)
    MOVE_AXIS1_relative_negative_ten = FuncMoveAxisToInput(axis_id=1,  pos=-10 * mult, how=relative.__name__)
    STOP_AXIS1 = FuncStopAxisInput(axis_id=1)
    POWER_ON = FuncPowerInput(flag=True)
    POWER_OFF = FuncPowerInput(flag=False)
    # Testing Power function
    # power On
    res: FuncPowerOutput = stpmtr.power(POWER_ON)
    assert type(res) == FuncPowerOutput
    assert res.func_success
    assert res.device_status.power
    # power off when device is active
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    assert res.func_success
    res: FuncPowerOutput = stpmtr.power(POWER_OFF)
    assert not res.func_success
    assert 'Cannot switch power off when device is activated.' in res.comments
    
    # Testing Activate function
    # activate
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    assert type(res) == FuncActivateOutput
    assert res.func_success
    assert res.device_status.active
    # activate for a second time
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    assert res.func_success
    assert res.device_status.active
    # deactivate
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert res.func_success
    assert not res.device_status.active
    # deactivate for a second time
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert not res.func_success
    assert not res.device_status.active
    # power off
    res: FuncPowerOutput = stpmtr.power(POWER_OFF)
    assert res.func_success
    assert not res.device_status.power
    # activate when device power is Off
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    assert not res.func_success
    assert not res.device_status.active

    # Test Activate axis, for example with id=1
    res: FuncPowerOutput = stpmtr.power(POWER_ON)  # power is On
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)  # activate device
    # activate axis 1
    res: FuncActivateAxisOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    assert res.func_success
    essentials = stpmtr.axes_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert f'Axes status: {status}. ' in res.comments
    assert stpmtr.axes[1].status == 1
    # deactivate axis 1
    res: FuncActivateAxisOutput = stpmtr.activate_axis(DEACTIVATE_AXIS1)
    assert res.func_success
    essentials = stpmtr.axes_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert f'Axes status: {status}. ' in res.comments

    # activate axis 1
    res: FuncActivateAxisOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    # deactivate controller
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert stpmtr.axes[1].status == 0

    # activate axis 1
    res: FuncActivateAxisOutput = stpmtr.activate_axis(DEACTIVATE_AXIS1)
    assert not res.func_success
    # activate controller
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    # activate axis 1
    res: FuncActivateAxisOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    # set axis 1 status to 1
    axis_one = stpmtr.axes[1]
    axis_one.status = 1
    # deactivate controller when all axis are not running
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert res.func_success
    assert not stpmtr.device_status.active
    assert not stpmtr.device_status.connected
    # activate controller and activate axis 1, set it status to 2
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    res: FuncActivateAxisOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    stpmtr.axes[1].status = 2
    # deactivate controller when Not all axis are not running
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert not res.func_success
    assert stpmtr.device_status.active
    assert stpmtr.device_status.connected
    assert stpmtr.device_status.power

    # Test StopAxis function
    # axis 1 status has been set to 2 already.
    # stop axis 1
    if not isinstance(stpmtr, stpmtr_TopDirect_test_non_fixture()):
        # Stpmtr_TopDirect cannot be stopped by user.
        res: FuncStopAxisOutput = stpmtr.stop_axis(STOP_AXIS1)
        assert res.func_success
        assert res.comments == f'Axis id={1}, name={stpmtr.axes[1].name} was stopped by user.'
        assert res.axes == stpmtr.axes_essentials
        # stop axis 1 again
        res: FuncStopAxisOutput = stpmtr.stop_axis(STOP_AXIS1)
        assert res.func_success
        assert res.comments == f'Axis id={1}, name={stpmtr.axes[1].name} was already stopped.'

    # Test Move_axis1
    # Move axis 1 to pos=10
    res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_absolute_ten)
    assert res.func_success
    assert res.axes[1].position == MOVE_AXIS1_absolute_ten.pos
    assert res.comments == f'Movement of Axis with id={1}, name={stpmtr.axes[1].name} was finished.'
    # Move axis 1 -10 steps
    res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_relative_negative_ten)
    assert res.func_success
    assert res.axes[1].position == MOVE_AXIS1_absolute_ten.pos + MOVE_AXIS1_relative_negative_ten.pos
    # Move axis 1 to pos=100 and stop it immediately

    def move() -> FuncMoveAxisToOutput:
        res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_absolute_hundred)
        return res

    def stop() -> FuncStopAxisOutput:
        from time import sleep
        sleep(sleep_time)
        res: FuncStopAxisOutput = stpmtr.stop_axis(STOP_AXIS1)
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
    assert res_stop.comments == f'Axis id={1}, name={stpmtr.axes[1].name} was stopped by user.'
    # move to 10
    res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_absolute_ten)

    # Test get_pos
    res: FuncGetPosOutput = stpmtr.get_pos(GET_POS_AXIS1)
    assert res.func_success
    assert type(res.axes[1]) == AxisStpMtrEssentials
    assert res.axes[1].position == MOVE_AXIS1_absolute_ten.pos
    assert res.axes[2].position == 0
    assert res.comments == ''

    # Test get_contoller_state
    res: FuncGetStpMtrControllerStateOutput = stpmtr.get_controller_state(GET_CONTOLLER_STATE)
    assert res.func_success
    assert type(res.axes[1]) == AxisStpMtr

    # Test available function
    res = stpmtr.available_public_functions()
    assert isinstance(res[0], CmdStruct)
    assert len(res) == 8

    # Test available functions names
    res = stpmtr.available_public_functions_names
    acc = [True if name in available_functions_names else False for name in res]
    assert all(acc)

    # stop stpmtr_emulate device

    stpmtr.stop()
