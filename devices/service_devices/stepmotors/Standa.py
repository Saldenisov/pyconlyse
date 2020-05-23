"""
This controller is dedicated to control Standa motorized mirrors
On ELYSE there are 4 motorized mirrors
"""


from typing import List, Tuple, Union, Iterable, Dict, Any, Callable

import logging
import ctypes
import os
from time import sleep
from utilities.tools.decorators import development_mode
from utilities.myfunc import info_msg, unique_id, error_logger
from pathlib import Path
from .stpmtr_controller import StpMtrController, StpMtrError

from devices.service_devices.stepmotors.ximc import (lib, arch_type, ximc_dir, EnumerateFlags, get_position_t, Result,
                                                     controller_name_t, status_t)

module_logger = logging.getLogger(__name__)


dev_mode = False


class StpMtrCtrl_Standa(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._devenum = None  # LP_device_enumeration_t
        self._devices: Dict[int, str] = {}

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        res, comments = self._form_devices_list()
        if res:
            self.device_status.connected = True
        return res, comments

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_axis_flag(flag)
        if res:
            if self.axes[axis_id].status != flag:
                info = ''
                if self.axes[axis_id].status == 2:
                    self._stop_axis(axis_id)
                    info = f' Axis id={axis_id}, name={self.axes[axis_id].name} was stopped.'

                self.axes[axis_id].status = flag
                res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is set to {flag}.' + info
            else:
                res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is already set to {flag}'
        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()

    def _check_if_connected(self) -> Tuple[bool, str]:
        status = status_t()
        if self.axes:
            result = lib.get_status(list(self.axes.keys())[0], ctypes.byref(status))
            if result == Result.Ok:
                self.device_status.connected = True
                comments = ''
            else:
                self.device_status.connected = False
                comments = False, f'No connection with 8SMC5-USB {result}.'

        else:
            self.device_status.connected = False
            comments = f'No connection with 8SMC5-USB, since there are not devices found.'
        return self.device_status.connected, comments

    def _form_devices_list(self) -> Tuple[bool, str]:
        """
        1) enumerates devices 2) count devices 3) checks vs database 4) form dict of devices {id: name}
        5) set positions
        :return:
        """
        # Set bindy (network) keyfile. Must be called before any call to "enumerate_devices" or "open_device"
        lib.set_bindy_key(str(Path(ximc_dir / arch_type / "keyfile.sqlite")).encode("utf-8"))
        # Enumerate devices
        # This is device search and enumeration with probing. It gives more information about soft.
        probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
        # TODO: change to database readings
        enum_hints = b"addr=192.168.0.1, 129.175.100.137"
        # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
        self._devenum = lib.enumerate_devices(probe_flags, enum_hints)
        device_counts = self._get_number_axes()
        if device_counts != self._axes_number and device_counts != 0:
            res, comments = True, f'Number of available axes {device_counts} does not correspond to ' \
                                   f'database value {self._axes_number}. Check cabling or power.'
            for key in range(device_counts + 1, self._axes_number + 1):
                del self.axes[key]
            self.device_status.connected = True
        elif device_counts == 0:
            res, comments = False, f'None of devices were found, check connection.'
        else:
            res, comments = True, ''
        if res:
            for i in range(device_counts):
                uri = lib.get_device_name(self._devenum, i)
                device_id = lib.open_device(uri)
                name = controller_name_t()
                result = lib.get_controller_name(device_id, ctypes.byref(name))
                if result == Result.Ok:
                    name = name.ControllerName
                else:
                    error_logger(self, self._form_devices_list, result)
                    name = f'Axis{device_id}'
                self.axes[device_id].name = name
                self.axes[device_id].pos = self._get_position_controller(device_id)[1]

        return res, comments

    def GUI_bounds(self) -> Dict[str, Any]:
        pass

    def _get_axes_names(self) -> List[str]:
        return [val.name for val in self.axes.values()]

    def _get_axes_status(self) -> List[int]:
        return self._axes_status

    def _get_number_axes(self) -> int:
        return lib.get_device_count(self._devenum)

    def _move_axis_to(self, axis_id: int, pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis_id, 2)
        if res:
            full_turn = pos // 256
            steps = pos % 256
            result = lib.command_move(axis_id, full_turn, steps)
            if result == Result.Ok:
                result = lib.command_wait_for_stop(axis_id, 5)
                if result == Result.Ok:
                    res, comments = True, ''
                else:
                    res, comments = False, f'Confirmation of movement finish for device_id {axis_id} was not recieved ' \
                                           f'{result}.'
            else:
                res, comments = False, f'Move command for device_id {axis_id} did not work {result}.'

            StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)

        return res, comments

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._axes_limits

    def _get_positions(self) -> List[Union[int, float]]:
        positions = []
        for device_id in self.axes.keys():
            res, val = self._get_position_controller(device_id)
            if res:
                positions.append(val)
            else:
                positions.append(self.axes[device_id].position)
        return positions

    def _get_position_controller(self, device_id: int) -> Tuple[bool, int]:
        """
        Return position in microsteps for device_id. One full turn equals to 256 microsteps
        :param device_id: corresponds to device_id of Standa controller
        :return: microsteps
        """
        pos = get_position_t()
        result = lib.get_position(device_id, ctypes.byref(pos))
        if result == Result.Ok:
            return True, pos.Position * 256 + pos.uPosition
        else:
            error_logger(self, self._get_position_controller, str(result))
            return False, 0

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._axes_preset_values

    def _set_controller_positions(self, positions: List[Union[int, float]]) -> Tuple[bool, str]:
        return super()._set_controller_positions(positions)

    def _stop_axis(self, device_id):
        result = lib.command_stop(device_id)
