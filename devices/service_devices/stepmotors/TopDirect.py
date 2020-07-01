"""
CLI for controlling 5V NEWPORT steppers with A9888
in reality 12V is supplied, thus is really important to
disable controller and switch off for doulbe protection
so current does not run during waiting time

4 axis are controlled at this moment with this peace of code
INSTEAD of RPi.GPIO -> gpiozero will be used, since it could be installed
under windows with no problems
"""
import logging
from time import sleep
from typing import Callable

import serial
import serial.tools.list_ports

from utilities.datastructures.mes_independent import *
from utilities.myfunc import error_logger
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


class StpMtrCtrl_TopDirect_1axis(StpMtrController):

    class States(Enum):
        ON = 0
        OFF = 1

    class Direction(Enum):
        FORWARD = 'forward'
        BACKWARD = 'backward'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.arduino_serial: serial.Serial = None
        self._arduino_port = ''

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        if self.device_status.power:
            if flag:
                res, comments = self._find_arduino_check(self.get_parameters['arduino_serial_id'])
                if res:
                    self.arduino_serial = serial.Serial(self._arduino_port, timeout=1,
                                                        baudrate=int(self.get_parameters['baudrate']))
                    sleep(1)
                    get = self._get_reply_from_arduino()
                    if get == 'INITIALIZED':
                        res, comments = True, ''
                    else:
                        res, comments = False, 'Arduino was not initialized.'
            else:
                self._disable_controller()
                self.arduino_serial.close()
                self.arduino_serial = None
                res, comments = True, ''
            if res:
                self.device_status.connected = flag
        else:
            res, comments = False, f'Power is off, connect to controller function cannot be called with flag {flag}'
        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        if self.device_status.connected:
            self._send_to_arduino(f'GET STATE')
            rcv = self._get_reply_from_arduino(True)
            if rcv[1] == 0:
                return True, ''
            elif rcv[1] != 0:
                return False, f'Arduino error {rcv[1]}.'
        else:
            return False, f'Arduino is not connected.'

    def _check_if_connected(self) -> Tuple[bool, str]:
        if self.arduino_serial:
            self._send_to_arduino('GET STATE')
            res = self._get_reply_from_arduino(True)
            if res:
                return True, ''
            else:
                return False, 'Arduino is not responding. Try later, maybe it is moving and cannot answer.'
        else:
            return False, 'Not connected, serial connection is absent. First Connect.'

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        if self.axes[axis_id].status == flag:
            res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is already set to {flag}'
        else:
            if not force:
                if self.axes[axis_id].status != 2:
                    self.axes[axis_id].status = flag
                    res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is set to {flag}'
                    if flag == 2:
                        self._enable_controller()
                    elif flag == 1:
                        self._enable_controller()
                    elif flag == 0:
                        self._disable_controller()
                else:
                    return False, f'Axis id={1} is moving. Use force, or wait movement to complete to change the status.'
            else:
                self.axes[axis_id].status = flag
                res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is set to {flag}'

        return res, comments

    def _check_arduino_port(self, com_port: serial) -> Tuple[bool, str]:
        from time import sleep
        try:
            ser = serial.Serial(com_port)
            sleep(0.1)
            ser.close()
            return True, ''
        except serial.SerialException as e:
            error_logger(self, self._check_arduino_port, e)
            return False, str(e)

    def _disable_controller(self):
        self._send_to_arduino('SET STATE 0')
        out = self._get_reply_from_arduino()
        if  out != 0:
            error_logger(self, self._enable_controller, f'Arduino was not disabled.')
            res, comments = False, f'Arduino was not disabled: {out}.'
        else:
            res, comments = True, ''
        return res, comments

    def _enable_controller(self) -> Tuple[bool, str]:
       self._send_to_arduino('SET STATE 1')
       out = self._get_reply_from_arduino()
       if out != 0:
           error_logger(self, self._enable_controller, f'Arduino was not enabled: {out}.')
       else:
           res, comments = True, ''
       return res, comments

    def _find_arduino_check(self, serial_number) -> Tuple[bool, str]:
        """
        Searches for Arduino with a given serial number and returns its COM com_port.
        :param serial_number: Arduino serial id
        :return: COM PORT
        """
        for pinfo in serial.tools.list_ports.comports():
            if pinfo.serial_number == serial_number:
                res, comments = self._check_arduino_port(pinfo.device)
                if res:
                    self._arduino_port = pinfo.device
                    return True, ''
                else:
                    return False, f'Arduino with {serial_number} was found, but port check was not passed: {comments}.'
        return False, f"Could not find an Arduino {serial_number}. Check connection."

    def _get_reply_from_arduino(self, all_lines=False) -> Union[str, List[str], None]:
        sleep(0.1)
        def convert_str_float_or_int(s: str):
            try:
                s = int(s)
            except ValueError:
                try:
                    s = float(s)
                except ValueError:
                    pass
            finally:
                return s

        if all_lines:
            res = self.arduino_serial.readlines()
        else:
            res = self.arduino_serial.readline()

        if res:
            if isinstance(res, list):
                res_s = []
                for line in res:
                    line = convert_str_float_or_int(line.decode().rstrip())
                    res_s.append(line)
                return res_s
            else:
                res = convert_str_float_or_int(res.decode().rstrip())
                return res
        else:
            return None

    def GUI_bounds(self):
        # TODO: to be done something with this
        return {'visual_components': [[('activate'), 'button'], [('move_pos', 'get_pos'), 'text_edit']]}

    def _get_axes_names(self):
        return self._get_axes_names_db()

    def _get_axes_status(self) -> List[int]:
        return self._axes_status

    def _get_number_axes(self) -> int:
        return len(self.axes)

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._axes_limits

    def _get_positions(self) -> Dict[int, float]:
        self._send_to_arduino('GET POS')
        rcv = self._get_reply_from_arduino(True)
        if rcv[1] == 0:
            return {1: rcv[0]}
        else:
            return {1: 0}

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._axes_preset_values

    def _move_axis_to(self, axis_id: int, go_pos: float, how='absolute') -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis_id, 2)
        if res:
            interrupted = False
            self._send_to_arduino(f'MOVE ABS {float(go_pos)}')
            rcv = self._get_reply_from_arduino()
            if rcv == 'STARTED':
                timeout = True
                for i in range(30):
                    rcv = self._get_reply_from_arduino()
                    if rcv == 0:
                        timeout = False
                        break
                    sleep(1)
                if timeout:
                    rcv = -4  # timeout

            if rcv != 0:
                res, comments = False, f'Movement of Axis with id={axis_id}, name={self.axes[axis_id].name} ' \
                                       f'did not start. Error {rcv}.'
            else:
                res, comments = True, f'Movement of Axis with id={axis_id}, name={self.axes[axis_id].name} ' \
                                      f'was finished.'

            self.arduino_serial.flush()
            sleep(0.5)
            self._send_to_arduino('GET POS')
            rcv = self._get_reply_from_arduino(True)
            if rcv[1] == 0:
                self.axes[axis_id].position = rcv[0]
            else:
                error_logger(self, self.move_axis_to, f'Could not get position of controller after the movement.')
                res, comments = False, f'Could not get position of controller after the movement.'


            _, _ = self._change_axis_status(axis_id, 1, force=True)
            StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)

        return res, comments

    def _release_hardware(self) -> Tuple[bool, str]:
        return super(StpMtrCtrl_TopDirect_1axis, self)._release_hardware()

    def _setup(self) -> Tuple[Union[bool, str]]:
        res, comments = self._set_move_parameters()
        if res:
            return self._setup_pins()
        else:
            return res, comments

    def _set_i_know_how(self):
        self.i_know_how = {'mm': 1, 'steps': 0}

    def _set_controller_positions(self, positions: Dict[str, Union[int, float]]) -> Tuple[bool, str]:
        self._send_to_arduino(f'SET POS {positions[1]}')
        rcv = self._get_reply_from_arduino()
        if rcv == 0:
            return True, ''
        else:
            return False, 'Did not update Arduino pos from file.'

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        return super()._set_parameters()

    def _send_to_arduino(self, cmd: str) -> Tuple[bool, str]:
        if self.device_status.connected:
            self.arduino_serial.write(cmd.encode('utf-8'))
            sleep(0.1)

    def stop_axis(self, func_input: FuncStopAxisInput) -> FuncStopAxisOutput:
        return FuncStopAxisOutput(axes=self.axes_essentials,
                                  comments=f'Cannot be stopped by user. Wait controller to finish its movement.',
                                  func_success=False)