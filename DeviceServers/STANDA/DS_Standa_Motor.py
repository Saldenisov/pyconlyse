#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import ctypes

from typing import Tuple, Union
import random
from time import sleep
from pathlib import Path
app_folder = Path(__file__).resolve().parents[2]
sys.path.append(str(app_folder))

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property


from ximc import (lib, arch_type, ximc_dir, EnumerateFlags, get_position_t, Result,
                  controller_name_t, status_t, set_position_t, PositionFlags, status_t, device_information_t,
                  string_at, serial_number_t)

try:
    from DeviceServers.General.DS_Motor import DS_MOTORIZED_MONO_AXIS
except ModuleNotFoundError:
    from General.DS_Motor import DS_MOTORIZED_MONO_AXIS


class DS_Standa_Motor(DS_MOTORIZED_MONO_AXIS):
    """"
    Device Server (Tango) which controls the Standa motorized equipment using libximc.dll
    """
    _version_ = '0.4'
    _model_ = 'STANDA step motor'
    polling_local = 1500

    unit = device_property(dtype=str, default_value='')
    conversion = device_property(dtype=float, default_value=1.0)
    ip_address = device_property(dtype=str, default_value='10.20.30.204')

    # if it is done so leave it like this
    position = attribute(label="Position", dtype=float, display_level=DispLevel.OPERATOR,
                         access=AttrWriteType.READ_WRITE, format="8.4f", doc="the position of axis",
                         polling_period=polling_local, abs_change=0.001)

    @attribute(label='Temperature', access=AttrWriteType.READ, display_level=DispLevel.OPERATOR, unit='deg',
               polling_period=polling_local, doc="Temperature in tenths of degrees C.")
    def temperature(self):
        return self._temperature

    @attribute(label='Power current', access=AttrWriteType.READ, display_level=DispLevel.OPERATOR, unit='mA',
               polling_period=polling_local)
    def power_current(self):
        return self._power_current

    @attribute(label='Power voltage', access=AttrWriteType.READ, display_level=DispLevel.OPERATOR, unit='V',
               polling_period=polling_local)
    def power_voltage(self):
        return self._power_voltage

    @attribute(label='Power status', access=AttrWriteType.READ, dtype=str, display_level=DispLevel.OPERATOR,
               polling_period=polling_local)
    def power_status(self):
        return self._power_status

    def init_device(self):
        self._power_status = self.POWER_STATES[0]
        self._temperature = None
        self._power_current = 0
        self._power_voltage = 0
        super().init_device()
        attr_prop = self.position.get_properties()
        attr_prop.unit = self.unit
        self.position.set_properties(attr_prop)
        self.turn_on()

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            self.info(f"Searching for STANDA device {self.device_id}", True)
            lib.set_bindy_key(str(Path(ximc_dir / arch_type / "keyfile.sqlite")).encode("utf-8"))
            # Enumerate devices
            probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
            enum_hints = f"addr={self.ip_address}".encode('utf-8')
            # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
            devenum = lib.enumerate_devices(probe_flags, enum_hints)
            device_counts = lib.get_device_count(devenum)
            if device_counts > 0:
                for device_id_internal_seq in range(device_counts):
                    uri = lib.get_device_name(devenum, device_id_internal_seq)
                    device_id = lib.open_device(uri)
                    x_serial = ctypes.c_uint()
                    result = lib.get_serial_number(device_id, ctypes.byref(x_serial))
                    self._device_id_internal = device_id
                    self.turn_off_local()
                    serial = int(x_serial.value)
                    if int(self.device_id) == int(x_serial.value):
                        argreturn = device_id, uri
                        break
        self.info(f'Result: {argreturn}', True)
        return argreturn

    def read_position_local(self) -> Union[int, str]:
        pos = get_position_t()
        wait = random.randint(1, 10)
        sleep(wait / 1000.)
        result = lib.get_position(self._device_id_internal, ctypes.byref(pos))
        if result == Result.Ok:
            pos_microsteps = pos.Position * 256 + pos.uPosition
            pos_basic_units = pos_microsteps / 256
            self._position = round(pos_basic_units / self.conversion, 3)
            return 0
        else:
            return f'Could not read position of {self.device_name}: {result}.'

    def write_position_local(self, pos) -> Union[int, str]:
        self.move_axis(pos)
        return 0

    def _standa_error(self, error: int) -> Tuple[bool, str]:
        # TODO: finish filling different errors values
        if error == 0:
            res, comments = True, ''
        elif error == -1:
            res, comments = False, 'Standa: generic error.'
        else:
            res, comments = False, 'Standa: unknown error.'

        return res, comments

    #Commands
    def define_position_local(self, position) -> Union[str, int]:
        position = position * self.conversion
        pos_steps = int(position // 1)
        pos_microsteps = int(position % 1 * 256)
        pos_standa = set_position_t()
        pos_standa.Position = ctypes.c_int(pos_steps)
        pos_standa.uPosition = ctypes.c_int(pos_microsteps)
        pos_standa.EncPosition = ctypes.c_longlong(0)
        pos_standa.PosFlags = ctypes.c_uint(PositionFlags.SETPOS_IGNORE_ENCODER)
        result = lib.set_position(self._device_id_internal, ctypes.byref(pos_standa))
        if result == Result.Ok:
            return 0
        else:
            return f'Could not define position of {self.device_name}: {result}.'

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.info(f'Searching for device: {self.device_id}', True)
            self._device_id_internal, self._uri = self.find_device()

        if self._device_id_internal == -1:
            return f'Could NOT turn on {self.device_name}: Device could not be found.'

        res = lib.open_device(self._uri)

        if res >= 0:
            self._device_id_internal = res
            self.set_state(DevState.ON)
            self.stop_movement_local()
            self.read_position_local()
            return 0
        else:
            self.set_state(DevState.FAULT)
            return f'Could NOT turn on {self.device_name}: {res}.'

    def turn_off_local(self) -> Union[int, str]:
        arg = ctypes.cast(self._device_id_internal, ctypes.POINTER(ctypes.c_int))
        result = lib.close_device(ctypes.byref(arg))
        sleep(0.05)
        if result == 0:
            self.set_state(DevState.OFF)
            self._device_id_internal = -1
            self._uri = ''
            return 0
        else:
            self.set_state(DevState.FAULT)
            return self.error(f'Could not turn off device {self.device_name}: {result}.')

    def move_axis_local(self, pos) -> Union[int, str]:
        pos = pos * self.conversion
        microsteps = int(pos % 1 * 256)
        steps = int(pos // 1)
        result = lib.command_move(self._device_id_internal, steps, microsteps)
        self.set_state(DevState.MOVING)
        if result == Result.Ok:
            result = lib.command_wait_for_stop(self._device_id_internal, self.wait_time)
        else:
            return f'Move command for {self.device_name} did NOT work: {result}.'

        if result != Result.Ok:
            return f'{self.device_name} did NOT stop moving yet: {result}.'
        else:
            self.set_state(DevState.ON)
            self.stop_movement_local()
            return 0

    def stop_movement_local(self) -> Union[int, str]:
        result = lib.command_stop(self._device_id_internal)
        if result == 0:
            self.state = DevState.ON
            self.info(f"Axis movement of device {self.device_name} was stopped by user.")
            return 0
        else:
            return f"Axis movement of device {self.device_name} WAS NOT stopped by user."

    def get_controller_status_local(self) -> Union[int, str]:
        x_status = status_t()
        # Different STANDA controllers call xilib at different times
        wait = random.randint(10, 50)
        sleep(wait / 1000.)
        result = lib.get_status(self._device_id_internal, ctypes.byref(x_status))
        if result == Result.Ok:
            self._temperature = x_status.CurT / 10.0
            self._power_current = x_status.Ipwr
            self._power_voltage = x_status.Upwr / 100.0
            self._power_status = self.POWER_STATES[x_status.PWRSts]
            if self._status_check_fault > 0:
                self._status_check_fault = 0
            return super().get_controller_status_local()
        else:
            self._status_check_fault += 1
            if self._status_check_fault > 10:
                self.set_state(DevState.FAULT)
                self._status_check_fault = 0
                self.init_device()
            return f'Could not get controller status of {self.device_name}: {result}: N {self._status_check_fault}.'


if __name__ == "__main__":
    DS_Standa_Motor.run_server()
