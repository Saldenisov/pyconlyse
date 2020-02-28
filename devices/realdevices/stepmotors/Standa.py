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
from pathlib import Path
from platform import system, architecture
from .stpmtr_controller import StpMtrController, StpmtrError
from devices.realdevices.stepmotors.ximc.pyximc import (lib, EnumerateFlags, )

module_logger = logging.getLogger(__name__)


dev_mode = False


class StpMtrCtrl_Standa(StpMtrController):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        file_folder = Path(__file__).resolve().parents[0]
        self._ximc_dir = Path(file_folder / 'ximc')
        self._devenum = None  # LP_device_enumeration_t
        self._devices: Dict[int, str] = {}
        if system() == "Windows":
            self._arch_dir = "win64" if "64" in architecture()[0] else "win32"
            libdir = self._ximc_dir / self._arch_dir
            os.environ["Path"] = str(libdir) + ";" + os.environ["Path"]  # add dll
        else:
            raise StpmtrError(self, text=f'OS System is {system()}. Can handle only windows')

    def _connect(self, flag: bool) -> Tuple[bool, str]:



        res, comments = self._form_devices_list()
        # Check enumerated devices in accordance with DB data
        if not res:
            pass
        # Open available devices, but keep software status set to 0
        if res:

        return res, comments

    def _change_axis_status(self, axis_id: int, flag: int, force=False) -> Tuple[bool, str]:
        pass

    def _form_devices_list(self) -> Tuple[bool, str]:
        """
        1) enumerates devices 2) count devices 3) checks vs DB 4) form dict of devices {id: name}
        5) set positions
        :return:
        """
        # Set bindy (network) keyfile. Must be called before any call to "enumerate_devices" or "open_device"
        lib.set_bindy_key(str(Path(self._ximc_dir / self._arch_dir / "keyfile.sqlite")).encode("utf-8"))
        # Enumerate devices
        # This is device search and enumeration with probing. It gives more information about soft.
        probe_flags = EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
        # TODO: change to DB readings
        enum_hints = b"addr=192.168.0.1, 129.175.100.137"
        # enum_hints = b"addr=" # Use this hint string for broadcast enumerate
        self._devenum = lib.enumerate_devices(probe_flags, enum_hints)
        device_counts = lib.get_device_count(self._devenum)
        if device_counts != self._axes_number:
            res, comments = False, f'Number of available axes {device_counts} does not correspond to ' \
                                   f'DB value {self._axes_number}. Check cabling or power.'
        else:
            res, comments = True, ''
        if res:
<<<<<<< HEAD

=======
            for i in range(device_counts):
                name = lib.get_device_name(self._devenum, i)
                device_id = lib.open_device(name)
                self._devices[device_id] = name
                self._pos[device_id - 1]0
                pos[device_id] = test_get_position(lib, device_ids[name])
>>>>>>> 4fd33b997ab328c14f6a258b4b0570a97f093b11
        return res, comments

    def GUI_bounds(self) -> Dict[str, Any]:
        pass

    def _get_axes_status(self) -> List[int]:
        pass

    def _get_number_axes(self) -> int:
        pass

    def _move_axis_to(self, axis: int, pos: Union[float, int], how='absolute') -> Tuple[bool, str]:
        pass

    def _get_limits(self) -> List[Tuple[Union[float, int]]]:
        pass

    def _get_pos(self) -> List[Union[int, float]]:
        pass

    def _get_preset_values(self) -> List[Tuple[Union[int, float]]]:
        pass