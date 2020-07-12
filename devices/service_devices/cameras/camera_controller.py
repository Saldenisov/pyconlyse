import logging
from abc import abstractmethod
from os import path
from pathlib import Path
from typing import Any, Callable

from devices.devices import Service
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.camera_dataclass import *
from utilities.errors.myexceptions import DeviceError
from utilities.myfunc import error_logger, info_msg

module_logger = logging.getLogger(__name__)


class CameraCtrl(Service):
    ACTIVATE_CAMERA = CmdStruct(FuncActivateCameraInput, FuncActivateCameraOutput)
    GET_IMAGES = CmdStruct(None, None)
    SET_IMAGE_PARAMETERS = CmdStruct(None, None)
    SET_SYNC_PARAMETERS = CmdStruct(None, None)
    SET_TRANSPORT_PARAMETERS = CmdStruct(None, None)
    SET_ALL_PARAMETERS = CmdStruct(None, None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)