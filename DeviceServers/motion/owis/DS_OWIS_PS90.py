#!/usr/bin/env python



from sys import modules as _refactor_modules

import ast
import os
import sys
from pathlib import Path

p = os.path.realpath(__file__)

app_folder = Path(p).resolve().parents[0]
app_folder1 = Path(p).resolve().parents[3]
sys.path.append(str(app_folder1))

from DeviceServers.motion.owis.owis_ps90_parts_ps90tcpadapter import _bind_owis_ps90_parts_ps90tcpadapter
from DeviceServers.motion.owis.owis_ps90_methods_pos1 import _bind_owis_ps90_methods_pos1
from DeviceServers.motion.owis.owis_ps90_methods_read_position_axis_local import _bind_owis_ps90_methods_read_position_axis_local
from DeviceServers.motion.owis.owis_ps90_methods_motor_on_ps90 import _bind_owis_ps90_methods_motor_on_ps90

import ctypes
import time
from threading import Thread
from time import sleep
from typing import Optional, Tuple, Union

from tango import AttrWriteType, DevState, DeviceProxy, DispLevel
from tango.server import attribute, device_property, command

from utilities.tools.decorators import development_mode

dev_mode = False
# Strange delay for ps90.dll
time_ps_delay = 0.005

try:
    from DeviceServers.base.motor import DS_MOTORIZED_MULTI_AXES
    from DeviceServers.base.hardware_lifecycle import (
        HardwareConnectionState,
        InitializationState,
    )
except ModuleNotFoundError:
    from base.motor import DS_MOTORIZED_MULTI_AXES
    from base.hardware_lifecycle import HardwareConnectionState, InitializationState


_owis_ps90_parts_ps90tcpadapter = _bind_owis_ps90_parts_ps90tcpadapter(_refactor_modules[__name__])
_PS90TcpAdapter = _owis_ps90_parts_ps90tcpadapter["_PS90TcpAdapter"]
del _owis_ps90_parts_ps90tcpadapter


class DS_OWIS_PS90(DS_MOTORIZED_MULTI_AXES):
    """ "
    Device Server (Tango) which controls the OWIS delay lines using ps90.dll
    """

    RULES = {
        **DS_MOTORIZED_MULTI_AXES.RULES,
        # Idempotent bring-up command: allowed even when already ON
        "ensure_on": [
            DevState.OFF,
            DevState.FAULT,
            DevState.STANDBY,
            DevState.INIT,
            DevState.ON,
        ],
        # Keep status polling active in FAULT so reconnection logic can self-heal.
        "get_controller_status": [
            DevState.ON,
            DevState.MOVING,
            DevState.RUNNING,
            DevState.INIT,
            DevState.FAULT,
        ],
    }

    baudrate = device_property(dtype=int, default_value=9600)
    com_port = device_property(dtype=int, default_value=4)
    interface = device_property(dtype=int, default_value=0)
    control_unit_id = device_property(dtype=int, default_value=1)
    serial_number = device_property(dtype=int)
    transport = device_property(dtype=str, default_value="tcp")
    controller_ip = device_property(dtype=str, default_value="")
    controller_port = device_property(dtype=int, default_value=8777)
    tcp_timeout = device_property(dtype=float, default_value=5.0)
    tcp_command_delay = device_property(dtype=float, default_value=0.005)
    tcp_velocity_scale = device_property(dtype=float, default_value=16.0)
    tcp_velocity_scale_map = device_property(dtype=str, default_value="")
    allow_high_current_level = device_property(dtype=bool, default_value=False)
    ovis_tcp_strict_init_profile = device_property(dtype=bool, default_value=True)
    ovis_tcp_current_level = device_property(dtype=int, default_value=0)
    ovis_tcp_hold_current_percent = device_property(dtype=int, default_value=38)
    ovis_tcp_drive_current_percent = device_property(dtype=int, default_value=50)
    ovis_tcp_init_ready_timeout = device_property(dtype=float, default_value=6.0)
    ovis_tcp_init_poll_interval = device_property(dtype=float, default_value=0.05)
    ovis_tcp_keep_motor_on = device_property(dtype=bool, default_value=True)
    power_dependency_device = device_property(dtype=str, default_value="")
    power_dependency_output_id = device_property(dtype=int, default_value=0)
    recovery_connect_attempts = device_property(dtype=int, default_value=3)
    recovery_attempt_delay_seconds = device_property(dtype=float, default_value=1.0)
    recovery_pause_seconds = device_property(dtype=float, default_value=8.0)

    _version_ = "0.3"
    _model_ = "OWIS controller PS90 multi-axes 4 axes"
    recovery_fault_threshold = 3

    _owis_ps90_methods_pos1 = _bind_owis_ps90_methods_pos1(_refactor_modules[__name__])
    pos1 = (attribute(
        label="Axis 1 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    ))(_owis_ps90_methods_pos1["pos1"])

    write_pos1 = _owis_ps90_methods_pos1["write_pos1"]

    pos2 = (attribute(
        label="Axis 2 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    ))(_owis_ps90_methods_pos1["pos2"])

    write_pos2 = _owis_ps90_methods_pos1["write_pos2"]

    pos3 = (attribute(
        label="Axis 3 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    ))(_owis_ps90_methods_pos1["pos3"])

    write_pos3 = _owis_ps90_methods_pos1["write_pos3"]

    pos4 = (attribute(
        label="Axis 4 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    ))(_owis_ps90_methods_pos1["pos4"])

    write_pos4 = _owis_ps90_methods_pos1["write_pos4"]

    get_pos = _owis_ps90_methods_pos1["get_pos"]

    def init_device(self):
        super().init_device()
        self._next_recovery_attempt_ts = 0.0
        self._last_recovery_wait_log_ts = 0.0
        self._controller_connection_status = "initialising"
        self.follow = {}
        # A server start must never initialise axes or energise motors.  Probe
        # transport only; an explicit turn_on/ensure_on performs axis setup.
        self.find_device()

    def _read_power_dependency_state(self) -> tuple[Union[bool, None], str]:
        """Read configured Netio output without changing it.

        A controller without supply voltage is expected to be unavailable.  A
        configured PDU dependency lets the server report OFF rather than
        treating that condition as a communication/recovery failure.
        """
        return super()._read_power_dependency_state()

    _power_dependency_proxy = (staticmethod)(_owis_ps90_methods_pos1["_power_dependency_proxy"])

    _handle_power_dependency_off = _owis_ps90_methods_pos1["_handle_power_dependency_off"]

    def _handle_power_dependency_unavailable(self, detail: str) -> None:
        self._controller_connection_status = f"Power dependency is unavailable: {detail}"
        super()._handle_power_dependency_unavailable(detail)

    probe_powered_hardware = _owis_ps90_methods_pos1["probe_powered_hardware"]

    _set_off_for_unpowered_controller = _owis_ps90_methods_pos1["_set_off_for_unpowered_controller"]

    controller_connection_status = (attribute(
        label="Controller connection status",
        dtype=str,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
        doc="Power-aware OWIS connection diagnostic without initiating recovery.",
    ))(_owis_ps90_methods_pos1["controller_connection_status"])

    def register_variables_for_archive(self):
        from functools import partial

        super().register_variables_for_archive()
        archive_items = {}
        for axis in sorted(self._delay_lines_parameters.keys()):
            archive_items[f"position_axis_{axis}"] = (partial(self.get_pos, axis), "float16")
        self.archive_state.update(archive_items)

    find_device = _owis_ps90_methods_pos1["find_device"]

    turn_on_local = _owis_ps90_methods_pos1["turn_on_local"]

    turn_off_local = _owis_ps90_methods_pos1["turn_off_local"]

    _attempt_recover_connection = _owis_ps90_methods_pos1["_attempt_recover_connection"]

    is_ensure_on_allowed = _owis_ps90_methods_pos1["is_ensure_on_allowed"]

    ensure_on = (command)(_owis_ps90_methods_pos1["ensure_on"])

    get_controller_status_local = _owis_ps90_methods_pos1["get_controller_status_local"]

    _is_tcp_backend_active = _owis_ps90_methods_pos1["_is_tcp_backend_active"]

    _keep_motor_powered = _owis_ps90_methods_pos1["_keep_motor_powered"]

    init_axis_local = _owis_ps90_methods_pos1["init_axis_local"]

    get_status_axis_local = _owis_ps90_methods_pos1["get_status_axis_local"]
    del _owis_ps90_methods_pos1

    _owis_ps90_methods_read_position_axis_local = _bind_owis_ps90_methods_read_position_axis_local(_refactor_modules[__name__])
    read_position_axis_local = _owis_ps90_methods_read_position_axis_local["read_position_axis_local"]

    set_param_axis_local = _owis_ps90_methods_read_position_axis_local["set_param_axis_local"]

    _set_axis_acceleration_local = _owis_ps90_methods_read_position_axis_local["_set_axis_acceleration_local"]

    _amps_to_percent = _owis_ps90_methods_read_position_axis_local["_amps_to_percent"]

    _apply_axis_currents_local = _owis_ps90_methods_read_position_axis_local["_apply_axis_currents_local"]

    _axis_state_name = _owis_ps90_methods_read_position_axis_local["_axis_state_name"]

    _refresh_axis_state = _owis_ps90_methods_read_position_axis_local["_refresh_axis_state"]

    _ensure_axis_ready_for_motion = _owis_ps90_methods_read_position_axis_local["_ensure_axis_ready_for_motion"]

    turn_on_axis_local = _owis_ps90_methods_read_position_axis_local["turn_on_axis_local"]

    turn_off_axis_local = _owis_ps90_methods_read_position_axis_local["turn_off_axis_local"]

    move_axis_local = _owis_ps90_methods_read_position_axis_local["move_axis_local"]

    follow_after_moving = _owis_ps90_methods_read_position_axis_local["follow_after_moving"]

    stop_axis_local = _owis_ps90_methods_read_position_axis_local["stop_axis_local"]

    define_position_axis_local = _owis_ps90_methods_read_position_axis_local["define_position_axis_local"]

    # Hardware controller functions
    # Be aware that OWIS PS90 counts axis from 1, not from 0!!!
    _connect_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_read_position_axis_local["_connect_ps90"])

    _connect_simple_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_read_position_axis_local["_connect_simple_ps90"])

    _convert_axis_state_format_ps90 = _owis_ps90_methods_read_position_axis_local["_convert_axis_state_format_ps90"]

    _disconnect_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_read_position_axis_local["_disconnect_ps90"])

    _free_switch_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_read_position_axis_local["_free_switch_ps90"])

    _get_connection_info = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_read_position_axis_local["_get_connection_info"])

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _get_serial_number_ps90(self, control_unit: int) -> Tuple[Union[bool, str]]:
        """Synopsis
                    long PS90_GetSerNumber (long Index, char* pszBuffer, long Length)


        Description
        read serial number of the control unit


        Parameters
        ----------
        Index control unit index (1-10)
        pszBuffer address of the buffer for reading
        Length length of the buffer



        Returns
        -------
        length of the string


        Example
        Read serial number of the control unit (Index=1):
        char szString[25];
        long len = PS90_GetSerNumber(1, 1, szString, 25);
        long error = PS90_GetReadError(1);

        """
        buf = ctypes.create_string_buffer(25)
        control_unit_c = ctypes.c_long(control_unit)
        try:
            self.lib.PS90_GetSerNumber(control_unit_c, buf, 25)
            error = self.__get_read_error_ps90(control_unit)
            if error != 0:
                return -1
            result = buf.value.decode("utf-8", errors="ignore").strip()
            if not result:
                return -1
            return int(result)
        except Exception:
            return -1

    @development_mode(dev=dev_mode, with_return=(3, "DEV MODE"))
    def _get_axis_state_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[int, bool, str]]:
        """Long PS90_GetAxisState (long Index, long AxisId)
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
        res = self.lib.PS90_GetAxisState(control_unit, axis)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(0.0, "DEV MODE"))
    def _get_target_ex_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[float, bool, str]]:
        """Double PS90_GetTargetEx (long Index, long AxisId)
        Description
        read target position or distance of an axis (values in selected unit)

        Parameters
        ----------
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
        res = self.lib.PS90_GetTargetEx(control_unit, axis) / 10000
        sleep(time_ps_delay)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(0.0, "DEV MODE"))
    def _get_pos_ex_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[float, bool, str]]:
        """Double PS90_GetPositionEx (long Index, long AxisId)
        Description
        read current value of a position counter of an axis (values in selected unit)

        Example:
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
        pitch = self._delay_lines_parameters[axis]["pitch"]
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_GetPosition(control_unit, axis) / 10000 * pitch
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        error = self._error_OWIS_ps90(error, 1)
        return res, error

    @development_mode(dev=dev_mode, with_return=(0.0, "DEV MODE"))
    def _get_target_mode_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[float, bool, str]]:
        """Description
        read target mode of an axis
        Parameters
        Index control unit index (1-10)
        AxisId axis number (1...9)

        Returns:
        0 – relative positioning (target value is distance)
        1 – absolute positioning (target value is target position)

        Example:
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
        res = self.lib.PS90_GetTargetMode(control_unit, axis)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    _go_target_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_read_position_axis_local["_go_target_ps90"])

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def __get_read_error_ps90(self, control_unit: int) -> int:
        if not isinstance(control_unit, ctypes.c_long):
            control_unit = ctypes.c_long(control_unit)
        sleep(time_ps_delay)
        res = self.lib.PS90_GetReadError(control_unit)
        return res

    _motor_init_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_read_position_axis_local["_motor_init_ps90"])
    del _owis_ps90_methods_read_position_axis_local

    _owis_ps90_methods_motor_on_ps90 = _bind_owis_ps90_methods_motor_on_ps90(_refactor_modules[__name__])
    _motor_on_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_motor_on_ps90"])

    _motor_off_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_motor_off_ps90"])

    _stop_axis_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_stop_axis_ps90"])

    _set_limit_min_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_limit_min_ps90"])

    _set_limit_max_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_limit_max_ps90"])

    _set_position_ex_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_position_ex_ps90"])

    _set_pos_mode_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_pos_mode_ps90"])

    _set_pos_velocity_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_pos_velocity_ps90"])

    _set_stage_attributes_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_stage_attributes_ps90"])

    _set_target_mode_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_target_mode_ps90"])

    _set_target_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_target_ps90"])

    _set_target_ex_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_target_ex_ps90"])

    _set_drive_current_ex_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_drive_current_ex_ps90"])

    _set_hold_current_ex_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_hold_current_ex_ps90"])

    _set_current_level_ps90 = (development_mode(dev=dev_mode, with_return=(True, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_set_current_level_ps90"])

    _get_current_level_ps90 = (development_mode(dev=dev_mode, with_return=(0, "DEV MODE")))(_owis_ps90_methods_motor_on_ps90["_get_current_level_ps90"])

    _error_OWIS_ps90 = _owis_ps90_methods_motor_on_ps90["_error_OWIS_ps90"]
    del _owis_ps90_methods_motor_on_ps90


def main(device_name=None):
    sys.argv.append(device_name)
    DS_OWIS_PS90.run_server()


if __name__ == "__main__":
    DS_OWIS_PS90.run_server()
