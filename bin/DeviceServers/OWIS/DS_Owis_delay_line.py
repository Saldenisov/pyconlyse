#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import os

from pathlib import Path
import os
p = os.path.realpath(__file__)

app_folder = Path(p).resolve().parents[0]

app_folder1 = Path(p).resolve().parents[1]
sys.path.append(str(app_folder1))
app_folder2 = Path(p).resolve().parents[3]
sys.path.append(str(app_folder2))

from tango import AttrQuality, AttrWriteType, DispLevel, DevState
from tango.server import Device, attribute, command, pipe, device_property

import ctypes

from typing import Tuple, Union
from pathlib import Path
from time import sleep

from utilities.tools.decorators import development_mode
dev_mode = False
# Strange delay for ps90.dll
time_ps_delay = 0.05
dll_path = str(app_folder / 'ps90.dll')
lib = ctypes.WinDLL(dll_path)

try:
    from DS_general import DS_MOTORIZED_MONO_AXIS
except ModuleNotFoundError:
    from bin.DeviceServers.DS_general import DS_MOTORIZED_MONO_AXIS


class DS_Owis_delay_line(DS_MOTORIZED_MONO_AXIS):
    """"
    Device Server (Tango) which controls the OWIS delay lines using ps90.dll
    """
    internal_id = device_property(dtype=int)
    keep_on = device_property(dtype=bool, default_value=False)
    gear_ratio = device_property(dtype=float, default_value=1.0)
    pitch = device_property(dtype=float, default_value=1.0)
    speed = device_property(dtype=float, default_value=8.0)
    revolution = device_property(dtype=int, default_value=200)
    mother_device = device_property(dtype=str, default_value='manip/general/DS_OWIS_PS90')

    _version_ = '0.1'
    _model_ = 'OWIS step motor'

    position = attribute(label="Position", dtype=float,
                         display_level=DispLevel.OPERATOR,
                         access=AttrWriteType.READ_WRITE,
                         unit="mm", format="8.4f",
                         doc="the position of axis",
                         polling_period=100)

    def define_position_local(self, position):
        res, comments = self._set_position_ex_ps90(self.control_unit_id, self._device_id_internal, position)
        if not res:
            self.error_stream(f'Device {self.device_name()} _set_position func did NOT work {comments}.')

    def find_device(self) -> Tuple[int, str]:
        res, comments = self._connect_ps90(self.control_unit_id,
                                           interface=self.interface,
                                           port=self.com_port,
                                           baudrate=self.baudrate)
        # TODO: this is stupid
        if comments == "access react_denied  (com_port is busy)":
            res = 1

        if res:
            self._device_id_internal = int(self.device_id)
            return self._device_id_internal, f'{self.device_name()}'.encode('utf-8')
        else:
            return -1, b''

    def get_controller_status_local(self):
        res, comments = self._get_axis_state_ps90(self.control_unit_id, self._device_id_internal)
        if res == 0:
            self.set_state(DevState.FAULT)
            self.error_stream(f'Device {self.device_name()} is not active.')
        elif res == 1:
            self.set_state(DevState.FAULT)
            self.error_stream(f'Device {self.device_name()} is not initialized.')
        elif res == 2:
            self.set_state(DevState.STANDBY)
        elif res == 3:
            self.set_state(DevState.ON)

    def init_device(self):
        self._mother_available = False
        super().init_device()
        if not self._mother_available:
            self.error(f'The mother device {self.mother_device} is not available. First start it.')
        self.turn_on()

    def read_position_local(self):
        res, com = self._get_pos_ex_ps90(self.control_unit_id, self._device_id_internal)
        if not com:
            self._position = res
        else:
            self.error_stream(f'Device {self.device_name()} reading position was not succeful.')

    def _set_device_param(self):
        res1, com1 = self._set_stage_attributes_ps90(self.control_unit_id,
                                                   self._device_id_internal,
                                                   self.pitch,
                                                   self.revolution,
                                                   self.gear_ratio)
        res2, com2 = self._set_pos_velocity_ps90(self.control_unit_id, self._device_id_internal, self.speed)

        res3, com3 = self._set_limit_min_ps90(self.control_unit_id, self._device_id_internal, self.limit_min)

        res4, com4 = self._set_limit_max_ps90(self.control_unit_id, self._device_id_internal, self.limit_max)

    def turn_on_local(self):
        res, comments = self._motor_init_ps90(self.control_unit_id, self._device_id_internal)
        if not res:
            self.error_stream(f'Device {self.device_name()} motor_init func did NOT work {comments}.')
            self.set_state(DevState.FAULT)
        else:
            self.set_state(DevState.ON)
            res, comments = self._set_target_mode_ps90(self.control_unit_id, self._device_id_internal, 1)
            if not res:
                self.error_stream(f'Device {self.device_name()} set_target_mode to ABS did NOT work {comments}.')
                self.set_state(DevState.FAULT)
            if not self.keep_on:
                self.on_off_motor(self.keep_on)

    def on_off_motor(self, on=False):
        if on:
            res, comments = self._motor_on_ps90(self.control_unit_id, self._device_id_internal)
            if not res:
                self.error_stream(f'Device {self.device_name()} motor_on func did NOT work {comments}.')
                self.set_state(DevState.STANDBY)
            else:
                self.set_state(DevState.ON)
        else:
            res, comments = self._motor_off_ps90(self.control_unit_id, self._device_id_internal)
            if not res:
                self.error_stream(f'Device {self.device_name()} motor_off func did NOT work {comments}.')
            else:
                self.set_state(DevState.STANDBY)

    def turn_off_local(self):
        # TODO: should be finished, if I close connection with PS90, it will effect all of the DLs
        res, comments = self._stop_axis_ps90(self.control_unit_id, self._device_id_internal)
        self.on_off_motor(False)

    def move_axis_local(self, pos):
        res, comments = self._set_target_ex_ps90(self.control_unit_id, self._device_id_internal, pos)
        if not res:
            self.error_stream(f'Device {self.device_name()} set_target_ex to {pos} did NOT work {comments}.')
        else:
            if self.get_state() == DevState.STANDBY:
                self.on_off_motor(True)

            res, comments = self._go_target_ps90(self.control_unit_id, self._device_id_internal)

            if res:
                self.info_stream(f'Device {self.device_name()} started moving.')
            else:
                self.set_state(DevState.MOVING)
                self.error_stream(f'Device {self.device_name()} did NOT started moving {comments}.')

    def stop_movement_local(self):
        res, comments = self._stop_axis_ps90(self.control_unit_id, self._device_id_internal)
        if res:
            self.set_state(DevState.ON)
            if not self.keep_on:
                res, comments = self._motor_off_ps90(self.control_unit_id, self._device_id_internal)
                if not res:
                    self.error_stream(f'Device {self.device_name()} motor_off func did NOT work {comments}.')
        else:
            self.error_stream(f'Device {self.device_name()} could not stop it {comments}.')

    def write_position_local(self, pos) -> Union[int, str]:
        self.move_axis(pos)
        return 0


def main(device_name=None):
    sys.argv.append(device_name)
    DS_Owis_delay_line.run_server()


if __name__ == "__main__":
    DS_Owis_delay_line.run_server()
