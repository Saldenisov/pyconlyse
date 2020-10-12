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
from typing import Callable, Dict, List, Set, Tuple, Union

import serial
import serial.tools.list_ports
from utilities.myfunc import error_logger, join_smart_comments
from devices.devices_dataclass import HardwareDeviceDict
from devices.service_devices.stepmotors.stpmtr_dataclass import *
from .stpmtr_controller import StpMtrController, StpMtrError


module_logger = logging.getLogger(__name__)


class StpMtrCtrl_TopDirect_1axis(StpMtrController):

    class States(Enum):
        ON = 0
        OFF = 1

    class Direction(Enum):
        FORWARD = 'forward'
        BACKWARD = 'backward'

    def __init__(self, **kwargs):
        kwargs['stpmtr_dataclass'] = TopDirectAxisStpMtr
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, StandaAxisStpMtr] = HardwareDeviceDict()
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('friendly_name', 'friendly_names', str),
                                                                      ('move_parameters', 'move_parameters', dict),
                                                                      ('limits', 'limits', tuple),
                                                                      ('preset_values', 'preset_values', tuple),
                                                                      ('baudrate', 'baudrates', int)],
                                                          extra_func=[self._get_positions_file,
                                                                      self._set_move_parameters_axes])
        if not res:
            raise StpMtrError(self, comments)

    def _form_devices_list(self) -> Tuple[bool, str]:
        do_not_keep_device_ids = []
        for device in self._hardware_devices.values():
            device: TopDirectAxisStpMtr = device
            res, comments = self._find_arduino_check(device.device_id)
            if res:
                device.arduino_port = res
                device.arduino_serial = serial.Serial(device.arduino_port, timeout=1, baudrate=device.baudrate)
                sleep(1)
                get = self._get_reply_from_arduino(device_id=device.device_id)
                if get != 'INITIALIZED':
                    do_not_keep_device_ids.append(device.device_id)
                else:
                    self._disable_controller(device.device_id)
            else:
                do_not_keep_device_ids.append(device.device_id)

        for device_id in do_not_keep_device_ids:
            del self._hardware_devices[device_id]

        self._hardware_devices_number = len(self._hardware_devices)

        if self._hardware_devices:
            return True, ''
        else:
            return False, 'None of devices listed in DB are available.'
        return res, comments

    def _change_device_status_local(self, device: HardwareDevice, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = False, 'Did not work.'
        if device.status == 2 and force:
            #res_loc, comments_loc = self._stop_axis(device.device_id)
            self.axes_stpmtr[device.device_id_seq].status = flag
            res, comments = True, f'Axis id={device.device_id_seq}, name={device.friendly_name} is set to {flag}.'
            if flag == 0:
                _, _ = self._disable_controller(device.device_id)
        elif device.status == 2 and not force:
            res, comments = False, f'Axis id={device.device_id_seq}, name={device.friendly_name} is moving. ' \
                                   'Force Stop in order to change.'
        else:
            if flag in [2, 1]:
                res, comments = self._enable_controller(device.device_id)
            elif flag == 0:
                res, comments = self._disable_controller(device.device_id)
            if res:
                self.axes_stpmtr[device.device_id_seq].status = flag
                res, comments = True, f'Axis id={device.device_id_seq}, name={device.friendly_name} is set to {flag}.'

        return res, comments

    def _check_arduino_port(self, com_port: serial) -> Tuple[bool, str]:
        try:
            ser = serial.Serial(com_port)
            sleep(0.05)
            ser.close()
            return True, ''
        except serial.SerialException as e:
            error_logger(self, self._check_arduino_port, e)
            return False, str(e)

    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        res, comments = self._get_positions_file()
        res, comments = [res], comments
        for device in self._hardware_devices.values():
            r, com = self._set_pos_axis(device.device_id, device.position)
            res.append(r)
            if com:
                comments = join_smart_comments(comments, com)

        for device in self._hardware_devices.values():
            r, com = self._get_position_axis(device.device_id)
            res.append(r)
            if com:
                comments = join_smart_comments(comments, com)
        return all(res), comments

    def _enable_controller(self, device_id: Union[str, int]) -> Tuple[bool, str]:
       self._send_to_arduino(device_id, 'SET STATE 1')
       out = self._get_reply_from_arduino(device_id)
       if out != 0:
           error_logger(self, self._enable_controller, f'Arduino was not enabled: {out}.')
           res, comments = False, f'Arduino was not enabled: {out}.'
       else:
           res, comments = True, ''
       return res, comments

    def _disable_controller(self, device_id: Union[str, int]):
        self._send_to_arduino(device_id, 'SET STATE 0')
        out = self._get_reply_from_arduino(device_id)
        if out != 0:
            error_logger(self, self._disable_controller, f'Arduino was not disabled: {out}.')
            res, comments = False, f'Arduino was not disabled: {out}.'
        else:
            res, comments = True, ''
        return res, comments

    def _find_arduino_check(self, serial_number: Union[int, str]) -> Tuple[Union[bool, str], str]:
        """
        Searches for Arduino with a given serial number and returns its COM com_port.
        :param serial_number: Arduino serial id
        :return: COM PORT
        """
        serial_number = str(serial_number)
        for pinfo in serial.tools.list_ports.comports():
            if pinfo.serial_number == serial_number:
                res, comments = self._check_arduino_port(pinfo.device)
                if res:
                    return pinfo.device, ''
                else:
                    return False, f'Arduino with {serial_number} was found, but port check was not passed: {comments}.'
        return False, f"Could not find an Arduino {serial_number}. Check connection."

    def _get_reply_from_arduino(self, device_id: Union[int, str], all_lines=False) -> Union[str, List[str], None]:
        sleep(0.05)
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

        device = self.axes_stpmtr[device_id]
        arduino_serial = device.arduino_serial
        if all_lines:
            res = arduino_serial.readlines()
        else:
            res = arduino_serial.readline()

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

    def _get_number_hardware_devices(self):
        return len(self.axes_stpmtr)

    def _get_position_axis(self, device_id: Union[int, str]) -> Tuple[bool, int]:
        self._send_to_arduino(device_id, 'GET POS')
        rcv = self._get_reply_from_arduino(device_id, True)
        if rcv[1] == 0:
            pos = rcv[0]
        else:
            pos = 0
        self._hardware_devices[device_id].position = pos
        self._write_positions_to_file(positions=self._form_axes_positions())
        return True, ''

    def _move_axis_to(self, device_id: Union[int, str], go_pos: Union[float, int]) -> Tuple[bool, str]:
        res, comments = self._change_device_status_local(self.axes_stpmtr[device_id], 2)
        device = self.axes_stpmtr[device_id]
        if res:
            interrupted = False
            self._send_to_arduino(device_id, f'MOVE ABS {float(go_pos)}')
            rcv = self._get_reply_from_arduino(device_id)
            if rcv == 'STARTED':
                timeout = True
                for i in range(50):
                    rcv = self._get_reply_from_arduino(device_id)
                    if rcv == 0:
                        timeout = False
                        break
                    sleep(.5)
                if timeout:
                    rcv = -4  # timeout

            if rcv != 0:
                res, comments = False, f'Movement of Axis with id={device_id}, name={device.name} did not start. ' \
                                       f'Error {rcv}.'
            else:
                res, comments = True, f'Movement of Axis with id={device_id}, name={device.name} was finished.'

            device.arduino_serial.flush()
            sleep(0.1)
            _, _ = self._get_position_axis(device_id)
        _, _ = self._change_device_status_local(self.axes_stpmtr[device_id], 1, force=True)
        return res, comments

    def _release_hardware(self) -> Tuple[bool, str]:
        res, comments = [], ''
        for device in self._hardware_devices.values():
            r, com = self._change_device_status_local(device, 0, True)
            if r:
                device.arduino_serial.close()
                device.arduino_serial = None
            res.append(r)
            comments = join_smart_comments(comments, com)
        return all(res), comments

    def _setup(self) -> Tuple[Union[bool, str]]:
        res, comments = self._set_move_parameters()
        if res:
            return self._setup_pins()
        else:
            return res, comments

    def _set_move_parameters_axes(self, must_have_param: Dict[int, Set[str]] = None):
        must_have_param = {'55838333832351518082': set(['microsteps', 'conversion_step_mm', 'basic_unit']),
                           '75833353934351B05090': set(['microsteps', 'conversion_step_mm', 'basic_unit'])
                           }
        return super()._set_move_parameters_axes(must_have_param)

    def _send_to_arduino(self, device_id: Union[str, int], cmd: str) -> Tuple[bool, str]:
        if self.ctrl_status.connected:
            device = self.axes_stpmtr[device_id]
            device.arduino_serial.write(cmd.encode('utf-8'))
            sleep(0.05)

    def _set_pos_axis(self, device_id: Union[int, str], pos: Union[int, float]) -> Tuple[bool, str]:
        res, comments = False, ''
        self._send_to_arduino(device_id, f'SET POS {pos}')
        rcv = self._get_reply_from_arduino(device_id, True)
        if rcv[0] == 0:
            res, comments = self._get_position_axis(device_id)
        else:
            res, comments = False, rcv
        return res, comments

    def _stop_axis(self, device_id: Union[int, str]) -> Tuple[bool, str]:
        return False, f'Device {device_id} cannot be stopped by user. Wait controller to finish its movement.'
