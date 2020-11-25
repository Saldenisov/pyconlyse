from time import sleep
from tests.fixtures.services import *
from devices.datastruct_for_messaging import *
from devices.service_devices.stepmotors.datastruct_for_messaging import *
from devices.service_devices.stepmotors import StpMtrController, StpMtrCtrl_TopDirect_1axis, StpMtrCtrl_OWIS
from utilities.datastructures.mes_independent.general import CmdStruct


one_service = [stpmtr_OWIS_test_non_fixture()]
#all_services = [stpmtr_a4988_4axes_test_non_fixture(), stpmtr_emulate_test_non_fixture(), stpmtr_Standa_test_non_fixture(), stpmtr_TopDirect_test_non_fixture()]
test_param = one_service


@pytest.mark.parametrize('stpmtr', test_param)
def test_func_stpmtr(stpmtr: StpMtrController):
    stpmtr.start()
    available_functions_names = ['activate', 'power', 'get_controller_state', 'activate_device', 'get_pos_axis',
                                 'move_axis_to', 'stop_axis', 'service_info', 'set_pos_axis']
    ACTIVATE = FuncActivateInput(flag=True)
    DEACTIVATE = FuncActivateInput(flag=False)
    POWER_ON = FuncPowerInput(flag=True)
    POWER_OFF = FuncPowerInput(flag=False)
    # Testing Power function
    # power On
    res: FuncPowerOutput = stpmtr.power(POWER_ON)
    assert type(res) == FuncPowerOutput
    assert res.func_success
    try:
        assert stpmtr.ctrl_status.power
    except AssertionError:
        print('Power On did not work')
        stpmtr.ctrl_status.power = True
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

    ACTIVATE_AXIS1 = FuncActivateDeviceInput(device_id=first_axis, flag=1)
    DEACTIVATE_AXIS1 = FuncActivateDeviceInput(device_id=first_axis,  flag=0)
    GET_POS_AXIS1 = FuncGetPosInput(axis_id=first_axis)
    GET_CONTOLLER_STATE = FuncGetStpMtrControllerStateInput()
    if isinstance(stpmtr, StpMtrCtrl_Standa):
        mult = 3.9
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
    assert not res.controller_status.active
    # power off
    res: FuncPowerOutput = stpmtr.power(POWER_OFF)
    assert res.func_success

    try:
        assert not stpmtr.ctrl_status.power
    except AssertionError:
        print('Power Off did not work')
        stpmtr.ctrl_status.power = False

    # activate when device power is Off
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
    assert not res.func_success
    assert not res.controller_status.active

    # Test Activate axis, for example with id=1
    res: FuncPowerOutput = stpmtr.power(POWER_ON)  # power is On
    try:
        assert stpmtr.ctrl_status.power
    except AssertionError:
        print('Power On did not work')
        stpmtr.ctrl_status.power = True
    sleep(0.2)
    res: FuncActivateOutput = stpmtr.activate(ACTIVATE)  # activate device
    assert stpmtr.ctrl_status.active
    # activate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_device(ACTIVATE_AXIS1)
    assert res.func_success
    assert stpmtr.axes_stpmtr[first_axis].status == 1

    # Test set_pos_axis
    pos_var = stpmtr.axes_stpmtr[1].position
    if isinstance(stpmtr, StpMtrCtrl_OWIS):
        type_move = MoveType.mm
    else:
        type_move = MoveType.step

    input = FuncSetPosInput(1, 10.50, type_move)
    res: FuncSetPosOutput = stpmtr.set_pos_axis(input)
    assert res.func_success
    res: FuncGetPosOutput = stpmtr.get_pos_axis(GET_POS_AXIS1)
    assert res.func_success
    pos = res.axis.convert_pos_to_unit(type_move)
    assert pos / 10.5 < 1.01
    res: FuncSetPosOutput = stpmtr.set_pos_axis(FuncSetPosInput(1, pos_var, stpmtr.axes_stpmtr[1].basic_unit))
    assert stpmtr.axes_stpmtr[1].position == pos_var

    # deactivate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_device(DEACTIVATE_AXIS1)
    assert res.func_success

    # activate axis 1
    res: FuncActivateDeviceOutput = stpmtr.activate_device(ACTIVATE_AXIS1)

    if not isinstance(stpmtr, StpMtrCtrl_Standa) and not isinstance(stpmtr, StpMtrCtrl_OWIS):
        # deactivate controller
        res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)
        assert stpmtr.axes_stpmtr[first_axis].status == 0

        # activate axis 1
        res: FuncActivateDeviceOutput = stpmtr.activate_device(DEACTIVATE_AXIS1)
        assert res.func_success
        # activate controller
        res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
        # activate axis 1
        res: FuncActivateDeviceOutput = stpmtr.activate_device(ACTIVATE_AXIS1)
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

    res: FuncActivateDeviceOutput = stpmtr.activate_device(ACTIVATE_AXIS1)
    stpmtr.axes_stpmtr[first_axis].status = 2


    # Test StopAxis function
    # axis 1 status has been set to 2 already.
    # stop axis 1
    if not isinstance(stpmtr, StpMtrCtrl_TopDirect_1axis):
        # Stpmtr_TopDirect cannot be stopped by user.
        res: FuncStopAxisOutput = stpmtr.stop_axis(STOP_AXIS1)
        assert res.func_success
        assert res.comments == f'Axis id={first_axis}, name={stpmtr.axes_stpmtr[first_axis].friendly_name} was stopped by user.'
        assert res.axis == stpmtr.axes_stpmtr[first_axis]
        assert res.axis.status == 1
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
        assert res_move.comments == f'Movement of Axis with id={first_axis} was interrupted.'
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

        # Move back to initial position
        res: FuncMoveAxisToOutput = stpmtr.move_axis_to(FuncMoveAxisToInput(axis_id=1, pos=pos_var, how='absolute',
                                                                            move_type=type_move))
        assert res.func_success

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


@pytest.mark.parametrize('stpmtr', test_param)
def test_short_func_stpmtr(stpmtr: StpMtrController):
    stpmtr.start()
    first_axis = list(stpmtr.axes_stpmtr.keys())[0]


    def func(first_axis):
        ACTIVATE = FuncActivateInput(flag=True)
        DEACTIVATE = FuncActivateInput(flag=False)
        ACTIVATE_AXIS1 = FuncActivateDeviceInput(device_id=first_axis, flag=1)
        MOVE_AXIS1_absolute_ten = FuncMoveAxisToInput(axis_id=first_axis, pos=10, how=absolute.__name__)
        POWER_ON = FuncPowerInput(flag=True)

        res: FuncPowerOutput = stpmtr.power(POWER_ON)
        assert type(res) == FuncPowerOutput
        assert res.func_success
        try:
            assert stpmtr.ctrl_status.power
        except AssertionError:
            print('Power On did not work')
            stpmtr.ctrl_status.power = True
        res: FuncActivateOutput = stpmtr.activate(ACTIVATE)
        assert res.func_success

        # activate axis 1
        res: FuncActivateDeviceOutput = stpmtr.activate_device(ACTIVATE_AXIS1)
        assert res.func_success
        assert stpmtr.axes_stpmtr[first_axis].status == 1

        if isinstance(stpmtr, StpMtrCtrl_TopDirect_1axis):
            top_direct_test_arduino_communication(stpmtr)

        if isinstance(stpmtr, StpMtrCtrl_Standa):
            mult = 1
            sleep_time = 0.15
        else:
            mult = 1
            sleep_time = 1

        MOVE_AXIS1_absolute_ten = FuncMoveAxisToInput(axis_id=first_axis, pos=10 * mult, how=absolute.__name__)
        MOVE_AXIS1_relative_negative_ten = FuncMoveAxisToInput(axis_id=first_axis, pos=-10 * mult,
                                                               how=relative.__name__)
        # Test Move_axis1
        # Move axis 1 to pos=10
        res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_absolute_ten)
        assert res.func_success
        assert res.axis.position == MOVE_AXIS1_absolute_ten.pos
        # Move axis 1 -10 steps
        res: FuncMoveAxisToOutput = stpmtr.move_axis_to(MOVE_AXIS1_relative_negative_ten)
        assert res.func_success
        assert res.axis.position == MOVE_AXIS1_absolute_ten.pos + MOVE_AXIS1_relative_negative_ten.pos

        res: FuncActivateOutput = stpmtr.activate(DEACTIVATE)

    for axis in list(stpmtr.axes_stpmtr.keys()):
        func(axis)
    stpmtr.stop()


def top_direct_test_arduino_communication(stpmtr: StpMtrCtrl_TopDirect_1axis):
    # checking messaging with Arduino
    first_axis = list(stpmtr.axes_stpmtr.keys())[0]
    get = stpmtr._get_reply_from_arduino(device_id=first_axis)
    assert get == None
    stpmtr._send_to_arduino(first_axis, cmd='GET STATE')
    get = stpmtr._get_reply_from_arduino(first_axis, True)
    assert get[0] == 'READY'
    assert get[1] == 0

    stpmtr._send_to_arduino(first_axis, cmd='SET STATE 1')
    get = stpmtr._get_reply_from_arduino(first_axis)
    assert get == 0

    stpmtr._send_to_arduino(first_axis, cmd='GET STATE')
    get = stpmtr._get_reply_from_arduino(first_axis, True)
    assert get[0] == 'READY'
    assert get[1] == 0

    stpmtr._send_to_arduino(first_axis, cmd='GET S')
    get = stpmtr._get_reply_from_arduino(first_axis, True)
    assert get[0] == -2

    stpmtr._send_to_arduino(first_axis, cmd='MOVE ABS 205')
    get = stpmtr._get_reply_from_arduino(first_axis)
    assert get == -1

    stpmtr._send_to_arduino(first_axis, cmd='MOVE ABS 10')
    get = stpmtr._get_reply_from_arduino(first_axis)
    assert get == 'STARTED'
    get = stpmtr._get_reply_from_arduino(first_axis)
    assert get == None
    sleep(3)
    get = stpmtr._get_reply_from_arduino(first_axis)
    assert get == 0

    stpmtr._send_to_arduino(first_axis, cmd='GET POS')
    get = stpmtr._get_reply_from_arduino(first_axis, True)
    assert get[0] == 10.0
    assert get[1] == 0

    stpmtr._send_to_arduino(first_axis, cmd='MOVE ABS 0')
    sleep(1)