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
import zlib

from tango import AttrWriteType, DispLevel, DevState
from tango.server import attribute, command, device_property
from taurus import Device
from taurus.core import TaurusDevState

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

    parameters = device_property(dtype=str)

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
            self.dir_pin = int(self.parameters['dir_pin'])
            self.pulse_pin = int(self.parameters['pulse_pin'])
            self.enable_pin = int(self.parameters['enable_pin'])
            self.microstep = int(self.parameters['microstep'])
            self.step_mm = self.parameters['step_mm']
            self.delay_time = int(self.parameters['delay_time'])
            self.dt = int(self.parameters['dt'])
            self.enable_ds = Device(self.parameters['enable_ds'])
            self.dir_ds = Device(self.parameters['dir_ds'])
            self.pulse_ds = Device(self.parameters['pulse_ds'])
            error, errors = self.check_controlled_devices()

            if error:
                self.error(str(errors))
            else:
                argreturn = self.device_id, self.device_id
        self._device_id_internal, self._uri = argreturn
        from os.path import exists
        file_exists = exists(f'{self.friendly_name}_position.txt')
        if file_exists:
            with open(f'{self.friendly_name}_position.txt', 'r') as f:
                line = f.readline()
                self._position = float(line)
        else:
            with open(f'{self.friendly_name}_position.txt', 'w') as f:
                f.write('0')

    def check_controlled_devices(self):
        active = {'enable_ds': self.enable_ds.state, 'dir_ds': self.dir_ds.state, 'pulse_ds': self.pulse_ds.state}
        error = False
        errors = []
        for name, value in active.items():
            if value != TaurusDevState.Ready:
                error = True
                errors.append(f'State of {name} is {value}')
        return error, errors

    def read_position_local(self) -> Union[int, str]:
        return 0

    def write_position_local(self, pos) -> Union[int, str]:
        self.move_axis(pos)
        return 0

    def define_position_local(self, position) -> Union[str, int]:
        self._position = position
        with open(f'{self.friendly_name}_position.txt', 'w') as f:
            f.write(str(self._position))
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
        rel_pos = pos - self._position

        if rel_pos > 0:
            dir_state = 1
            dir = 1
        else:
            dir_state = 0
            dir = -1
        self.dir_ds.set_pin_state([self.dir_pin, dir_state])

        microsteps = abs(int(rel_pos / self.step_mm * self.microstep))

        if microsteps != 0:
            self.enable_ds.set_pin_state([self.enable_pin, 0])  # enable controller
            order_name = self.pulse_ds.register_order([self.pulse_pin, microsteps, self.dt, self.delay_time])

            already_done = 0
            for i in range(120):
                sleep(2)
                ready = self.pulse_ds.is_order_ready(order_name)
                if not ready:
                    done = self.pulse_ds.give_pulses_done(order_name)
                    self._position += dir * (done - already_done) / self.microstep * self.step_mm
                    already_done = done
                else:
                    order = eval(self.pulse_ds.give_order(order_name))
                    order = zlib.decompress(order)
                    microsteps_done = int(order)
                    self._position += dir * (microsteps_done - already_done) / self.microstep * self.step_mm
                    break

            with open(f'{self.friendly_name}_position.txt', 'w') as f:
                f.write(str(self._position))
            self.enable_ds.set_pin_state([self.enable_pin, 1])  # disable controller
        return 0

    def stop_movement_local(self) -> Union[int, str]:
        return 'Cannot be stopped by user. Code on Arduino is wrong.'

    def get_controller_status_local(self) -> Union[int, str]:
        error, errors = self.check_controlled_devices()
        if not error:
            self.set_state(DevState.ON)
            return super().get_controller_status_local()
        else:
            self.set_state(DevState.FAULT)
            return f'{errors}'

    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        self.archive_state.update({'position': (self.get_pos, 'float16')})


if __name__ == "__main__":
    DS_DenisBox_Motor.run_server()
