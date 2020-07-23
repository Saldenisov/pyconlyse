"""
This controller is dedicated to control Standa motorized mirrors
On ELYSE there are 4 motorized mirrors
"""


import ctypes
import logging
from pathlib import Path
from typing import Callable, List, Tuple, Union, Dict, Any, Set
from time import sleep

from devices.service_devices.stepmotors.ximc import (lib, arch_type, ximc_dir, EnumerateFlags, get_position_t, Result,
                                                     controller_name_t, status_t, set_position_t, PositionFlags)
from utilities.myfunc import info_msg, error_logger
from .stpmtr_controller import StpMtrController, StpMtrError, MoveType

module_logger = logging.getLogger(__name__)


dev_mode = False


class StpMtrCtrl_Standa(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._devenum = None  # LP_device_enumeration_t
        self._devices: Dict[int, str] = {}
        self._enumerated = False
        self.lib = lib
        #self._register_observation('_enumerated')

    def _connect(self, flag: bool) -> Tuple[bool, str]:
        if self.device_status.power:
            if flag:
                res, comments = self._form_devices_list()
            else:
                res, comments = self._release_hardware()
            self.device_status.connected = flag
        else:
            res, comments = False, f'Power is off, connect to controller function cannot be called with flag {flag}'

        return res, comments

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_axis_flag(flag)
        if res:
            axis = self.axes[axis_id]
            if axis.status != flag:
                info = ''
                if axis.status == 2 and force:
                    self._stop_axis(axis.device_id)
                    info = f' Axis id={axis_id}, name={axis.name} was stopped.'
                    self.axes[axis_id].status = flag
                    res, comments = True, f'Axis id={axis_id}, name={axis.name} is set to {flag}.' + info
                elif axis.status == 2 and not force:
                    res, comments = False, f'Axis id={axis_id}, name={axis.name} is moving. ' \
                                           'Force Stop in order to change.'
                else:
                    self.axes[axis_id].status = flag
                    res, comments = True, f'Axis id={axis_id}, name={axis.name} is set to {flag}.' + info
            else:
                res, comments = True, f'Axis id={axis_id}, name={axis.name} is already set to {flag}'
        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()  # TODO: should be replaced with something reasonable

    def _check_if_connected(self) -> Tuple[bool, str]:
        status = status_t()
        if self.axes:
            result = self.lib.get_status(list(self.axes.keys())[0], ctypes.byref(status))
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
        self.lib.set_bindy_key(str(Path(ximc_dir / arch_type / "keyfile.sqlite")).encode("utf-8"))
        # Enumerate devices
        # This is device search and enumeration with probing. It gives more information about soft.
        probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
        # TODO: change to database readings
        enum_hints = f"addr={self.get_parameters['network_hints']}".encode('utf-8')
        # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
        self._devenum = self.lib.enumerate_devices(probe_flags, enum_hints)
        sleep(0.05)
        info_msg(self, 'INFO', f'Axes are enumerated.')
        self._enumerated = True
        device_counts = self._get_number_axes()
        info_msg(self, 'INFO', f'Number of axes is {device_counts}.')
        if device_counts != 0:
            comments = ''
            if device_counts != self._axes_number:
                res, comments = True, f'Number of available axes {device_counts} does not correspond to ' \
                                      f'database value {self._axes_number}. Check cabling or power.'

            def search_id(self: StpMtrCtrl_Standa, uri: str):
                uri = uri.decode('utf-8')
                for axis_id, axis in self.axes.items():
                    if axis.name in uri:
                        return axis_id
                return None

            keep_ids = []
            Oks = []
            for key in range(device_counts):
                uri = self.lib.get_device_name(self._devenum, key)
                id_to_keep = search_id(self, uri)
                if not id_to_keep:
                    return False, f'Unknown uri {uri}. Check DB, modify or add.'
                else:
                    keep_ids.append(id_to_keep)
                    info_msg(self, 'INFO', f'Settings names and positions.')
                    self.axes[id_to_keep].name = uri.decode('utf-8')
                    device_id = self.lib.open_device(uri)
                    # Sometimes there is a neccesity to call stop function
                    # So we do it always for every axes
                    self._stop_axis(device_id)
                    friendly_name = controller_name_t()
                    result = self.lib.get_controller_name(device_id, ctypes.byref(friendly_name))
                    if result == Result.Ok:
                        friendly_name = friendly_name.ControllerName
                        Oks.append(True)
                    else:
                        error_logger(self, self._form_devices_list, result)
                        friendly_name = f'Axis{device_id}'
                    self.axes[id_to_keep].device_id = device_id
                    self.axes[id_to_keep].friendly_name = friendly_name.decode('utf-8')
                    self.axes[id_to_keep].pos = self._get_position_controller(device_id)[1]

            for id_axis in list(self.axes.keys()):
                if id_axis not in keep_ids:
                    del self.axes[id_axis]
            if all(Oks):
                res, comments = True, comments
            else:
                res, comments = f'Did not initialize Standa controller properly. {comments}'

        elif device_counts == 0:
            res, comments = False, f'None of devices were found, check connection.'
        else:
            res, comments = True, ''

        return res, comments

    def GUI_bounds(self) -> Dict[str, Any]:
        pass

    def _get_axes_names(self) -> List[str]:
        return [val.name for val in self.axes.values()]

    def _get_axes_status(self) -> List[int]:
        return self._axes_status

    def _get_number_axes(self) -> int:
        return self.lib.get_device_count(self._devenum)

    def _move_axis_to(self, axis_id: int, go_pos: Union[float, int]) -> Tuple[bool, str]:
        res, comments = self._change_axis_status(axis_id, 2)
        interrupted = False
        if res:
            axis = self.axes[axis_id]
            microsteps_set = self.axes[axis_id].move_parameters['microsteps']
            microsteps = int(go_pos % 1 * microsteps_set)
            steps = int(go_pos // 1)
            device_id = axis.device_id
            result = self.lib.command_move(device_id, steps, microsteps)

            if result == Result.Ok:
                try:
                    await_time = axis.move_parameters['wait_to_complete']
                except (KeyError, ValueError):
                    await_time = 5
                result = self.lib.command_wait_for_stop(device_id, await_time)

            if result != Result.Ok:
                # TODO: fix that
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
        for axis_id, axis in self.axes.items():
            res, val = self._get_position_controller(axis_id)
            if res:
                positions[axis_id] = val
            else:
                positions[axis_id] = self.axes[axis_id].position
        return positions

    def _get_position_controller(self, axis_id: int) -> Tuple[bool, int]:
        """
        Return position in microsteps for device_id. One full turn equals to 256 microsteps
        :param device_id: corresponds to device_id of Standa controller
        :return: Basic_units
        """
        pos = get_position_t()
        axis = self.axes[axis_id]
        device_id = axis.device_id
        result = self.lib.get_position(device_id, ctypes.byref(pos))
        if result == Result.Ok:
            pos_microsteps = pos.Position * axis.move_parameters['microsteps'] + pos.uPosition
            pos_basic_units = axis.convert_to_basic_unit(MoveType.microstep, pos_microsteps)
            return True, pos_basic_units
        else:
            return self._standa_error(result, func=self._get_position_controller)

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        return self._axes_preset_values

    def _release_hardware(self) -> Tuple[bool, str]:
        try:
            for axis in self.axes.values():
                info_msg(self, 'INFO', f'Settings names and positions.')
                device_id = axis.device_id
                # Sometimes there is a neccesity to call stop function
                # So we do it always for every axes
                self._stop_axis(device_id)
                arg = ctypes.byref(ctypes.cast(device_id, ctypes.POINTER(ctypes.c_int)))
                result = self.lib.close_device(arg)
                # TODO: something wrong happens when device is closed, nothing works afterwards
            return True, ''
        except Exception as e:
            error_logger(self, self._release_hardware, e)
            return False, f'{e}'
        finally:
            sleep(1)

    def _stop_axis(self, device_id) -> Tuple[bool, str]:
        result = self.lib.command_stop(device_id)
        return self._standa_error(result)

    def _set_pos(self, axis_id: int, pos: Union[int, float]) -> Tuple[bool, str]:
        axis = self.axes[axis_id]
        microsteps = axis.move_parameters['microsteps']
        pos_steps = int(pos // 1)
        pos_microsteps = int(pos % 1 * microsteps)
        pos_standa = set_position_t()
        try:
            pos_standa.Position = ctypes.c_int(pos_steps)
            pos_standa.uPosition = ctypes.c_int(pos_microsteps)
            pos_standa.EncPosition = ctypes.c_longlong(0)
            pos_standa.PosFlags = ctypes.c_uint(PositionFlags.SETPOS_IGNORE_ENCODER)
            device_id = ctypes.c_int(self.axes[axis_id].device_id)
        except Exception as e:
            error_logger(self, self._set_pos, e)
        result = self.lib.set_position(device_id, ctypes.byref(pos_standa))
        self.axes[axis_id].position = self._get_position_controller(axis_id=axis_id)[1]
        return self._standa_error(result)

    def _set_move_parameters_axes(self, must_have_param: Set[str] = None):
        must_have_param = {1: set(['microsteps', 'basic_unit']),
                           2: set(['microsteps', 'basic_unit']),
                           3: set(['microsteps', 'basic_unit']),
                           4: set(['microsteps', 'basic_unit']),
                           5: set(['microsteps', 'basic_unit']),
                           6: set(['microsteps', 'basic_unit']),
                           7: set(['microsteps', 'basic_unit']),
                           8: set(['microsteps', 'basic_unit']),
                           }
        return super()._set_move_parameters_axes(must_have_param)

    def _standa_error(self, error: int, func: Callable = None) -> Tuple[bool, str]:
        # TODO: finish filling different errors values
        if error == 0:
            res, comments = True, ''
        elif error == -1:
            res, comments = False, 'Standa: generic error.'
        else:
            res, comments = False, 'Standa: unknown error.'
        if func:
            error_logger(self, func, comments)

        return res, comments