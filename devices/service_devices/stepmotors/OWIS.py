"""
This controller is dedicated to control OWIS PS90 controller hardware
On ELYSE there are 3 cards dedicated to delaylines
"""
import ctypes
import logging
import os
from time import sleep
from typing import Dict, Union, Tuple, Set, Callable
from pathlib import Path

from communication.messaging.messages import MessageExt
from devices.devices_dataclass import HardwareDeviceDict, HardwareDevice
from devices.service_devices.stepmotors.stpmtr_controller import StpMtrController, StpMtrError
from utilities.tools.decorators import development_mode
from devices.service_devices.stepmotors.stpmtr_dataclass import OwisAxisStpMtr
from utilities.myfunc import join_smart_comments, error_logger
from utilities.errors.myexceptions import DLLIsBlocked
from utilities.tools.decorators import dll_lock_for_class

module_logger = logging.getLogger(__name__)


dev_mode = False
time_ps_delay = 0.05


class StpMtrCtrl_OWIS(StpMtrController):

    def __init__(self, **kwargs):
        kwargs['stpmtr_dataclass'] = OwisAxisStpMtr
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, OwisAxisStpMtr] = HardwareDeviceDict()
        self._PS90: ctypes.WinDLL = None
        self._dll_lock = False
        self._dirname = Path(os.path.dirname(__file__))
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('move_parameters', 'move_parameters', dict),
                                                                      ('limits', 'limits', tuple),
                                                                      ('preset_values', 'preset_values', tuple),
                                                                      ('speed', 'speeds', float),
                                                                      ('pitch', 'pitches', float),
                                                                      ('gear_ratio', 'gear_ratios', float),
                                                                      ('revolution', 'revolutions', int)],
                                                          extra_func=[self._get_positions_file,
                                                                      self._set_move_parameters_axes,
                                                                      self._set_power_settings])
        if not res:
            raise StpMtrError(self, comments)
        else:
            self.control_unit_id = 1

    def _dll_is_locked(self, com: str):
        if com in self.available_public_functions_names:
            if self._dll_lock:
                raise DLLIsBlocked()

    def _change_device_status_local(self, axis: HardwareDevice, flag: int, force=False) -> Tuple[bool, str]:
        axis: OwisAxisStpMtr = axis
        res, comments = False, 'Did not work.'
        if axis.status == 2 and force:
            res_loc, comments_loc = self._stop_axis(axis.device_id)
            if res_loc:
                info = f'Axis id={axis.device_id_seq}, name={axis.name} was stopped.'
                self.axes_stpmtr[axis.device_id_seq].status = flag
                res, comments = True, f'{info} ' \
                                      f'Axis id={axis.device_id_seq}, name={axis.friendly_name} is set to {flag}.'
            else:
                info = f' Axis id={axis.device_id_seq}, name={axis.name} was not stopped: {comments_loc}.'
                res, comments = False, info
        elif axis.status == 2 and not force:
            res, comments = False, f'Axis id={axis.device_id_seq}, name={axis.friendly_name} is moving. ' \
                                   'Force Stop in order to change.'
        else:
            self.axes_stpmtr[axis.device_id_seq].status = flag
            res, comments = True, f'Axis id={axis.device_id_seq}, name={axis.friendly_name} is set to {flag}.'

        if flag == 0 or flag == 1:
            res, comments_loc = self._motor_off_ps90(self.control_unit_id, axis.device_id_seq)
        elif flag == 2:
            res, comments_loc = self._motor_on_ps90(self.control_unit_id, axis.device_id_seq)
        if not res:
            comments = comments_loc
        return res, comments

    def execute_com(self, msg: MessageExt, lock_func: Callable = None):
        super().execute_com(msg, self._dll_is_locked)

    def create_dll_connection(self):
        param = self.get_parameters
        dll_path = str(Path(self._dirname / param['dll_path']))
        self._PS90 = ctypes.WinDLL(dll_path)

    def destroy_dll_connection(self):
        self._PS90 = None
        self._dll_lock = False

    @dll_lock_for_class
    def _form_devices_list(self) -> Tuple[bool, str]:
        param = self.get_parameters
        self.create_dll_connection()
        res, comments = self._connect_ps90(self.control_unit_id, interface=param['interface'], port=param['com_port'],
                                           baudrate=param['baudrate'])
        if res:
            keep = []
            for axis in self.axes_stpmtr.values():
                res, comments = self._motor_init_ps90(self.control_unit_id, axis.device_id_seq)
                if res:
                    _, _ = self._motor_off_ps90(self.control_unit_id, axis.device_id_seq)
                    keep.append(axis.device_id)
                    axis.device_id_internal_seq = axis.device_id_seq
                else:
                    return res, comments
            cleaned_axes = HardwareDeviceDict()
            i = 1
            for axis in self.axes_stpmtr.values():
                if not axis.device_id_internal_seq:
                    del self.axes_stpmtr[axis.device_id]
                else:
                    if not axis.friendly_name:
                        axis.friendly_name = axis.name
                    cleaned_axes[i] = axis
                    i += 1
            self._hardware_devices = cleaned_axes
        else:
            self._PS90 = None

        return res, comments

    def _get_number_hardware_devices(self):
        return self._hardware_devices_number

    @dll_lock_for_class
    def _get_position_axis(self, device_id: Union[int, str]) -> Tuple[bool, str]:
        axis: OwisAxisStpMtr = self.axes_stpmtr[device_id]
        res, com = self._get_pos_ex_ps90(self.control_unit_id, axis.device_id_seq)
        if not com:
            axis.position = res
            pos = self._form_axes_positions()
            self._write_positions_to_file(pos)
            return True, ''
        else:
            return False, com

    @dll_lock_for_class
    def _move_axis_to(self, axis_id: int, go_pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        """
        Move selected axis to set position. Turns on motor, set target, go target and checks position every 25ms for
        1000 cycles. Motor off when position is within 0.001mm accuracy
        :param axis_id: 1-n
        :param go_pos: position in mm
        :param how: absolute, relative
        :return: True/False, comments
        """
        try:
            axis: OwisAxisStpMtr = self.axes_stpmtr[axis_id]
            res, comments = self._change_device_status_local(axis, 2, True)
            if res:
                res, comments = self._get_target_mode_ps90(self.control_unit_id, axis.device_id_seq)
                if isinstance(res, bool):
                    return res, comments
                else:
                    how_local = 1 if how == 'absolute' else 0
                    if res != how_local:
                        res, comments = self._set_target_mode_ps90(self.control_unit_id, axis.device_id_seq)
                    else:
                        res, comments = True, ''

                if res:
                    res, comments = self._set_target_ex_ps90(self.control_unit_id, axis.device_id_seq, go_pos)

                if res:
                    res, comments = self._get_target_ex_ps90(self.control_unit_id, axis.device_id_seq)
                    if isinstance(res, bool):
                        return res, comments
                    else:
                        if abs(res - go_pos) >= 0.001:
                            res, comments = False, f'Target was not set correctly: ' \
                                                   f'abs(res - go_pos)={abs(res - go_pos)}, pos={go_pos}, res={res}'
                        else:
                            res, comments = True, ''

                if res:
                    res, comments = self._go_target_ps90(self.control_unit_id, axis.device_id_seq)

                interrupted = False
                if res:
                    for i in range(300):
                        if axis.status != 2:
                            interrupted = True
                            break
                        t = (0.1 * abs(axis.position - go_pos))
                        print(f'Sleep time 1: {t}')
                        sleep(t)
                        res, com = self._get_pos_ex_ps90(self.control_unit_id, axis.device_id_seq)
                        res = go_pos
                        if com:
                            comments = join_smart_comments(comments, com)
                        if not isinstance(res, bool):
                            axis.position = res
                            if abs(res - go_pos) <= 0.001:
                                res, comments = True, f'Axis {axis.friendly_name} is stopped. Actual position is {res}'
                                break
                        else:
                            res, comments = False, join_smart_comments(f'During movement Axis={axis.friendly_name} '
                                                                       f'error has occurred.', com)
                            break

                if res:
                    if not interrupted:
                        res, comments = True, f'Movement of Axis with id={axis.device_id_internal_seq}, ' \
                                              f'name={axis.friendly_name} was finished.'
                    else:
                        return False, f'Movement of Axis with id={axis.device_id_internal_seq} was interrupted.'
            if not res:
                _, com = self._change_device_status_local(axis, 1, True)
                comments = join_smart_comments(comments, com)
                return res, comments
            else:
                res, com = self._change_device_status_local(axis, 1, True)

            if not res:
                comments = join_smart_comments(comments, com)
        except Exception as e:
            error_logger(self, self._move_axis_to, e)
            res, comments = False, f'{e}'
        print(res, comments)
        return res, comments

    @dll_lock_for_class
    def _set_pos_axis(self, device_id: Union[int, str], pos: float) -> Tuple[bool, str]:
        axis: OwisAxisStpMtr = self.axes_stpmtr[device_id]
        res, com = self._set_position_ex_ps90(self.control_unit_id, axis.device_id_seq, pos)
        if res:
            self._get_position_axis(axis.device_id)
            return True, ''
        else:
            return False, com

    @dll_lock_for_class
    def _set_move_parameters_axes(self, must_have_param: Set[str] = None):
        must_have_param = {'ALL': set(['basic_unit'])}
        return super()._set_move_parameters_axes(must_have_param)

    @dll_lock_for_class
    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        results, comments = [], ''
        res, com = self._set_stages_settings()
        results.append(res)
        comments = join_smart_comments(comments, com)
        res, com = super()._set_parameters_after_connect()
        results.append(res)
        comments = join_smart_comments(comments, com)
        return all(results), comments

    def _set_stages_settings(self) -> Tuple[bool, str]:
        results, comments = [], ''
        for axis in self.axes_stpmtr.values():
            axis: OwisAxisStpMtr = axis
            try:
                param = self.get_main_device_parameters
                gear_ratio = float(eval(param['gear_ratios'])[axis.device_id])
                pitch = float(eval(param['pitches'])[axis.device_id])
                speed = float(eval(param['speeds'])[axis.device_id])
                revolution = int(eval(param['revolutions'])[axis.device_id])
                limits = eval(param['limits'])[axis.device_id]
                axis.limits = limits
                axis.speed = speed
                axis.pitch = pitch
                axis.revolution = revolution
                axis.gear_ratio = gear_ratio

                res, com = self._set_stage_attributes_ps90(self.control_unit_id, axis.device_id_seq, pitch/pitch,
                                                           revolution,
                                                           gear_ratio)
                comments = join_smart_comments(comments, com)
                if res:
                    res, com = self._set_pos_velocity_ps90(self.control_unit_id, axis.device_id_seq, speed)
                comments = join_smart_comments(comments, com)

                if res:
                    res, com = self._set_limit_min_ps90(self.control_unit_id, axis.device_id_seq, limits[0])
                comments = join_smart_comments(comments, com)

                if res:
                    res, com = self._set_limit_max_ps90(self.control_unit_id, axis.device_id_seq, limits[1])
                comments = join_smart_comments(comments, com)
                results.append(res)

            except Exception as e:
                error_logger(self, self._set_stages_settings, e)
                comments = join_smart_comments(comments, str(e))
                results.append(False)

        return all(results), comments

    @dll_lock_for_class
    def _stop_axis(self, device_id: str) -> Tuple[bool, str]:
        axis = self.axes_stpmtr[device_id]
        return self._stop_axis_ps90(self.control_unit_id, axis.device_id_internal_seq)

    @dll_lock_for_class
    def _release_hardware(self) -> Tuple[bool, str]:
        for axis in self.axes_stpmtr.values():
            self._change_device_status_local(axis, 0, True)
        return self._disconnect_ps90(self.control_unit_id)

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
        res = self._PS90.PS90_Connect(control_unit, interface, port, baudrate, par3, par4, par5, par6) * -1
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
        res = self._PS90.PS90_SimpleConnect(control_unit, ser_num) * -1  # *-1 is according official documentation
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
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
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
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self._PS90.PS90_GetAxisState(control_unit, axis)
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
        pitch = self.axes_stpmtr[axis].pitch
        axis = ctypes.c_long(axis)
        res = self._PS90.PS90_GetTargetEx(control_unit, axis) / 10000 * pitch
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
        pitch = self.axes_stpmtr[axis].pitch
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        print('measuring pos....')
        res = self._PS90.PS90_GetPosition(control_unit, axis) / 10000 * pitch
        print('measured pos....')
        print('checking error....')
        error = self.__get_read_error_ps90(control_unit)
        print('checked error....')
        if error != 0:
            res = False
        print(f'result: {res}')
        error = self._error_OWIS_ps90(error, 1)
        print(f'error: {error}')
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
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self._PS90.PS90_GetTargetMode(control_unit, axis)
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
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self._PS90.PS90_GoTarget(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def __get_read_error_ps90(self, control_unit: int) -> int:
        if not isinstance(control_unit, ctypes.c_long):
            control_unit = ctypes.c_long(control_unit)
        sleep(time_ps_delay)
        res = self._PS90.PS90_GetReadError(control_unit)
        return res

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
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self._PS90.PS90_MotorInit(control_unit, axis)
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
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self._PS90.PS90_MotorOn(control_unit, axis)
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
        axis = ctypes.c_int(axis)
        sleep(time_ps_delay)
        res = self._PS90.PS90_MotorOff(control_unit, axis)
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
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
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
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
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
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self._PS90.PS90_SetLimitMaxEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, 'DEV MODE'))
    def _set_position_ex_ps90(self, control_unit: int, axis: int, pos: float) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_long(control_unit)
        axis = ctypes.c_long(axis)
        pos = ctypes.c_double(pos)
        sleep(time_ps_delay)
        res = self._PS90.PS90_SetPositionEx(control_unit, axis, pos)
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
        axis = ctypes.c_long(axis)
        mode = ctypes.c_long(mode)
        sleep(time_ps_delay)
        res = self._PS90.PS90_SetPosMode(control_unit, axis, mode)
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
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self._PS90.PS90_SetPosFEx(control_unit, axis, value)
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
        axis = ctypes.c_long(axis)
        pitch = ctypes.c_double(pitch)
        inc_rev = ctypes.c_long(inc_rev)
        gear_ratio = ctypes.c_double(gear_ratio)
        sleep(time_ps_delay)
        res = self._PS90.PS90_SetStageAttributes(control_unit, axis, pitch, inc_rev, gear_ratio)
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
        axis = ctypes.c_long(axis)
        mode = ctypes.c_long(mode)
        sleep(time_ps_delay)
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
        axis = ctypes.c_long(axis)
        value = ctypes.c_long(value)
        sleep(time_ps_delay)
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
        pitch = self.axes_stpmtr[axis].pitch
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value / pitch)
        sleep(time_ps_delay)
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
