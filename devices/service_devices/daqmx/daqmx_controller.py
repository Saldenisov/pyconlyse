"""
14/09/2020 DENISOV Sergey
"""

import logging
from typing import Dict, Tuple
from devices.devices import Service
from devices.service_devices.daqmx.daqmx_dataclass import DAQmxCard
from devices.devices_dataclass import HardwareDeviceDict, HardwareDevice, HardwareDeviceEssentials
from utilities.datastructures.mes_independent.general import CmdStruct

module_logger = logging.getLogger(__name__)


class DAQmxController(Service):
    READ_CHANNEL = CmdStruct(None, None)
    WRITE_CHANNEL = CmdStruct(None, None)
    SET_CHANNEL_TYPE = CmdStruct(None, None)

    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['pdu_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, DAQmxCard] = HardwareDeviceDict()

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