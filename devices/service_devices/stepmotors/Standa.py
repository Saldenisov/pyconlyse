"""
This controller is dedicated to control Standa motorized mirrors
On ELYSE there are 4 motorized mirrors
"""


import ctypes
import logging
from pathlib import Path
from typing import List, Tuple, Union, Dict, Any

from devices.service_devices.stepmotors.ximc import (lib, arch_type, ximc_dir, EnumerateFlags, get_position_t, Result,
                                                     controller_name_t, status_t)
from utilities.myfunc import info_msg, error_logger
from .stpmtr_controller import StpMtrController

module_logger = logging.getLogger(__name__)


dev_mode = False


class StpMtrCtrl_Standa(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._devenum = None  # LP_device_enumeration_t
        self._devices: Dict[int, str] = {}
        self._enumerated = False
        #self._register_observation('_enumerated')

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        if self.device_status.power:
            if flag:
                res, comments = self._form_devices_list()
            else:
                res = []
                for device_id, axis in self.axes.items():
                    dev_id = ctypes.c_int32(device_id)
                    lib.close_device(ctypes.byref(dev_id))
                res, comments = True, ''
            if res:
                self.device_status.connected = flag
        else:
            res, comments = False, f'Power is off, connect to controller function cannot be called with flag {flag}'

        return res, comments

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_axis_flag(flag)
        if res:
            if self.axes[axis_id].status != flag:
                info = ''
                if self.axes[axis_id].status == 2 and force:
                    self._stop_axis(axis_id)
                    info = f' Axis id={axis_id}, name={self.axes[axis_id].name} was stopped.'
                    self.axes[axis_id].status = flag
                    res, comments = True, f'Axis id={axis_id}, name={self.axes[axis_id].name} is set to {flag}.' + info
                elif self.axes[axis_id].status == 2 and not force:
                    res, comments = False, 'Axis id={axis_id}, name={self.axes[axis_id].name} is moving. ' \
                                           'Force Stop in order to change.'
                else:
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
        enum_hints = b"addr=129.175.100.137, 192.168.0.1"
        # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
        if not self._enumerated:
            self._devenum = lib.enumerate_devices(probe_flags, enum_hints)
            info_msg(self, 'INFO', f'Axes are enumerated.')
            self._enumerated = True
        device_counts = self._get_number_axes()
        info_msg(self, 'INFO', f'Number of axes is {device_counts}.')
        if device_counts != self._axes_number and device_counts != 0:
            res, comments = True, f'Number of available axes {device_counts} does not correspond to ' \
                                   f'database value {self._axes_number}. Check cabling or power.'
            for key in range(device_counts + 1, self._axes_number + 1):
                del self.axes[key]
        elif device_counts == 0:
            res, comments = False, f'None of devices were found, check connection.'
        else:
            res, comments = True, ''
        if res:
            for i in range(device_counts):
                info_msg(self, 'INFO', f'Settings names and positions.')

                uri = lib.get_device_name(self._devenum, i)
                device_id = lib.open_device(uri)
                # Sometimes there is a neccesity to call stop function
                # So we do it always for every axes
                self._stop_axis(device_id)
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

    def _move_axis_to(self, axis_id: int, go_pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis_id, 2)
        interrupted = False
        if res:
            full_turn = int(go_pos // 256)
            steps = int(go_pos % 256)
            try:
                result = lib.command_move(ctypes.c_int32(axis_id), ctypes.c_int32(full_turn), ctypes.c_int32(steps))
            except Exception as e:
                print(e)
            if result == Result.Ok:
                result = lib.command_wait_for_stop(axis_id, 5)

            if result != Result.Ok:
                res, comments = False, f'Move command for device_id {axis_id} did not work {result}.'

            if self.axes[axis_id].status != 2:
                interrupted = True

            if not interrupted:
                res, comments = True, f'Movement of Axis with id={axis_id}, name={self.axes[axis_id].name} ' \
                                      f'was finished.'
            else:
                res, comments = False, f'Movement of Axis with id={axis_id} was interrupted'

            self.axes[axis_id].position = self._get_position_controller(axis_id)[1]
            StpMtrController._write_to_file(str(self._axes_positions), self._file_pos)

        self._change_axis_status(axis_id, 1, True)
        return res, comments

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        return self._axes_limits

    def _get_positions(self) -> Dict[int, Union[int, float]]:
        positions = {}
        for device_id in self.axes.keys():
            res, val = self._get_position_controller(device_id)
            if res:
                positions[device_id] = val
            else:
                positions[device_id] = self.axes[device_id].position
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

    def _release_hardware(self) -> Tuple[bool, str]:
        self.i_know_how = {'mm': 0, 'steps': 1}

    def _set_controller_positions(self, positions: List[Union[int, float]]) -> Tuple[bool, str]:
        return super()._set_controller_positions(positions)

    def _stop_axis(self, device_id):
        result = lib.command_stop(device_id)
