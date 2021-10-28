#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import os

from pathlib import Path
import os
p = os.path.realpath(__file__)

app_folder = Path(p).resolve().parents[0]

app_folder1 = Path(p).resolve().parents[2]
sys.path.append(str(app_folder1))


from tango import DevState
from tango.server import command, device_property

import ctypes

from typing import Tuple, Union
from time import sleep

from utilities.tools.decorators import development_mode
dev_mode = False
# Strange delay for ps90.dll
time_ps_delay = 0.05
dll_path = str(app_folder / 'ps90.dll')
lib = ctypes.WinDLL(dll_path)

try:
    from DeviceServers.General.DS_Motor import DS_MOTORIZED_MULTI_AXES
except ModuleNotFoundError:
    from General.DS_motor import DS_MOTORIZED_MULTI_AXES


class DS_OWIS_PS90(DS_MOTORIZED_MULTI_AXES):
    """"
    Device Server (Tango) which controls the OWIS delay lines using ps90.dll
    """

    RULES = {**DS_MOTORIZED_MULTI_AXES.RULES}

    baudrate = device_property(dtype=int, default_value=9600)
    com_port = device_property(dtype=int, default_value=4)
    interface = device_property(dtype=int, default_value=0)
    control_unit_id = device_property(dtype=int, default_value=1)
    serial_number = device_property(dtype=int)

    _version_ = '0.2'
    _model_ = 'OWIS controller PS90 multi-axes'

    def init_device(self):
        super().init_device()
        self.turn_on()

    def find_device(self) -> Tuple[int, str]:
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            res, comments = self._connect_ps90(self.control_unit_id,
                                               interface=self.interface,
                                               port=self.com_port,
                                               baudrate=self.baudrate)
            if res:
                self.set_state(DevState.ON)
                argreturn = self.control_unit_id, f'{self.serial_number}'.encode('utf-8')
            else:
                self.set_state(DevState.FAULT)
        return argreturn

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.info(f'Searching for device: {self.device_id}', True)
            self._device_id_internal, self._uri = self.find_device()
        if self._device_id_internal == -1:
            self.set_state(DevState.FAULT)
            return f'Could NOT turn on {self.device_name()}: Device could not be found.'
        else:
            self.set_state(DevState.ON)
            for axis in self._delay_lines_parameters.keys():
                self.init_axis(axis)
            return 0

    def turn_off_local(self) -> Union[int, str]:
        self._device_id_internal = -1
        res, comments = self._disconnect_ps90(self.control_unit_id)
        if res:
            self.set_state(DevState.OFF)
            return 0
        else:
            self.set_state(DevState.FAULT)
            return comments

    def get_controller_status_local(self) -> Union[int, str]:
        for axis in self._delay_lines_parameters.keys():
            self.get_status_axis_local(axis)
        ser_num = self._get_serial_number_ps90(self.control_unit_id)
        if self.serial_number != ser_num:
            return f'Connection with PS90 is lost'
        else:
             return 0

    def init_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._motor_init_ps90(self.control_unit_id, axis)
        if not res:
            result = f'ERROR: Device {self.device_name()} motor_init for axis {axis} func did NOT work {comments}.'
            self.error(result)
            self._delay_lines_parameters[axis]['state'] = DevState.FAULT
        else:
            res, comments = self._set_target_mode_ps90(self.control_unit_id, axis, 1)
            if not res:
                result = f'ERROR: Device {self.device_name()} set_target_mode to ABS for axis {axis} ' \
                         f'did NOT work {comments}.'
                self.error(result)
            else:
                self._delay_lines_parameters[axis]['state'] = DevState.INIT
                res = self.set_param_axis(axis)
                if res == '0':
                    result = 0
                else:
                    result = res
        return result

    def get_status_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._get_axis_state_ps90(self.control_unit_id, axis)
        if res == 0:
            result = DevState.OFF
        elif res == 1:
            result = DevState.STANDBY
        elif res == 2:
            result = DevState.INIT
        elif res == 3:
            result = DevState.ON
        else:
            error = f'ERROR: {comments}'
            self.error(error)
            result = DevState.FAULT
        self._delay_lines_parameters[axis]['state'] = result
        return 0

    def read_position_axis_local(self, axis: int) -> Union[int, str]:
        res, com = self._get_pos_ex_ps90(self.control_unit_id, axis)
        if not com:
            self._delay_lines_parameters[axis]['position'] = res
            result = 0
        else:
            result = f'Device {self.device_name()} reading position of axis {axis} was not successful.'
            self.error(result)
        return result

    def set_param_axis_local(self, args) -> Union[int, str]:
        axis = int(args[0])
        pitch = args[1]
        revolution = args[2]
        gear_ratio = args[3]
        speed = args[4]
        limit_min = args[5]
        limit_max = args[6]

        res1, com1 = self._set_stage_attributes_ps90(self.control_unit_id, axis, pitch, revolution, gear_ratio)
        res2, com2 = self._set_pos_velocity_ps90(self.control_unit_id, axis, speed)
        res3, com3 = self._set_limit_min_ps90(self.control_unit_id, axis, limit_min)
        res4, com4 = self._set_limit_max_ps90(self.control_unit_id, axis, limit_max)

        if all([res1, res2, res3, res4]):
            result = 0
        else:
            result = f'ERROR: {com1}:{com2}:{com3}:{com4}'
            self.error(result)
        return result

    def turn_on_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._motor_on_ps90(self.control_unit_id, axis)
        if not res:
            result = f'ERROR: Device {self.device_name()} turn_on_axis for axis {axis} func did NOT work {comments}.'
            self.error(result)
        else:
            self._delay_lines_parameters[axis]['state'] = DevState.ON
            result = 0
        return result

    def turn_off_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._motor_off_ps90(self.control_unit_id, axis)
        if not res:
            result = f'ERROR: Device {self.device_name()} turn_off_axis for axis {axis} func did NOT work {comments}.'
            self.error(result)
        else:
            self._delay_lines_parameters[axis]['state'] = DevState.OFF
            result = 0
        return result

    def move_axis_local(self, args) -> Union[int, str]:
        axis = int(args[0])
        pos: float = args[1]
        res, comments = self._set_target_ex_ps90(self.control_unit_id, axis, pos)
        if not res:
            result = f'ERROR: Device {self.device_name()} set_target_ex to {pos} for axis {axis} ' \
                     f'did NOT work {comments}.'
            self.error(result)
        else:
            res, comments = self._go_target_ps90(self.control_unit_id, axis)
            if res:
                result = f'Device {self.device_name()} axis {axis} started moving.'
            else:
                result = f'ERROR: Device {self.device_name()} axis {axis} did NOT started moving {comments}.'
                self.error(result)
        return result

    def stop_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._stop_axis_ps90(self.control_unit_id, axis)
        if not res:
            result = f'ERROR: Device {self.device_name()} stop_axis axis {axis} ' \
                     f'did NOT work {comments}.'
            self.error(result)
        else:
            result = 0
        return result

    # @command
    # def define_position_axis(self, axis:int, pos: float):
    #     pass

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
        interface = ctypes.c_long(int(interface))
        port = ctypes.c_long(int(port))
        baudrate = ctypes.c_long(int(baudrate))
        par3 = ctypes.c_long(par3)
        par4 = ctypes.c_long(par4)
        par5 = ctypes.c_long(par5)
        par6 = ctypes.c_long(par6)
        # res x -1 is according official documentation
        sleep(time_ps_delay)
        res = lib.PS90_Connect(control_unit, interface, port, baudrate, par3, par4, par5, par6) * -1
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _connect_simple_ps90(self, control_unit=1, ser_num="") -> Tuple[Union[bool, str]]:
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
        :param ser_num: pszSerNum control unit serial number (default=empty string)
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
        ser_num = ctypes.c_char_p(ser_num)
        sleep(time_ps_delay)
        res = lib.PS90_SimpleConnect(control_unit, ser_num) * -1  # *-1 is according official documentation
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    def _convert_axis_state_format_ps90(self, axis_state_OWIS: int) -> int:
        """
        Converts OWIS controller axis state to the used for stpmtr_controller
        :param axis_state_OWIS: 0     axis is not active
                                1     axis is not initialized
                                2     axis is switched off
                                3     axis is active and initialized and switched on
        :return: 0 - axis is not initialized, 1 - is active
        """
        if axis_state_OWIS in [0, 1, 2]:
            return 0
        elif axis_state_OWIS == 3:
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
        sleep(time_ps_delay)
        res = lib.PS90_Disconnect(control_unit)
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_FreeSwitch(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _get_connection_info(self, control_unit: int) -> Tuple[Union[bool, str]]:
        """
        Synopsis
        long PS90_GetConnectInfo (long Index, char* pszBuffer, long Length, long Mode)
        Description
        read connecting configuration
        Parameters
        Index control unit index (1-10)
        pszBuffer address of buffer for reading
        Length length of the buffer
        Mode mode (default=0, range=0...3)
        0 – connecting configuration
        1 – connecting configuration (short format)
        2 – last transferred data
        3 – connecting state (online or offline)

        Returns
        length of the string
        Example
        Read a connecting configuration for the control unit (Index=1):
        char szString[50];
        long len = PS90_GetConnectInfo(1, szString, 50, 0);
        long error = PS90_GetReadError(1);
        """

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _get_serial_number_ps90(self, control_unit: int) -> Tuple[Union[bool, str]]:
        """
        Synopsis
            long PS90_GetSerNumber (long Index, char* pszBuffer, long Length)


Description
read serial number of the control unit


Parameters
Index control unit index (1-10)
pszBuffer address of the buffer for reading
Length length of the buffer



Returns
length of the string


Example
Read serial number of the control unit (Index=1):
char szString[25];
long len = PS90_GetSerNumber(1, 1, szString, 25);
long error = PS90_GetReadError(1);
        """
        buf = ctypes.create_string_buffer(25)
        control_unit = ctypes.c_long(control_unit)
        res = lib.PS90_GetSerNumber(control_unit, buf, 25)
        result = buf.value.decode('utf-8')
        return int(result)

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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_GetAxisState(control_unit, axis)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(0.0, 'DEV MODE'))
    def _get_target_ex_ps90(self, control_unit: int, axis: int) -> Tuple[Union[float, bool, str]]:
        """
        double PS90_GetTargetEx (long Index, long AxisId)
        Description
        read target position or distance of an axis (values in selected unit)
        Parameters
        Index control unit index (1-10)
        AxisId axis number (1...9)
        Example
        Read target position or distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        double dValue = PS90_GetTargetEx(1,1);
        error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: target position or distance (values in selected unit)


        """
        if not control_unit:
            control_unit = self.control_unit_id
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        res = lib.PS90_GetTargetEx(control_unit, axis) / 10000
        sleep(time_ps_delay)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(0.0, 'DEV MODE'))
    def _get_pos_ex_ps90(self, control_unit: int, axis: int) -> Tuple[Union[float, bool, str]]:
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
        if not control_unit:
            control_unit = self.control_unit_id
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_GetPosition(control_unit, axis) / 10000
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        error = self._error_OWIS_ps90(error, 1)
        return res, error

    @development_mode(dev=dev_mode, with_return=(0.0, 'DEV MODE'))
    def _get_target_mode_ps90(self, control_unit: int, axis: int) -> Tuple[Union[float, bool, str]]:
        """
        Description
        read target mode of an axis
        Parameters
        Index control unit index (1-10)
        AxisId axis number (1...9)
        Returns
        0 – relative positioning (target value is distance)
        1 – absolute positioning (target value is target position)
        Example
        Read target mode of an axis of the control unit (Index=1, Axis=1):
        long mode = PS90_GetTargetMode(1,1);
        long error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        """
        if not control_unit:
            control_unit = self.control_unit_id
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_GetTargetMode(control_unit, axis)
        error = self.__get_read_error_ps90(control_unit)
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_GoTarget(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def __get_read_error_ps90(self, control_unit: int) -> int:
        if not isinstance(control_unit, ctypes.c_long):
            control_unit = ctypes.c_long(control_unit)
        sleep(time_ps_delay)
        res = lib.PS90_GetReadError(control_unit)
        return res

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _motor_init_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """
        long PS90_MotorInit (long Index, long AxisId)
        Description
        initialize an axis and switch on.
        With this function the axis is completely initialized and afterwards is with a current and with active positioning regulator.
        It must be executed after the turning on of the control unit, so that the axis can be moved afterwards with the commands REF, PGO, VGO etc.
        Before the following parameters must have been set: limit switch mask and polarity, start regulator parameters.
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_MotorInit(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1, f'Motor of axis {axis} is initialized')

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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_MotorOn(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1, f'Motor of axis {axis} is on.')

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
        axis = int(axis)
        axis = ctypes.c_int(axis)
        sleep(time_ps_delay)
        res = lib.PS90_MotorOff(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1, f'Motor of axis {axis} is off.')

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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = lib.PS90_Stop(control_unit, axis)
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = lib.PS90_SetLimitMinEx(control_unit, axis, value)
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = lib.PS90_SetLimitMaxEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_position_ex_ps90(self, control_unit: int, axis: int, pos: float) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        pos = ctypes.c_double(pos)
        sleep(time_ps_delay)
        res = lib.PS90_SetPositionEx(control_unit, axis, pos)
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
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        mode = ctypes.c_long(mode)
        sleep(time_ps_delay)
        res = lib.PS90_SetPosMode(control_unit, axis, mode)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_pos_velocity_ps90(self, control_unit: int, axis: int, value: float) -> Tuple[Union[bool, str]]:
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = lib.PS90_SetPosFEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_stage_attributes_ps90(self, control_unit: int, axis: int, pitch: float, inc_rev: int,
                                   gear_ratio: float) -> Tuple[Union[bool, str]]:
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
        :param pitch: dPitch pitch
        :param inc_rev: IncRev pulses/steps per motor revolution
        :param gear_ratio: dRatio gear reduction ratio
        :return: 0 – function was successful
                -1 – function error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        pitch = ctypes.c_double(pitch)
        inc_rev = ctypes.c_long(int(inc_rev))
        gear_ratio = ctypes.c_double(gear_ratio)
        sleep(time_ps_delay)
        res = lib.PS90_SetStageAttributes(control_unit, axis, pitch, inc_rev, gear_ratio)
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        mode = ctypes.c_long(mode)
        sleep(time_ps_delay)
        res = lib.PS90_SetTargetMode(control_unit, axis, mode)
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_long(value)
        sleep(time_ps_delay)
        res = lib.PS90_SetTarget(control_unit, axis, value)
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
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = lib.PS90_SetTargetEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _error_OWIS_ps90(self, code: int, type: int, user_def='') -> str:
        """
        :param code: <=0
        :param type: 0 for Connection error codes, 1 for Function error codes
        :return: error as string
        """
        errors_connections = {0: 'no error',
                              -1: 'function error',
                              -3: 'invalid serial com_port (com_port is not found)',
                              -4: 'access react_denied  (com_port is busy)',
                              -5: 'no response from control unit',
                              -7: 'control unit with the specified serial number is not found',
                              -8: 'no connection to modbus/tcp',
                              -9: 'no connection to tcp/ip socket'}
        errors_functions = {0: 'no error',
                            -1: 'function error',
                            -2: 'communication error',
                            -3: 'syntax error',
                            -4: 'axis is in wrong state',
                            -9: 'OWISid chip is not found',
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


def main(device_name=None):
    sys.argv.append(device_name)
    DS_OWIS_PS90.run_server()


if __name__ == "__main__":
    DS_OWIS_PS90.run_server()
