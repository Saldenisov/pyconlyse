"""
01/09/2020 DENISOV Sergey

"""
import logging
from abc import abstractmethod
from typing import List, Tuple
from devices.devices import Service
from devices.devices_dataclass import HardwareDevice, HardwareDeviceEssentials, HardwareDeviceDict
from devices.service_devices.pdu.pdu_dataclass import *
from utilities.datastructures.mes_independent.general import CmdStruct
from utilities.myfunc import join_smart_comments

module_logger = logging.getLogger(__name__)


class PDUController(Service):
    GET_PDU_STATE = CmdStruct(FuncGetPDUStateInput, FuncGetPDUStateOutput)
    SET_PDU_STATE = CmdStruct(FuncSetPDUStateInput, FuncSetPDUStateOutput)

    def __init__(self, **kwargs):
        kwargs['hardware_device_dataclass'] = kwargs['pdu_dataclass']
        super().__init__(**kwargs)
        self._hardware_devices: Dict[int, PDU] = HardwareDeviceDict()

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return (*super().available_public_functions(), PDUController.GET_PDU_STATE, PDUController.SET_PDU_STATE)

    def get_pdu_state(self, func_input: FuncGetPDUStateInput) -> FuncGetPDUStateOutput:
        res, comments = self._check_device_range(func_input.pdu_id)
        if res:
            pdu = self.pdus[func_input.pdu_id]
            res, comments = self._get_pdu_outputs(pdu.device_id)
        else:
            pdu = None
        return FuncGetPDUStateOutput(func_success=res, comments=comments, pdu=pdu)

    @property
    @abstractmethod
    def pdus(self):
        return self._hardware_devices

    @property
    def pdus_essentials(self):
        return {device.device_id_seq: device.short() for device in self.hardware_devices.values()}

    @property
    def _pdus_status(self) -> List[int]:
        return [pdu.status for pdu in self._hardware_devices.values()]

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

    @property
    def hardware_devices_essentials(self) -> Dict[int, HardwareDeviceEssentials]:
        return super(PDUController, self).hardware_devices_essentials()

    def set_pdu_state(self, func_input: FuncSetPDUStateInput) -> FuncSetPDUStateOutput:
        res, comments = self._check_device(func_input.pdu_id)
        if res:
            pdu = self.pdus[func_input.pdu_id]
            res, comments = self._set_pdu_state(func_input)
        else:
            pdu = None
        comments = f'Func "set_pdu_state" is accomplished with success: {res}. {comments}'
        return FuncSetPDUStateOutput(func_success=res, comments=comments, pdu=pdu)

    @abstractmethod
    def _set_pdu_state(self, func_input: FuncSetPDUStateInput) -> Tuple[bool, str]:
        return False, ''

    def _set_parameters_after_connect(self) -> Tuple[bool, str]:
        return self._set_all_pdu_outputs()

    def _set_all_pdu_outputs(self) -> Tuple[bool, str]:
        results, comments = [], ''
        for pdu in self.pdus.values():
            res, com = self._get_pdu_outputs(pdu.device_id)
            results.append(res)
            comments = join_smart_comments(comments, com)
        return all(results), comments

    @abstractmethod
    def _get_pdu_outputs(self, pdu_id: Union[int, str]) -> Tuple[bool, str]:
        return False, ''


class PDUError(BaseException):
    def __init__(self, controller: PDUController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')