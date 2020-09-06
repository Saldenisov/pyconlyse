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
    GET_PDU_STATE = CmdStruct(FuncSetPDUState, FuncSetPDUStateOutput)
    SET_PDU_STATE = CmdStruct(FuncSetPDUState, FuncSetPDUStateOutput)

    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['pdu_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, PDU] = HardwareDeviceDict()

    def activate_pdu(self, func_input: FuncActivatePDUInput) -> FuncActivatePDUOutput:

        return FuncActivatePDUOutput()

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return [*super().available_public_functions(), PDUController.ACTIVATE_PDU, PDUController.GET_PDU_STATE,
                PDUController.SET_PDU_STATE]

    @property
    @abstractmethod
    def pdus(self):
        self._hardware_devices

    @property
    def pdus_essentials(self):
        return {camera_id: camera.short() for camera_id, camera in self._hardware_devices.items()}

    @property
    def _pdus_status(self) -> List[int]:
        return [pdu.status for pdu in self._hardware_devices.values()]

    @abstractmethod
    def _change_pdu_status(self, pdu_id: Union[int, str], flag: int, force=False) -> Tuple[bool, str]:
        pass

    @staticmethod
    def _check_status_flag(flag: int):
        flags = [0, 1, 2]  # 0 - non-available, 1 - available, 2 - locked
        if flag not in flags:
            return False, f'Wrong flag {flag} was passed. FLAGS={flags}.'
        else:
            return True, ''

    @property
    def hardware_devices(self):
        return self.pdus


class PDUError(BaseException):
    def __init__(self, controller: PDUController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')