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
    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['pdu_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, DAQmxController] = HardwareDeviceDict()


class DAQmxError(BaseException):
    def __init__(self, controller: DAQmxController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')