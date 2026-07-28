#!/usr/bin/env python


import os
import sys
from pathlib import Path

p = os.path.realpath(__file__)

app_folder = Path(p).resolve().parents[0]

app_folder1 = Path(p).resolve().parents[3]
sys.path.append(str(app_folder1))
app_folder2 = Path(p).resolve().parents[3]
sys.path.append(str(app_folder2))

import ctypes
from pathlib import Path
from typing import Tuple, Union

from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, device_property

dev_mode = False
# Strange delay for ps90.dll
time_ps_delay = 0.05
dll_path = str(app_folder / "ps90.dll")
lib = ctypes.WinDLL(dll_path)

try:
    from DeviceServers.General.DS_Motor import DS_MOTORIZED_MONO_AXIS
except ModuleNotFoundError:
    from DeviceServers.base.motor import DS_MOTORIZED_MONO_AXIS


class DS_Owis_delay_line(DS_MOTORIZED_MONO_AXIS):
    """ "
    Device Server (Tango) which controls the OWIS delay lines using ps90.dll
    """

    internal_id = device_property(dtype=int)
    keep_on = device_property(dtype=bool, default_value=False)
    gear_ratio = device_property(dtype=float, default_value=1.0)
    pitch = device_property(dtype=float, default_value=1.0)
    speed = device_property(dtype=float, default_value=8.0)
    revolution = device_property(dtype=int, default_value=200)
    mother_device = device_property(
        dtype=str, default_value="manip/general/DS_OWIS_PS90"
    )

    _version_ = "0.1"
    _model_ = "OWIS step motor"

    position = attribute(
        label="Position",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        unit="mm",
        format="8.4f",
        doc="the position of axis",
        polling_period=100,
    )

    def define_position_local(self, position):
        res, comments = self._set_position_ex_ps90(
            self.control_unit_id, self._device_id_internal, position
        )
        if not res:
            return (
                f"Device {self.device_name} _set_position func did NOT work "
                f"{comments}."
            )
        return 0

    def find_device(self) -> Tuple[int, str]:
        res, comments = self._connect_ps90(
            self.control_unit_id,
            interface=self.interface,
            port=self.com_port,
            baudrate=self.baudrate,
        )
        # TODO: this is stupid
        if comments == "access react_denied  (com_port is busy)":
            res = 1

        if res:
            self._device_id_internal = int(self.device_id)
            return self._device_id_internal, f"{self.device_name}".encode()
        return -1, b""

    def get_controller_status_local(self):
        res, comments = self._get_axis_state_ps90(
            self.control_unit_id, self._device_id_internal
        )
        if res == 0:
            self.set_state(DevState.FAULT)
            return f"Device {self.device_name} is not active: {comments}."
        elif res == 1:
            self.set_state(DevState.FAULT)
            return f"Device {self.device_name} is not initialized: {comments}."
        elif res == 2:
            self.set_state(DevState.STANDBY)
            return 0
        elif res == 3:
            self.set_state(DevState.ON)
            return 0
        self.set_state(DevState.FAULT)
        return f"Device {self.device_name} returned unknown axis state {res}: {comments}."

    def init_device(self):
        self._mother_available = False
        super().init_device()
        if not self._mother_available:
            self.error(
                f"The mother device {self.mother_device} is not available. First start it."
            )
        self.turn_on()

    def read_position_local(self):
        res, com = self._get_pos_ex_ps90(self.control_unit_id, self._device_id_internal)
        if not com:
            self._position = res
            return 0
        else:
            return (
                f"Device {self.device_name} reading position was not successful: "
                f"{com}."
            )

    def _set_device_param(self):
        res1, com1 = self._set_stage_attributes_ps90(
            self.control_unit_id,
            self._device_id_internal,
            self.pitch,
            self.revolution,
            self.gear_ratio,
        )
        res2, com2 = self._set_pos_velocity_ps90(
            self.control_unit_id, self._device_id_internal, self.speed
        )

        res3, com3 = self._set_limit_min_ps90(
            self.control_unit_id, self._device_id_internal, self.limit_min
        )

        res4, com4 = self._set_limit_max_ps90(
            self.control_unit_id, self._device_id_internal, self.limit_max
        )

    def turn_on_local(self):
        res, comments = self._motor_init_ps90(
            self.control_unit_id, self._device_id_internal
        )
        if not res:
            self.set_state(DevState.FAULT)
            return (
                f"Device {self.device_name} motor_init func did NOT work "
                f"{comments}."
            )

        self.set_state(DevState.ON)
        res, comments = self._set_target_mode_ps90(
            self.control_unit_id, self._device_id_internal, 1
        )
        if not res:
            self.set_state(DevState.FAULT)
            return (
                f"Device {self.device_name} set_target_mode to ABS did NOT work "
                f"{comments}."
            )
        if not self.keep_on:
            return self.on_off_motor(False)
        return 0

    def on_off_motor(self, on=False):
        if on:
            res, comments = self._motor_on_ps90(
                self.control_unit_id, self._device_id_internal
            )
            if not res:
                self.set_state(DevState.STANDBY)
                return (
                    f"Device {self.device_name} motor_on func did NOT work "
                    f"{comments}."
                )
            else:
                self.set_state(DevState.ON)
                return 0
        else:
            res, comments = self._motor_off_ps90(
                self.control_unit_id, self._device_id_internal
            )
            if not res:
                return (
                    f"Device {self.device_name} motor_off func did NOT work "
                    f"{comments}."
                )
            else:
                self.set_state(DevState.STANDBY)
                return 0

    def turn_off_local(self):
        # TODO: should be finished, if I close connection with PS90, it will effect all of the DLs
        res, comments = self._stop_axis_ps90(
            self.control_unit_id, self._device_id_internal
        )
        if not res:
            return f"Device {self.device_name} stop_axis did NOT work {comments}."
        return self.on_off_motor(False)

    def move_axis_local(self, pos):
        res, comments = self._set_target_ex_ps90(
            self.control_unit_id, self._device_id_internal, pos
        )
        if not res:
            return (
                f"Device {self.device_name} set_target_ex to {pos} did NOT work "
                f"{comments}."
            )
        if self.get_state() == DevState.STANDBY:
            motor_result = self.on_off_motor(True)
            if motor_result != 0:
                return motor_result

        res, comments = self._go_target_ps90(
            self.control_unit_id, self._device_id_internal
        )
        if res:
            self.info_stream(f"Device {self.device_name} started moving.")
            return 0
        return f"Device {self.device_name} did NOT start moving: {comments}."

    def stop_movement_local(self):
        res, comments = self._stop_axis_ps90(
            self.control_unit_id, self._device_id_internal
        )
        if res:
            self.set_state(DevState.ON)
            if not self.keep_on:
                res, comments = self._motor_off_ps90(
                    self.control_unit_id, self._device_id_internal
                )
                if not res:
                    return (
                        f"Device {self.device_name} motor_off func did NOT work "
                        f"{comments}."
                    )
                self.set_state(DevState.STANDBY)
            return 0
        else:
            return f"Device {self.device_name} could not stop it: {comments}."

    def write_position_local(self, pos) -> Union[int, str]:
        return self.move_axis(pos)


def main(device_name=None):
    sys.argv.append(device_name)
    DS_Owis_delay_line.run_server()


if __name__ == "__main__":
    DS_Owis_delay_line.run_server()
