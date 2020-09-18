"""
14/09/2020 DENISOV Sergey
"""

import logging
from abc import abstractmethod
from os import path
from pathlib import Path
from typing import Any, Callable
from functools import lru_cache
from devices.devices import Service
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.daqmx_dataclass import *
from utilities.errors.myexceptions import DeviceError
from utilities.myfunc import error_logger, info_msg, join_smart_comments

module_logger = logging.getLogger(__name__)


class DAQmxController(Service):
    READ_CHANNEL = CmdStruct(None, None)
    WRITE_CHANNEL = CmdStruct(None, None)
    SET_CHANNEL_TYPE = CmdStruct(None, None)

    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['pdu_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, DAQmxCard] = HardwareDeviceDict()

        res, comments = self._set_parameters_main_devices(parameters=[('name', 'names', str),
                                                                      ('сhannel_settings', 'сhannel_settings', dict)],
                                                          extra_func=[])
        # Set parameters from database first and after connection is done; update from hardware controller if possible
        if not res:
            raise DAQmxError(self, comments)
        else:
            self.power(func_input=FuncPowerInput(flag=True))
            self.activate(func_input=FuncActivateInput(flag=True))
            for pdu in self.pdus.values():
                self.activate_device(func_input=FuncActivateDeviceInput(device_id=pdu.device_id_seq, flag=True))
            self._register_observation('PDU_outputs_state', self._set_all_pdu_outputs, 2)


    def available_public_functions(self) -> Tuple[CmdStruct]:
        return (*super().available_public_functions(), DAQmxController.READ_CHANNEL, DAQmxController.SET_CHANNEL_TYPE,
                DAQmxController.WRITE_CHANNEL)

    @staticmethod
    def _check_status_flag(flag: int):
        flags = [0, 1, 2]  # 0 - non-available, 1 - available, 2 - locked
        if flag not in flags:
            return False, f'Wrong flag {flag} was passed. FLAGS={flags}.'
        else:
            return True, ''

    @property
    def daqmxes(self):
        return self._hardware_devices

    @property
    def daqmxes_essentials(self):
        return {device.device_id_seq: device.short() for device in self.hardware_devices.values()}

    @property
    def hardware_devices(self) -> Dict[int, HardwareDevice]:
        return self.daqmxes

    @property
    def hardware_devices_essentials(self) -> Dict[int, HardwareDeviceEssentials]:
        return super(DAQmxController, self).hardware_devices_essentials()

    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        pass


class DAQmxError(BaseException):
    def __init__(self, controller: DAQmxController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')