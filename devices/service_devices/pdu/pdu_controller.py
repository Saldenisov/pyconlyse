import logging
from abc import abstractmethod
from os import path
from pathlib import Path
from typing import Any, Callable
from functools import lru_cache
from devices.devices import Service
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.pdu_dataclass import *
from utilities.errors.myexceptions import DeviceError
from utilities.myfunc import error_logger, info_msg

module_logger = logging.getLogger(__name__)


class PDUController(Service):
    ACTIVATE_PDU = CmdStruct(FuncActivatePDUInput, FuncActivatePDUOutput)
    SET_PDU_STATE =CmdStruct(FuncSetPDUState, FuncSetPDUStateOutput)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._camera_class = kwargs['PDU_class']
        self._cameras: Dict[int, PDU] = dict()

        res, comments = self._set_parameters()  # Set parameters from database first and after connection is done update
        # from hardware controller if possible
        if not res:
            raise PDUError(self, comments)


class PDUError(BaseException):
    def __init__(self, controller: PDUController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')