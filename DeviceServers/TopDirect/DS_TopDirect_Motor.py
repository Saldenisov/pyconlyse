#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))
from typing import Tuple, Union, List
from time import sleep
import serial
import serial.tools.list_ports


from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property


try:
    from DeviceServers.General.DS_Motor import DS_MOTORIZED_MONO_AXIS
except ModuleNotFoundError:
    from General.DS_Motor import DS_MOTORIZED_MONO_AXIS


class DS_TopDirect_Motor(DS_MOTORIZED_MONO_AXIS):
    RULES = {'set_state_arduino': [DevState.ON, DevState.INIT], **DS_MOTORIZED_MONO_AXIS.RULES}
    """"
    Device Server (Tango) which controls the TOP_DIRECT motorized equipment using home-written Arduino based controller
    """
    _version_ = '0.1'
    _model_ = 'TopDirect step motor under arduino control'
    polling_local = 3500
    _local_sleep = 0.15
    baudrate = device_property(dtype=int, default_value=115200)
    timeout = device_property(dtype=float, default_value=0.5)

    # if it is done so leave it like this
    position = attribute(label="Position", dtype=float, display_level=DispLevel.OPERATOR,
                         access=AttrWriteType.READ_WRITE, unit="mm", format="8.4f",
                         doc="the position of axis")

    # @attribute(label="Arduino state", dtype=str, display_level=DispLevel.OPERATOR,
    #            access=AttrWriteType.READ,
    #            doc="Give state of Arduino.",
    #            abs_change='')
    # def arduino_state(self):
    #     self._send_to_arduino('GET STATE')
    #     result = self._get_reply_from_arduino()
    #     self._arduino_state = result
    #     return str(self._arduino_state)

    def init_device(self):
        self._arduino_lock = False
        self._arduino_state = 'NOT_ACTIVE'
        self.arduino_serial = None
        super().init_device()
        self.turn_on()

    def _check_arduino_port(self, com_port: serial) -> Tuple[bool, str]:
        try:
            ser = serial.Serial(com_port)
            ser.close()
            return True, ''
        except serial.SerialException as e:
            return False, str(e)

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            serial_number = str(self.device_id)
            self.info(f"Searching for TOP_DIRECT device {self.device_id}", True)
            for pinfo in serial.tools.list_ports.comports():
                if pinfo.serial_number == serial_number:
                    res, comments = self._check_arduino_port(pinfo.device)
                    if res:
                        argreturn = pinfo.device, serial_number.encode('utf-8')
                    else:
                       self.error(f'Arduino with {serial_number} was found, but port check was not passed: {comments}.')
                    break
        print(f'Result: {argreturn}')
        return argreturn

    def read_position_local(self) -> Union[int, str]:
        self._send_to_arduino('GET POS')
        reply = self._get_reply_from_arduino(True)
        if reply:
            self._position = reply[0]
            data = self.form_archive_data(self._position, f'position', dt='float16')
            self.write_to_archive(data)
            return 0
        else:
            return f'Could not read position of {self.device_name}: {reply}.'

    def write_position_local(self, pos) -> Union[int, str]:
        self.move_axis(pos)
        return 0

    def _topdirect_error(self, error: int) -> Tuple[bool, str]:
        if error == 0:
            res, comments = True, ''
        elif error == -1:
            res, comments = False, 'Out of range'
        elif error == -1:
            res, comments = False, 'Wrong cmd structure'
        else:
            res, comments = False, 'Unknown error'
        return res, comments

    def define_position_local(self, position) -> Union[str, int]:
        self._send_to_arduino(f'SET POS {position}')
        result = self._get_reply_from_arduino()
        if result == 0:
            return 0
        else:
            return f'Could not define position of {self.device_name}: {result}.'

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.info(f'Searching for device: {self.device_id}', True)
            self._device_id_internal, self._uri = self.find_device()

        if self._device_id_internal == -1:
            return f'Could NOT turn on {self.device_name}: Device could not be found.'

        try:
            self.arduino_serial = serial.Serial(self._device_id_internal, timeout=self.timeout, baudrate=self.baudrate)
            sleep(2)
            self._send_to_arduino('GET STATE')
            reply = self._get_reply_from_arduino(all_lines=True)
            print(reply)
            if 'INITIALIZED' in reply or 'NOT_ACTIVE' in reply or 'READY' in reply:
                res = True
            else:
                res = False
        except Exception:
            res = False

        if res:
            self.set_state(DevState.ON)
            self.read_position()
            return 0
        else:
            self.set_state(DevState.FAULT)
            return f'Could NOT turn on {self.device_name}: {res}.'

    def turn_off_local(self) -> Union[int, str]:
        result = False
        if result == 0:
            self.set_state(DevState.OFF)
            self._device_id_internal = -1
            self._uri = ''
            if self.arduino_serial:
                self.arduino_serial.close()
                self.arduino_serial = None
            return 0
        else:
            self.set_state(DevState.FAULT)
            return self.error(f'Could not turn off device {self.device_name}: {result}.')

    def _wait_unlock_arduino(self):
        i = 0
        while self._arduino_lock:
            sleep(0.01)
            if not self._arduino_lock or i > 200:
                break
            i += 1

    def _get_reply_from_arduino(self, all_lines=False) -> Union[str, List[str], None]:

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

        self._wait_unlock_arduino()

        if self.arduino_serial and not self._arduino_lock:
            sleep(self._local_sleep)
            self._arduino_lock = True
            self.info('Locking Arduino')
            arduino_serial = self.arduino_serial
            try:
                if all_lines:
                    res = arduino_serial.readlines()
                else:
                    res = arduino_serial.readline()
                self.info(f'Received from Arduino: {res}', True)

            except Exception as e:
                self.info(f'{e}', True)
                res = None
            self._arduino_lock = False
            self.info('Unlocking Arduino')

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
        else:
            return None

    def _send_to_arduino(self, cmd: str) -> Union[int, str]:
        if self.arduino_serial:
            try:
                sleep(self._local_sleep)
                self._wait_unlock_arduino()
                self.info(f'Sending to Arduino: {cmd}', True)
                self.arduino_serial.write(cmd.encode('utf-8'))
                sleep(self._local_sleep)
                return True, ''
            except Exception as e:
                return False, str(e)

    def move_axis_local(self, pos) -> Union[int, str]:
        if self._arduino_state != 1:
            self.set_state_arduino(1)
        self._send_to_arduino(f'MOVE ABS {pos}')
        sleep(2)
        result = self._get_reply_from_arduino(True)
        print(result)
        if result[0] == 'STARTED':
            return 0
        else:
            return f'Move command for {self.device_name} did NOT work: {result}.'

    def stop_movement_local(self) -> Union[int, str]:
        return 'Cannot be stopped by user. Code on Arduino is wrong.'

    def get_controller_status_local(self) -> Union[int, str]:
        if self.arduino_serial.is_open:
            self.set_state(DevState.ON)
            if self._status_check_fault > 0:
                self._status_check_fault = 0
            return super().get_controller_status_local()
        else:
            self._status_check_fault += 1
            if self._status_check_fault > 10:
                self.set_state(DevState.FAULT)
                self._status_check_fault = 0
                self.init_device()
            return f'Could not get controller status of {self.device_name}: N {self._status_check_fault}.'

    @command(dtype_in=int, doc_in="Takes state of arduino as int.")
    def set_state_arduino(self, state: int):
        self.debug_stream(f"Setting state of Arduino {self.device_name}.")
        state_ok = self.check_func_allowance(self.turn_off)
        if state_ok == 1:
            self._send_to_arduino(f'SET STATE {state}')
            res = self._get_reply_from_arduino()
            if res != 0:
                self.error_stream(f"{res}")
                self.info(f'Could not set state of Arduino to {state}.')
            else:
                self._arduino_state = state
                self.info(f"Arduino state was set to {state}.", True)

    @command(doc_in="Resets ARDUINO")
    def reset(self):
        self._send_to_arduino(f'RESET')
        return 0


if __name__ == "__main__":
    DS_TopDirect_Motor.run_server()
