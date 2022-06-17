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
from taurus import Device

try:
    from DeviceServers.General.DS_Motor import DS_MOTORIZED_MONO_AXIS
except ModuleNotFoundError:
    from General.DS_Motor import DS_MOTORIZED_MONO_AXIS


class DS_DenisBox_Motor(DS_MOTORIZED_MONO_AXIS):
    RULES = {**DS_MOTORIZED_MONO_AXIS.RULES}
    """"
    Device Server (Tango) which controls the TOP_DIRECT motorized equipment using Denis's box
    """
    _version_ = '0.1'
    _model_ = "TopDirect step motor under Denis's box"
    polling_local = 500
    _local_sleep = 0.15

    enable_ds = device_property(dtype=str)
    enable_pin = device_property(dtype=int)
    dir_ds = device_property(dtype=str)
    dir_pin = device_property(dtype=int)
    pulse_ds = device_property(dtype=str)
    pulse_pin = device_property(dtype=int)
    microstep = device_property(dtype=int)
    dt = device_property(dtype=int)
    delay_time = device_property(dtype=int)
    max_full_steps = device_property(dtype=int)
    step_mm = device_property(dtype=float)

    # if it is done so leave it like this
    position = attribute(label="Position", dtype=float, display_level=DispLevel.OPERATOR,
                         access=AttrWriteType.READ_WRITE, unit="mm", format="8.4f",
                         doc="the position of axis")

    @command(dtype_in=int, doc_in='Sets the width of the TTL pulse in us')
    def set_dt(self, value: int):
        self.dt = value

    @command(dtype_in=int, doc_in='Sets the distance between the TTL pulses in us')
    def set_delay_time(self, value: int):
        self.delay_time = value

    def init_device(self):
        super().init_device()
        self.turn_on()

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b''
        if state_ok:
            self.enable_ds = Device(self.enable_ds)
            self.dir_ds = Device(self.dir_ds)
            self.pulse_ds = Device(self.pulse_ds)
            error, errors = self.check_controlled_devices()

            if error:
                self.error(str(errors))
            else:
                argreturn = self.device_id, self.device_id

        self._device_id_internal, self._uri = argreturn

    def check_controlled_devices(self):
        active = {'enable_ds': self.enable_ds.state, 'dir_ds': self.dir_ds.state, 'pulse_ds': self.pulse_ds.state}
        error = False
        errors = []
        for name, value in active.items():
            if value != DevState.ON:
                error = True
                errors.append(f'State of {name} is {value}')
        return error, errors

    def read_position_local(self) -> Union[int, str]:
        return self._position

    def write_position_local(self, pos) -> Union[int, str]:
        self.move_axis(pos)
        return 0

    def define_position_local(self, position) -> Union[str, int]:
        self._position = position
        return 0

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal != -1:
            self.set_state(DevState.ON)
            return 0
        else:
            self.set_state(DevState.FAULT)
            return 'Cannot turn on, try to initialize'

    def turn_off_local(self) -> Union[int, str]:
        self.set_state(DevState.OFF)
        return 0

    def move_axis_local(self, pos) -> Union[int, str]:
        microsteps = pos / self.step_mm * self.microstep
        self.

    def stop_movement_local(self) -> Union[int, str]:
        return 'Cannot be stopped by user. Code on Arduino is wrong.'

    def get_controller_status_local(self) -> Union[int, str]:
        error, errors = self.check_controlled_devices()
        if not error:
            self.set_state(DevState.ON)
            return super().get_controller_status_local()
        else:
            self.set_state(DevState.FAULT)
            return f'{errors}

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        self.archive_state.update({'position': (self.get_pos, 'float16')})


if __name__ == "__main__":
    DS_TopDirect_Motor.run_server()
