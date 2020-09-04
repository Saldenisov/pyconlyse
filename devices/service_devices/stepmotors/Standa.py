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
from utilities.datastructures.mes_independent.stpmtr_dataclass import StandaAxisStpMtr
from utilities.datastructures.mes_independent.devices_dataclass import HardwareDeviceDict
from .stpmtr_controller import StpMtrController, StpMtrError, MoveType

module_logger = logging.getLogger(__name__)


dev_mode = False


class StpMtrCtrl_Standa(StpMtrController):

    def __init__(self, **kwargs):
        kwargs['stpmtr_dataclass'] = StandaAxisStpMtr
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, StandaAxisStpMtr] = HardwareDeviceDict()
        self._devenum = None  # LP_device_enumeration_t
        self._enumerated = False
        self.lib = lib
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('move_parameters', 'move_parameters', dict),
                                                                      ('limits', 'limits', tuple),
                                                                      ('preset_values', 'preset_values', tuple)],
                                                          extra_func=[self._get_positions_file,
                                                                      self._set_move_parameters_axes])

        if not res:
            raise StpMtrError(self, comments)

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

    def _change_axis_status(self, device_id: Union[int, str], flag: int, force=False) -> Tuple[bool, str]:
        res, comments = super()._check_status_flag(flag)
        if res:
            axis = self.axes_stpmtr[device_id]
            if axis.status != flag:
                info = ''
                if axis.status == 2 and force:
                    self._stop_axis(axis.device_id)
                    info = f' Axis id={device_id}, name={axis.name} was stopped.'
                    self.axes_stpmtr[device_id].status = flag
                    res, comments = True, f'Axis id={device_id}, name={axis.name} is set to {flag}.' + info
                elif axis.status == 2 and not force:
                    res, comments = False, f'Axis id={device_id}, name={axis.name} is moving. ' \
                                           'Force Stop in order to change.'
                else:
                    self.axes_stpmtr[device_id].status = flag
                    res, comments = True, f'Axis id={device_id}, name={axis.name} is set to {flag}.' + info
            else:
                res, comments = True, f'Axis id={device_id}, name={axis.name} is already set to {flag}'
        return res, comments

    def _check_if_active(self) -> Tuple[bool, str]:
        return super()._check_if_active()  # TODO: should be replaced with something reasonable

    def _check_if_connected(self) -> Tuple[bool, str]:
        status = status_t()
        if self.axes_stpmtr:
            result = self.lib.get_status(list(self.axes_stpmtr.keys())[0], ctypes.byref(status))
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
        enum_hints = f"addr={self.get_parameters['network_hints']}".encode('utf-8')
        # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
        self._devenum = self.lib.enumerate_devices(probe_flags, enum_hints)
        sleep(0.05)
        info_msg(self, 'INFO', f'Axes are enumerated.')
        self._enumerated = True
        device_counts = self._get_number_hardware_devices()
        info_msg(self, 'INFO', f'Number of axes is {device_counts}.')

        if device_counts != 0:
            comments = ''
            if device_counts != self._hardware_devices_number:
                res, comments = True, f'Number of available axes {device_counts} does not correspond to ' \
                                      f'database value {self._hardware_devices_number}. Check cabling or power.'

            def search_id(self: StpMtrCtrl_Standa, uri: str) -> str:
                uri = uri.decode('utf-8')
                for axis_id, axis in self.axes_stpmtr.items():
                    if axis.device_id in uri:
                        return axis.device_id
                return None

            Oks = []
            for key in range(device_counts):
                uri = self.lib.get_device_name(self._devenum, key)
                device_id = search_id(self, uri)
                if not device_id:
                    return False, f'Unknown uri {uri}. Check DB, modify or add.'
                else:
                    device_id_seq = self.lib.open_device(uri)
                    self.axes_stpmtr[device_id].device_id_seq = device_id_seq
                    info_msg(self, 'INFO', f'Settings names and positions.')
                    self.axes_stpmtr[device_id].name = uri.decode('utf-8')
                    # Sometimes there is a neccesity to call stop function
                    # So we do it always for every axes
                    self._stop_axis(device_id)
                    friendly_name = controller_name_t()
                    result = self.lib.get_controller_name(device_id_seq, ctypes.byref(friendly_name))
                    if result == Result.Ok:
                        friendly_name = friendly_name.ControllerName
                        Oks.append(True)
                    else:
                        error_logger(self, self._form_devices_list, result)
                        comments = f'{comments}. friendly_name for {device_id} was not set.'
                        friendly_name = f'Axis{device_id_seq}'.encode('utf-8')
                    self.axes_stpmtr[device_id].friendly_name = friendly_name.decode('utf-8')
                    _,_ = self._get_position_axis(device_id)

            cleaned_axes = HardwareDeviceDict()
            i = 1
            for axis in self.axes_stpmtr.values():
                if not axis.device_id_seq:
                    del self.axes_stpmtr[axis.device_id]
                else:
                    cleaned_axes[i] = axis
                    i += 1
            self._hardware_devices = cleaned_axes

            if all(Oks):
                res, comments = True, comments
            else:
                res, comments = f'Did not initialize Standa controller properly. {comments}'

        elif device_counts == 0:
            res, comments = False, f'None of devices were found, check connection.'
        else:
            res, comments = True, ''

        return res, comments

    def _get_number_hardware_devices(self):
        return self.lib.get_device_count(self._devenum)

    def _move_axis_to(self, device_id: Union[int, str], go_pos: Union[float, int]) -> Tuple[bool, str]:
        res, comments = self._change_axis_status(device_id, 2)
        interrupted = False
        if res:
            axis = self.axes_stpmtr[device_id]
            microsteps_set = axis.move_parameters['microsteps']
            microsteps = int(go_pos % 1 * microsteps_set)
            steps = int(go_pos // 1)
            device_id_seq = axis.device_id_seq
            result = self.lib.command_move(device_id_seq, steps, microsteps)

            if result == Result.Ok:
                try:
                    await_time = axis.move_parameters['wait_to_complete']
                except (KeyError, ValueError):
                    await_time = 5
                result = self.lib.command_wait_for_stop(device_id_seq, await_time)

            if result != Result.Ok:
                # TODO: fix that
                res, comments = False, f'Move command for device_id {device_id} did not work {result}.'

            if self.axes_stpmtr[device_id].status != 2:
                interrupted = True

            if not interrupted:
                res, comments = True, f'Movement of Axis with id={device_id}, name={axis.friendly_name} ' \
                                      f'was finished.'
            else:
                res, comments = False, f'Movement of Axis with id={device_id} was interrupted'

            _, _ = self._get_position_axis(device_id)

        self._change_axis_status(device_id, 1, True)
        return res, comments

    def _get_position_axis(self, device_id: str) -> Tuple[bool, int]:
        """
        Return position in microsteps for device_id. One full turn equals to 256 microsteps
        :param device_id: corresponds to device_id of Standa controller
        :return: Basic_units
        """
        pos = get_position_t()
        axis: StandaAxisStpMtr = self.axes_stpmtr[device_id]
        device_id_seq = axis.device_id_seq
        result = self.lib.get_position(device_id_seq, ctypes.byref(pos))
        if result == Result.Ok:
            pos_microsteps = pos.Position * axis.move_parameters['microsteps'] + pos.uPosition
            pos_basic_units = axis.convert_to_basic_unit(MoveType.microstep, pos_microsteps)
            axis.position = pos_basic_units
            self._write_positions_to_file(positions=self._form_axes_positions())
            return True, ''
        else:
            return self._standa_error(result, func=self._get_position_axis)

    def _release_hardware(self) -> Tuple[bool, str]:
        try:
            for axis in self.axes_stpmtr.values():
                info_msg(self, 'INFO', f'Settings names and positions.')
                # Sometimes there is a neccesity to call stop function
                # So we do it always for every axes
                if axis.device_id_seq:
                    self._stop_axis(axis.device_id_seq)
                    arg = ctypes.byref(ctypes.cast(axis.device_id_seq, ctypes.POINTER(ctypes.c_int)))
                    result = self.lib.close_device(arg)
            return True, ''
        except Exception as e:
            error_logger(self, self._release_hardware, e)
            return False, f'{e}'
        finally:
            sleep(1)

    def _stop_axis(self, device_id: str) -> Tuple[bool, str]:
        result = self.lib.command_stop(self.axes_stpmtr[device_id].device_id_seq)
        return self._standa_error(result)

    def _set_pos_axis(self, device_id: Union[int, str], pos: Union[int, float]) -> Tuple[bool, str]:
        axis = self.axes_stpmtr[device_id]
        microsteps = axis.move_parameters['microsteps']
        pos_steps = int(pos // 1)
        pos_microsteps = int(pos % 1 * microsteps)
        pos_standa = set_position_t()
        try:
            pos_standa.Position = ctypes.c_int(pos_steps)
            pos_standa.uPosition = ctypes.c_int(pos_microsteps)
            pos_standa.EncPosition = ctypes.c_longlong(0)
            pos_standa.PosFlags = ctypes.c_uint(PositionFlags.SETPOS_IGNORE_ENCODER)
            device_id_seq = ctypes.c_int(self.axes_stpmtr[device_id].device_id_seq)
        except Exception as e:
            error_logger(self, self._set_pos, e)
        result = self.lib.set_position(device_id_seq, ctypes.byref(pos_standa))
        _, _ = self._get_position_axis(device_id)
        return self._standa_error(result)

    def _set_move_parameters_axes(self, must_have_param: Set[str] = None):
        must_have_param = {'00003D73': set(['microsteps', 'basic_unit']),
                           '00003D6A': set(['microsteps', 'basic_unit']),
                           '00003D98': set(['microsteps', 'basic_unit']),
                           '00003D8F': set(['microsteps', 'basic_unit']),
                           '00003B1B': set(['microsteps', 'basic_unit']),
                           '00003B37': set(['microsteps', 'basic_unit'])
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