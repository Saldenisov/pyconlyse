from time import sleep
from tests.fixtures.services import *
from devices.datastruct_for_messaging import *
from devices.service_devices.stepmotors.datastruct_for_messaging import *
from devices.service_devices.stepmotors import StpMtrController
from utilities.datastructures.mes_independent.general import CmdStruct


one_service = [stpmtr_Standa_test_non_fixture()]
#all_services = [stpmtr_a4988_4axes_test_non_fixture(), stpmtr_emulate_test_non_fixture(), stpmtr_Standa_test_non_fixture(), stpmtr_TopDirect_test_non_fixture()]
test_param = one_service


@pytest.mark.parametrize('stpmtr', test_param)
def test_func_stpmtr(stpmtr: StpMtrController):
    stpmtr.start()
    test_comm_arduino = False
    if isinstance(stpmtr, StpMtrCtrl_TopDirect_1axis) and test_comm_arduino:
        stpmtr: StpMtrCtrl_TopDirect_1axis = stpmtr
        stpmtr.ctrl_status.power = True
        # checking messaging with Arduino
        res, comments = stpmtr._connect(True)
        if res:
            get = stpmtr._get_reply_from_arduino()
            assert get == None
            stpmtr._send_to_arduino(cmd='GET STATE')
            get = stpmtr._get_reply_from_arduino(True)
            assert get[0] == 'NOT_ACTIVE'
            assert get[1] == 0

            stpmtr._send_to_arduino(cmd='SET STATE 1')
            get = stpmtr._get_reply_from_arduino()
            assert get == 0

            stpmtr._send_to_arduino(cmd='GET STATE')
            get = stpmtr._get_reply_from_arduino(True)
            assert get[0] == 'READY'
            assert get[1] == 0

            stpmtr._send_to_arduino(cmd='GET S')
            get = stpmtr._get_reply_from_arduino(True)
            assert get[0] == -2

            stpmtr._send_to_arduino(cmd='MOVE ABS 205')
            get = stpmtr._get_reply_from_arduino()
            assert get == -1

            stpmtr._send_to_arduino(cmd='MOVE ABS 10')
            get = stpmtr._get_reply_from_arduino()
            assert get == 'STARTED'
            get = stpmtr._get_reply_from_arduino()
            assert get == None
            sleep(3)
            get = stpmtr._get_reply_from_arduino()
            assert get == 0

            stpmtr._send_to_arduino(cmd='GET POS')
            get = stpmtr._get_reply_from_arduino(True)
            assert get[0] == 10.0
            assert get[1] == 0

            stpmtr._send_to_arduino(cmd='MOVE ABS 0')
            sleep(5)
            stpmtr._connect(False)

    available_functions_names = ['activate', 'power', 'get_controller_state', 'activate_axis', 'get_pos_axis', 'move_axis_to',
                                 'stop_axis', 'service_info', 'set_pos_axis']
    ACTIVATE = FuncActivateInput(flag=True)
    DEACTIVATE = FuncActivateInput(flag=False)
    POWER_ON = FuncPowerInput(flag=True)
    POWER_OFF = FuncPowerInput(flag=False)
    # Testing Power function
    # power On
    res: FuncPowerOutput = stpmtr.power(POWER_ON)
    assert type(res) == FuncPowerOutput
    assert res.func_success
    assert res.controller_status.power
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
    assert res.controller_status.active

    first_axis = list(stpmtr.axes_stpmtr.keys())[0]
    second_axis = list(stpmtr.axes_stpmtr.keys())[1]

    ACTIVATE_AXIS1 = FuncActivateDeviceInput(axis_id=first_axis, flag=1)
    DEACTIVATE_AXIS1 = FuncActivateDeviceInput(axis_id=first_axis,  flag=0)
    GET_POS_AXIS1 = FuncGetPosInput(axis_id=first_axis)
    GET_CONTOLLER_STATE = FuncGetStpMtrControllerStateInput()
    if isinstance(stpmtr, StpMtrCtrl_Standa):
        mult = 1
        sleep_time = 0.15
    else:
        mult = 1
        sleep_time = 1
    MOVE_AXIS1_absolute_ten = FuncMoveAxisToInput(axis_id=first_axis, pos=10 * mult, how=absolute.__name__)
    MOVE_AXIS1_absolute_fifty = FuncMoveAxisToInput(axis_id=first_axis, pos=50 * mult, how=absolute.__name__)
    MOVE_AXIS1_relative_ten = FuncMoveAxisToInput(axis_id=first_axis,  pos=10 * mult, how=relative.__name__)
    MOVE_AXIS1_relative_negative_ten = FuncMoveAxisToInput(axis_id=first_axis,  pos=-10 * mult, how=relative.__name__)
    STOP_AXIS1 = FuncStopAxisInput(axis_id=first_axis)

    # activate for a second time
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    assert res.func_success
    assert res.controller_status.active

    # deactivate
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert res.func_success
    assert not res.controller_status.active
    # deactivate for a second time
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert not res.func_success
    assert not res.controller_status.active
    # power off
    res: FuncPowerOutput = stpmtr.power(POWER_OFF)
    assert res.func_success
    assert not res.controller_status.power
    # activate when device power is Off
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    assert not res.func_success
    assert not res.controller_status.active

    # Test Activate axis, for example with id=1
    res: FuncPowerOutput = stpmtr.power(POWER_ON)  # power is On
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)  # activate device
    # activate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    assert res.func_success
    essentials = stpmtr.axes_stpmtr_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert f'Axes status: {status}. ' in res.comments
    assert stpmtr.axes_stpmtr[first_axis].status == 1

    # Test set_pos_axis
    pos_var = stpmtr.axes_stpmtr[1].position
    input = FuncSetPosInput(1, 100.50, MoveType.step)
    res: FuncSetPosOutput = stpmtr.set_pos_axis(input)
    assert res.func_success
    res: FuncGetPosOutput = stpmtr.get_pos_axis(GET_POS_AXIS1)
    assert res.func_success
    assert res.axis.position == 100.5
    res: FuncSetPosOutput = stpmtr.set_pos_axis(FuncSetPosInput(1, pos_var, MoveType.step))
    assert stpmtr.axes_stpmtr[1].position == pos_var

    # deactivate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_axis(DEACTIVATE_AXIS1)
    assert res.func_success
    essentials = stpmtr.axes_stpmtr_essentials
    status = []
    for key, axis in essentials.items():
        status.append(essentials[key].status)
    assert f'Axes status: {status}. ' in res.comments

    # activate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    # deactivate controller
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert stpmtr.axes_stpmtr[first_axis].status == 0

    # activate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_axis(DEACTIVATE_AXIS1)
    assert res.func_success
    # activate controller
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    # activate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    # set axis 1 status to 1
    axis_one = stpmtr.axes_stpmtr[first_axis]
    axis_one.status = 1
    # deactivate controller when all axis are not running
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert res.func_success
    assert not stpmtr.ctrl_status.active
    assert not stpmtr.ctrl_status.connected
    # activate controller and activate axis 1, set it status to 2
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    res: FuncActivateDeviceOutput = stpmtr.activate_axis(ACTIVATE_AXIS1)
    stpmtr.axes_stpmtr[first_axis].status = 2
    # deactivate controller when Not all axis are not running
    res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
    assert not res.func_success
    assert stpmtr.ctrl_status.active
    assert stpmtr.ctrl_status.connected
    assert stpmtr.ctrl_status.power

    # Test StopAxis function
    # axis 1 status has been set to 2 already.
    # stop axis 1
    if not isinstance(stpmtr, StpMtrCtrl_TopDirect_1axis):
        # Stpmtr_TopDirect cannot be stopped by user.
        res: FuncStopAxisOutput = stpmtr.stop_axis(STOP_AXIS1)
        assert res.func_success
        assert res.comments == f'Axis id={first_axis}, name={stpmtr.axes_stpmtr[first_axis].friendly_name} was stopped by user.'
        assert res.axis == stpmtr.axes_stpmtr[first_axis]
        # stop axis 1 again
        res: FuncStopAxisOutput = stpmtr.stop_axis(STOP_AXIS1)
        assert res.func_success
        assert res.comments == f'Axis id={first_axis}, name={stpmtr.axes_stpmtr[first_axis].friendly_name} was already stopped.'
    else:
        stpmtr.axes_stpmtr[first_axis].status = 1

    # Test Move_axis1
    # Move axis 1 to pos=10
    res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_absolute_ten)
    assert res.func_success
    assert res.axis.position == MOVE_AXIS1_absolute_ten.pos
    assert res.comments == f'Movement of Axis with id={first_axis}, ' \
                           f'name={stpmtr.axes_stpmtr[first_axis].friendly_name} was finished.'
    # Move axis 1 -10 steps
    res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_relative_negative_ten)
    assert res.func_success
    assert res.axis.position == MOVE_AXIS1_absolute_ten.pos + MOVE_AXIS1_relative_negative_ten.pos

    if not isinstance(stpmtr, StpMtrCtrl_TopDirect_1axis):
        # Move axis 1 to pos=100 and stop it immediately

        def move() -> FuncMoveAxisToOutput:
            res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_absolute_fifty)
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
        assert res_move.comments == f'Movement of Axis with id={first_axis} was interrupted'
        assert res_move.axis.position != 0
        assert res_stop.func_success
        assert res_stop.comments == f'Axis id={first_axis}, name={stpmtr.axes_stpmtr[first_axis].friendly_name} ' \
                                    f'was stopped by user.'
        # move to 10
        res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_absolute_ten)

        # Test get_pos
        res: FuncGetPosOutput = stpmtr.get_pos_axis(GET_POS_AXIS1)
        assert res.func_success
        assert res.axis.position == MOVE_AXIS1_absolute_ten.pos
        assert res.comments == ''

    # Test get_contoller_state
    res: FuncGetControllerStateOutput = stpmtr.get_controller_state(GET_CONTOLLER_STATE)
    assert res.func_success
    assert isinstance(res.devices_hardware[first_axis], AxisStpMtr)

    # Test available function
    res = stpmtr.available_public_functions()
    assert isinstance(res[0], CmdStruct)
    assert len(res) == 9

    # Test available functions names
    res = stpmtr.available_public_functions_names
    acc = [True if name in available_functions_names else False for name in res]
    assert all(acc)

    # stop stpmtr_emulate device
    stpmtr.stop()
