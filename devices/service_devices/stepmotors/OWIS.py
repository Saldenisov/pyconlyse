"""
This controller is dedicated to control OWIS PS90 controller hardware
On ELYSE there are 3 cards dedicated to delaylines
"""


from typing import List, Tuple, Union, Iterable, Dict, Any, Callable

import logging
import ctypes
from time import sleep
from utilities.tools.decorators import development_mode
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


dev_mode = False


class StpMtrCtrl_OWIS(StpMtrController):
    #TODO: should be checked with dev_mode False and True
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._PS90: ctypes.WinDLL = None

    def _activate_axis(self, axis: int) -> Tuple[bool, str]:
        """
        Init, Set Stage Attributes, Pos mode set, Target mode set,  Free switch, Motor off
        :param axis: 1-n
        :return: True/False, comments
        """
        res, comments = self._check_axis_range(axis)
        if res:
            res, comments = self._motor_init_ps90(1, axis)
            if res:
                #TODO check parameters
                res, comments = self._set_stage_attributes_ps90(1, axis)
            if res:
                res, comments = self._set_pos_mode_ps90(1, axis, mode=0)
            if res:
                res, comments = self._set_target_mode_ps90(1, axis, mode=1)
            if res:
                res, comments = self._free_switch_ps90(1, axis)
            if res:
                res, comments = self._motor_off_ps90(1, axis)
            if res:
                res, comments = res, f'Axis {axis} pos_mode is 0, target_mode is 1, switch if free, motor is off.'
        return res, comments

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        if self.device_status.power:
            if flag:
                res, comments = self._connect_ps90(1, self._interface, self._port, self._baudrate)
                if not res:
                    res, comments = self._connect_simple_ps90(1)
            else:
                res, comments = self._disconnect_ps90(1)
            if res:
                self.device_status.connected = flag
            return res, comments
        else:
            return False, f'Power is off, connect to controller function cannot be called with flag {flag}'

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        """
        Changes axis status on software/hardware level
        :param axis_id: 0-n
        :param flag: 0, 1, 2
        :param force: is not needed for this controller
        :return: res, comments='' if True, else error_message
        """
        res, comments = super()._check_axis_flag(flag)
        if res:
            if self._axes_status[axis_id] != flag:
                local_axis_state = self._axes_status[axis_id]
                if self._axes_status[axis_id] == 0:
                    res, comments = self._activate_axis(axis_id)
                else:
                    self._axes_status[axis_id] = flag
                    res, comments = True, ''
                if flag == 2:
                    res, comments = self._motor_on_ps90(1, axis_id)
                elif (flag == 0 or flag == 1) and local_axis_state == 2:
                    _, info = self._stop_axis_ps90(1, axis_id)
                    res, comments = self._motor_off_ps90(1, axis_id)
                    res, comments = res, f'{info}. {comments}'
                if res:
                    res, comments = res, f'Axis {axis_id} is set to {flag}. {comments}'
            else:
                res, comments = True, f'Axis {axis_id} is already set to {flag}'

        return res, comments

    def GUI_bounds(self) -> Dict[str, Any]:
        pass

    def _get_axes_status(self) -> List[int]:
        for axis_id in range(self._axes_number):
            pass

    def _get_number_axes(self) -> int:
        return self._get_number_axes_db()

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._get_limits_db()

    def _get_positions(self) -> List[Union[int, float]]:
        pass

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._get_preset_values_db()

    def _move_axis_to(self, axis_id: int, go_pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        """
        Move selected axis to set position. Turns on motor, set target, go target and checks position every 25ms for
        1000 cycles. Motor off when position is within 0.001mm accuracy
        :param axis_id: 1-n
        :param go_pos: position in mm
        :param how: absolute, relative
        :return: True/False, comments
        """
        res, comments = self._change_axis_status(axis_id, 2)
        if res:
            res, comments = self._set_target_ex_ps90(1, axis_id, go_pos)
            if res:
                res, comments = self._go_target_ps90(1, axis_id)
            if res:
                for i in range(1000):
                    sleep(50. / 1000)
                    res, comments = self._get_position_ex_ps90(1, axis_id)
                    if not res:
                        pass
                    else:
                        self._pos[axis_id] = res
                    if abs(res - go_pos) <= 0.001:
                        res, comments = True, f'Axis {axis_id} is stopped. Actual position is {res}'
                        break
                    if i == 999:
                        res, comments = False, f'Waited for to long axis {axis_id} to stop. ' \
                                              f'Last position was {self._pos[axis_id]}. Motor is Off'
                        break
                    _, _ = self._change_axis_status(axis_id, 1)
        return res, comments

    def _setup(self) -> Tuple[Union[bool, str]]:
        """
        essential parameters for controller operation are read from database
        :return: bool, comment
        """
        # TODO: not all parameters are set
        try:
            list_param = ['DLL_path', 'interface', 'baudrate', 'com_port', 'speeds', 'gear_ratios', 'pitches']
            settings = self.get_general_settings()
            for param in list_param:
                if param not in settings:
                    raise KeyError(f'{param} is not found in database.')
            self._DLpath = settings['DLL_path']
            self._PS90 = ctypes.WinDLL(self._DLpath)
            self._interface = int(settings['interface'])
            self._baudrate = int(settings['baudrate'])
            self._port = int(settings['com_port'])
            self._axes_speeds: List[float] = self._get_list_db("Parameters", 'speeds', float)
            self._axes_gear_ratios: List[int] = self._get_list_db("Parameters", 'gear_ratios', int)
            return True, ''
        except KeyError as e:
            return False, f"_setup did not work; {e}"

    def _set_i_know_how(self):
        self.i_know_how = {'mm': 1, 'steps': 0}

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        if not self.device_status.connected:
            return super()._set_parameters(extra_func=[self._setup])
        else:
            return super()._set_parameters()

    # Hardware controller functions
    # Be aware that OWIS PS90 counts axis from 1, not from 0!!!
    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _connect_ps90(self, control_unit: int, interface: int, port: int, baudrate: int,
                 par3=0, par4=0, par5=0, par6=0) -> Tuple[Union[bool, str]]:
        """
        long PS90_Connect (long Index, long Interface, long p1, long p2, long p3, long p4, long p5, long p6)
        Description
        open interface and connect to PS 90. Serial interface (communication via USB or serial com_port)
        The application software can access this interface in the same way as it would access a standard serial com_port (COM). The parameters for Baudrate, Parity, Databits and Stopbits are predefined (9600, no parity, 8 databits, 1 stopbit).
        Example
        Open COM3 and connect to PS 90 (Index=1):
        long error = PS90_Connect(1, 0, 3, 9600, 0, 0, 0, 0);
        :param control_unit: Index control unit index 1–10 (default=1, range=1...20)  11...20 – debug mode 1...10 – standard mode
        :param interface: Interface define interface (default=0) USB or serial com_port (=0)
        :param com_port or p1: p1 define COM com_port (default=1 – COM1, range=0...255)
        :param baudrate or p2: p2 define request mode for communication (default=9600) 115200 – fast read (all bytes, fast check) 19200 – fast read (all bytes, slow check)  9600* – standard read (byte-by-byte)
        :param par3: p3 define delay value (=20+x) for serial communication (default=20 ms)
        :param par4: p4 system value (default=0) 10 – without check 0* – with check (firmware, terminal mode, clear error)
        :param par5: p5 system value (default=0) 10 – with com_port flush  0* – without com_port flush
        :param par6: p6 system value (default=0) 5 – reconnect for every message  0* – without reconnect

        :return: 0 – function was successful 1...9 – error
        1 function error (invalid parameters)
        3 invalid serial com_port (com_port is not found)
        4 access react_denied (com_port is busy)
        5 no response from control unit (check cable, connection or reset control unit)
        8 no connection to modbus/tcp
        9 no connection to tcp/ip socket
        """
        control_unit = ctypes.c_long(control_unit)
        interface = ctypes.c_long(interface)
        port = ctypes.c_long(port)
        baudrate = ctypes.c_long(baudrate)
        par3 = ctypes.c_long(par3)
        par4 = ctypes.c_long(par4)
        par5 = ctypes.c_long(par5)
        par6 = ctypes.c_long(par6)
        res = self._PS90.PS90_Connect(control_unit, interface, port,
                                      baudrate, par3, par4, par5, par6) * -1  # *-1 is according official documentation
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _connect_simple_ps90(self, control_unit: int, sernum = "") -> Tuple[Union[bool, str]]:
        """
        long PS90_SimpleConnect (long Index, const char* pszSerNum)
        Description
        find control unit with the specified serial number and connect to it.
        Serial interface (communication via USB or serial com_port)
        The application software can access this interface in the same way as it would access a standard serial com_port (COM). The parameters for Baudrate, Parity, Databits and Stopbits are predefined (9600, no parity, 8 databits, 1 stopbit).
        The software handshake character is CR.
        Ethernet interface (communication via Com-Server)
        As Com-Server the OWIS software tool “OWISerialServer.exe” may be used (..\OWISoft\Application\system). Alternatively, you can use other commercial products (hardware/software). The application software can access this interface via Windows TCP socket: special communication for OWIS software (command + delay). The software handshake character is CR.
        Example
        Find control unit and connect to it (empty string, COMx):
        long error = PS90_SimpleConnect(1, “”);
        :param control_unit: Index control unit index 1-10 (default=1, range=1...20)
                             11...20 – debug mode
                             1...10 – standard mode
        :param sernum: pszSerNum control unit serial number (default=empty string)
                       USB or serial com_port
                       empty string – the first found control unit is connected;
                       “12345678” – control unit with the specified serial number is connected;
                       Ethernet interface
                       “net” – control unit is connected to the Com-Server (local application) by the first found local IP address and com_port number 1200.
        :return: 0 – function was successful
                 1...9 – error
                 1 function error (invalid parameters)
                 5 no response from control unit (check cable, connection or reset control unit)
                 7 control unit with the specified serial number is not found
                 9 no connection to tcp/ip socket

        """
        control_unit = ctypes.c_long(control_unit)
        sernum = ctypes.c_char_p(sernum)

        res = self._PS90.PS90_SimpleConnect(control_unit, sernum) * -1  # *-1 is according official documentation
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    def _convert_axis_state_format_ps90(self, axis_state_OWIS: int) -> int:
        """
        Converts OWIS controller axis state to the used for stpmtr_contoller
        :param axis_state_OWIS: 0     axis is not active
                                1     axis is not initialized
                                2     axis is switched off
                                3     axis is active and initialized and switched on
        :return: 0 - axis is not initialized, 1 - is active
        """
        if axis_state_OWIS in [0, 1, 2]:
            return 0
        elif axis_state_OWIS ==3:
            return 1
        else:
            return 0

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _disconnect_ps90(self, control_unit: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_Disconnect (long Index)
        Description
        disconnect PS 90
        Example
        Disconnect a control unit (Index=1):
        long error = PS90_Disconnect(1);
        :param control_unit: Index control unit index (1-10)
        :return:  0 – function was successful -1 – function error

        """
        control_unit = ctypes.c_long(control_unit)
        res = self._PS90.PS90_Disconnect(control_unit)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _free_switch_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_FreeSwitch (long Index, long AxisId)
        Description
        release active limit switches of an axis.
        After an axis has driven into a limit switch, it can release a limit switch with this function. This is valid only for released axes. Besides, the direction of the movement is selected automatically, depending on whether a positive or negative limit switch is activated.
        Example
        Release active limit switches of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetLimitSwitch(1,1,15);
        error = PS90_SetLimitSwitchMode(1,1,15);
        long state = PS90_GetSwitchState(1,1);
        if( state & 15 ) error = PS90_FreeSwitch(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
                -4 – axis in wrong state
        """

        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        res = self._PS90.PS90_FreeSwitch(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(3, 'DEV MODE'))
    def _get_axis_state_ps90(self, control_unit: int, axis: int) -> Tuple[Union[int, bool, str]]:
        """
        long PS90_GetAxisState (long Index, long AxisId)
        Description
        read axis state
        Example
            Read axis state of the control unit (Index=1, Axis=1):
            long ready = PS90_GetAxisState(1,1);
            long error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId=0 read state of all axes AxisId=1...9 read state of an axis
        :return: AxisId Value Meaning
                 0      0     any axis is not active
                        1     any axis is not initialized
                        2     any axis is switch off
                        3     all axes are active and initialized and switched on
                1...9   0     axis is not active
                        1     axis is not initialized
                        2     axis is switched off
                        3     axis is active and initialized and switched on
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        res = self._PS90.PS90_GetAxisState(control_unit, axis)
        error = self.__get_read_error(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(0.0, 'DEV MODE'))
    def _get_position_ex_ps90(self, control_unit: int, axis: int) -> Tuple[Union[float, bool, str]]:
        """
        double PS90_GetPositionEx (long Index, long AxisId)
        Description
        read current value of a position counter of an axis (values in selected unit)
        Example
        Read current position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        double dValue = PS90_GetPositionEx(1,1);
        error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: value of the current position (values in selected unit) or False if error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        res = self._PS90.PS90_GetPositionEx(control_unit, axis)
        error = self.__get_read_error(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _go_target_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_GoTarget (long Index, long AxisId)
        Description
        start positioning of an axis.
        The axis goes to a new target position or a distance either in the trapezoidal or S-curve profile. This is valid only for released axes.
        Example
        Drive an axis of the control unit (Index=1, Axis=1) to a target in trapezoidal profile:
        long error = PS90_SetPosMode(1,1,0);
        error = PS90_SetTargetMode(1,1,1);
        error = PS90_SetTarget(1,1,0);
        error = PS90_GoTarget(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
                -4 – axis in wrong state
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        res = self._PS90.PS90_GoTarget(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def __get_read_error_ps90(self, control_unit: int) -> int:
        control_unit = ctypes.c_int(control_unit)
        return self._PS90.PS90_GetReadError(control_unit)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _motor_init_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_MotorInit (long Index, long AxisId)
        Description
        initialize an axis and switch on.
        With this function the axis is completely initialized and afterwards is with a current and with active positioning regulator. It must be executed after the turning on of the control unit, so that the axis can be moved afterwards with the commands REF, PGO, VGO etc. Before the following parameters must have been set: limit switch mask and polarity, start regulator parameters.
        Example
        Initialize an axis of the control unit (Index=1, Axis=1) and switch on:
        long error = PS90_MotorInit(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        res = self._PS90.PS90_MotorInit(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1, f'Motor of axis {axis - 1} is initialized')

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _motor_on_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_MotorOn (long Index, long AxisId)
        Description
        switch an axis on.
        With this function the axis, after the motor was switched off, is switched on again and afterwards is with a current and with active positioning regulator.
        Example
        Switch an axis of the control unit (Index=1, Axis=1) on:
        long error = PS90_MotorOff(1,1);
        error = PS90_MotorOn(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        res = self._PS90.PS90_MotorOn(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1, f'Motor of axis {axis - 1} is on.')

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _motor_off_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_MotorOff (long Index, long AxisId)
        Description
        switch an axis off.
        With this function the position regulator is deactivated and the power amplifier is switched off.
        Example
        Switch an axis of the control unit (Index=1, Axis=1) off:
        long error = PS90_MotorOff(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_int(axis + 1)
        res = self._PS90.PS90_MotorOff(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1, f'Motor of axis {axis - 1} is off.')

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _stop_axis_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_Stop (long Index, long AxisId)
        Description
        stop movement of an axis.
        Any active movement of an axis is terminated. The axis is stopped with the programmed brake ramp and stands still.
        Example
        Stop movement of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_Stop(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return:  0 – function was successful -1 – function error -2 – communication error -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        res = self._PS90.PS90_Stop(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1, f'Axis {axis} movement is stopped.')

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_limit_min_ps90(self, control_unit: int, axis: int, value: float) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetLimitMinEx (long Index, long AxisId, double dValue)
        Description
        set negative limit position of an axis (values in selected unit).
        This limit position is evaluated with moving in negative direction.

        Example
        Set negative limit position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetLimitMinEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue negative limit position (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        value = ctypes.c_double(value)
        res = self._PS90.PS90_SetLimitMinEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_limit_max_ps90(self, control_unit: int, axis: int, value: float) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetLimitMinEx (long Index, long AxisId, double dValue)
        Description
        set negative limit position of an axis (values in selected unit).
        This limit position is evaluated with moving in negative direction.

        Example
        Set positive limit position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetLimitMaxEx(1,1,50.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue negative limit position (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        value = ctypes.c_double(value)
        res = self._PS90.PS90_SetLimitMaxEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_pos_fex_ps90(self, control_unit: int, axis: int, speed: float) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetPosFEx (long Index, long AxisId, double dValue)
        Description
        set positioning velocity of an axis (values in selected unit).
        It is used for a trapezoidal and a S-curve profile.
        velocity = unit/s
        Example
        Set positioning velocity of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetPosFEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param speed: dValue positioning velocity (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        speed = ctypes.c_double(speed)
        res = self._PS90.PS90_SetPosFEx(control_unit, axis, speed)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_pos_mode_ps90(self, control_unit: int, axis: int, mode: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetPosMode (long Index, long AxisId, long Mode)
        Description
        set positioning mode of an axis
        Example
        Set positioning mode of an axis of the control unit (Index=1, Axis=1, trapezoidal profile):
        long error = PS90_SetPosMode(1,1,0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param mode: Mode positioning mode Mode=0 trapezoidal profile Mode=1 S-curve profile
        :return: 0 – function was successful -1 – function error -2 – communication error -3 – syntax error
        """
        control_unit = ctypes.c_int(control_unit)
        axis = ctypes.c_long(axis + 1)
        mode = ctypes.c_long(mode)
        res = self._PS90.PS90_SetPosMode(control_unit, axis, mode)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_pos_velocity_ps90(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetPosVel (long Index, long AxisId, long Value)
        Description
        set positioning velocity of an axis (internal values).
        It is used for a trapezoidal and a S-curve profile.
        Example
        Set positioning velocity of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetPosVel(1,1,100000);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: Value positioning velocity (internal values)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        value = ctypes.c_long(value)
        res = self._PS90.PS90_SetPosVel(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_stage_attributes_ps90(self, control_unit: int, axis: int, dpitch: float, increv: int,
                            dratio: float) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetStageAttributes (long Index, long AxisId, double dPitch, long IncRev, double dRatio)
        Description
        set stage attributes for an axis.
        The control unit uses for positioning of the axes internal values (increments). To allow the positioning in other units (e.g., for linear measuring stages - mm, µm, for rotary measuring stages - degrees, mrad etc.), these parameters should be defined. Then one is able to use the extended functions (...Ex) with a desired unit. The specified values are converted internally into increments. The movement of the slide per spindle revolution (pitch) is specified in a desired unit (e.g., 1 mm), as the first parameter for linear measuring stages. With rotary measuring stages a revolution of the rotary table is specified in a desired unit (e.g., 360 degrees). The number of the increments per motor revolution is defined as the second parameter. With the step motors it is the number of the full steps per revolution (e.g., 200). If a motor with the encoder is controlled, it is the number of the increments per revolution (e.g., encoder with 4-fold evaluation: encoder lines number x 4 = 500x4). The whole gear reduction ratio specified as the third parameter.
        Example
        Define stage attributes of the control unit (Index=1, Axis=1)
        (linear measuring stage + servo motor with encoder: pitch = 1.0 mm, pulses/rev = 2000, ratio =1.0):
        long error = PS90_SetStageAttributes(1,1,1.0,2000,1.0);
        double dValue = PS90_GetPositionEx(1,1);
        Define stage attributes of the control unit (Index=1, Axis=2)
        (rotary measuring stage + step motor without encoder: revolution = 360.0 degrees, full steps/rev = 200, ratio =180.0):
        error = PS90_SetStageAttributes(1,2,360.0,200,180.0);
        dValue = PS90_GetPositionEx(1,2);
        :param control_unit:Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param dpitch: dPitch pitch
        :param increv: IncRev pulses/steps per motor revolution
        :param dratio: dRatio gear reduction ratio
        :return: 0 – function was successful
                -1 – function error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        dpitch = ctypes.c_double(dpitch)
        increv = ctypes.c_long(increv)
        dratio = ctypes.c_double(dratio)
        res = self._PS90.PS90_SetStageAttributes(control_unit, axis, dpitch, increv, dratio)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_target_mode_ps90(self, control_unit: int, axis: int, mode: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetTargetMode (long Index, long AxisId, long Mode)
        Description
        set target mode of an axis
        Example
        Set target mode of the control unit (Index=1, Axis=1) for relative positioning:
        long error = PS90_SetTargetMode(1,1,0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param mode: Mode target mode Mode=0 relative positioning (target value is distance) Mode=1 absolute positioning (target value is target position)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        mode = ctypes.c_long(mode)
        res = self._PS90.PS90_SetTargetMode(control_unit, axis, mode)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_target_ps90(self, control_unit: int, axis: int, value: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetTarget (long Index, long AxisId, long Value)
        Description
        set target position or distance of an axis (values in increments).
        The definition depends on the target mode. The sign determines the positioning direction.
        Example
        Set distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetTargetMode(1,1,0);
        error = PS90_SetTarget(1,1,100);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1…9)
        :param value: Value target position or distance (values in increments)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        value = ctypes.c_long(value)
        res = self._PS90.PS90_SetTarget(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_target_ex_ps90(self, control_unit: int, axis: int, value: float) -> Tuple[Union[bool, str]]:
        """
        long PS90_SetTargetEx (long Index, long AxisId, double dValue)
        Description
        set target position or distance of an axis (values in selected unit).
        The definition depends on the target mode. The sign determines the positioning direction.
        Example
        Set distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetTargetMode(1,1,0);
        error = PS90_SetTargetEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue target position or distance (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis + 1)
        value = ctypes.c_double(value)
        res = self._PS90.PS90_SetTargetEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _error_OWIS_ps90(self, code: int, type: int, user_def='') -> str:
        """
        :param code: <=0
        :param type: 0 for Connection error codes, 1 for Function error codes
        :return: error as string
        """
        errors_connections = {0: 'no error', -1: 'function error', -2: 'invalid serial com_port (com_port is not found)',
                  -3: 'access react_denied  (com_port is busy)', -4: 'access react_denied  (com_port is busy)',
                  -5: 'no response from control unit', -7: 'control unit with the specified serial number is not found',
                  -8: 'no connection to modbus/tcp', -9: 'no connection to tcp/ip socket'}
        errors_functions = {0: 'no error', -1: 'function error', -2: 'communication error', -3: 'syntax error',
                            -4: 'axis is in wrong state', -9: 'OWISid chip is not found',
                            -10: 'OWISid parameter is empty (not defined)'}
        if code > 0 or (code not in errors_connections or code not in errors_functions):
            return "Wrong code number"
        elif type not in [0, 1]:
            return "Wrong type of error"
        else:
            if code != 0:
                return errors_connections[code] if type == 0 else errors_functions[code]
            else:
                return user_def