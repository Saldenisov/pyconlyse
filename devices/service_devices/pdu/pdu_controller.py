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
        super().__init__(**kwargs)
        self._pdu_class = kwargs['PDU_class']
        self._pdus: Dict[int, PDU] = dict()

        res, comments = self._set_parameters()  # Set parameters from database first and after connection is done update
        # from hardware controller if possible
        if not res:
            raise PDUError(self, comments)

    def activate(self, func_input: FuncActivateInput) -> FuncActivateOutput:
        flag = func_input.flag
        res, comments = self._check_if_active()
        if res ^ flag:  # res XOR Flag
            if flag:
                res, comments = self._connect(flag)  # guarantees that parameters could be read from controller
                if res:  # parameters should be set from hardware controller if possible
                    res, comments = self._set_parameters()  # This must be realized for all controllers
                    if res:
                        self.device_status.active = True
            else:
                res, comments = self._connect(flag)
                if res:
                    self.device_status.active = flag
        info = f'{self.id}:{self.name} active state is {self.device_status.active}. {comments}'
        info_msg(self, 'INFO', info)
        return FuncActivateOutput(comments=info, device_status=self.device_status, func_success=res)

    def available_public_functions(self) -> Tuple[CmdStruct]:
        return [*super().available_public_functions(), PDUController.ACTIVATE_PDU, PDUController.GET_PDU_STATE,
                PDUController.SET_PDU_STATE]

    def get_controller_state(self, func_input: FuncGetPDUControllerStateInput) -> FuncGetPDUControllerStateOutput:
        """
        State of controller is returned
        :return:  FuncOutput
        """
        comments = f'Controller is {self.device_status.active}. Power is {self.device_status.power}. ' \
                   f'Cameras are {self._cameras_status}'
        return FuncGetPDUControllerStateOutput(pdus=self.pdus, device_status=self.device_status,
                                               comments=comments, func_success=True)

    def _get_pdus_ids_db(self):
        try:
            ids: List[int] = []
            ids_s: List[str] = self.get_parameters['PDUs_ids'].replace(" ", "").split(';')
            for exp in ids_s:
                val = eval(exp)
                if not isinstance(val, int):
                    raise TypeError()
                ids.append(val)
            if len(ids) != self._pdus_number:
                raise PDUError(self, f'Number of PDUs_ids {len(ids)} is not equal to PDUs_number {self._pdus_number}.')
            return ids
        except KeyError:
            try:
                pdus_number = int(self.get_parameters['PDUs_number'])
                return list([pdu_id for pdu_id in range(1, pdus_number + 1)])
            except (KeyError, ValueError):
                raise PDUError(self, text="PDUs ids could not be set, PDUs_ids or PDUs_number fields is absent "
                                          "in the database.")
        except (TypeError, SyntaxError):
            raise PDUError(self, text="Check PDUs_ids field in database, must be integer.")

    @abstractmethod
    def _get_pdus_status(self) -> List[int]:
        pass

    def _get_pdus_status_db(self) -> List[int]:
        return [0] * self._pdus_number

    @abstractmethod
    def _get_number_pdus(self):
        pass

    def _get_number_pdus_db(self):
        try:
            return int(self.get_parameters['PDUs_number'])
        except KeyError:
            raise PDUError(self, text="PDUs_number could not be set, pdus_number field is absent in the database")
        except (ValueError, SyntaxError):
            raise PDUError(self, text="Check PDUs number in database, must be PDUs_number = number")

    def description(self) -> Description:
        """
        Description with important parameters
        :return: PDUDescription with parameters essential for understanding what this device is used for
        """
        try:
            parameters = self.get_settings('Parameters')
            return PDUDescription(pdus=self.pdus, info=parameters['info'], GUI_title=parameters['title'])
        except (KeyError, DeviceError) as e:
            return PDUError(self, f'Could not set description of controller from the database: {e}')

    @property
    def pdus(self):
        return self._pdus

    @property
    def pdus_essentials(self):
        essentials = {}
        for pdu_id, pdu in self._pdus.items():
            essentials[pdu_id] = pdu.short()
        return essentials

    def _set_ids_pdus(self):
        if not self.device_status.connected:
            ids = self._get_pdus_ids_db()
            i = 1
            for id_a in ids:
                self._pdus[i] = self._pdu_class(device_id=id_a)
                i += 1

    def _set_number_pdus(self):
        if self.device_status.connected:
            self._pdus_number = self._get_number_pdus()
        else:
            self._pdus_number = self._get_number_pdus_db()

    def _set_parameters(self, extra_func: List[Callable] = None) -> Tuple[bool, str]:
        try:
            self._set_number_pdus()
            self._set_ids_pdus()  # Ids must be set first
            self._set_names_pdus()
            #self._set_private_parameters_db()
            self._set_status_pdus()
            res = []
            if extra_func:
                comments = ''
                for func in extra_func:
                    r, com = func()
                    res.append(r)
                    comments = comments + com

            if self.device_status.connected:
                self._parameters_set_hardware = True
            if all(res):
                return True, ''
            else:
                raise PDUError(self, comments)
        except PDUError as e:
            error_logger(self, self._set_parameters, e)
            return False, str(e)

    def _set_status_pdus(self):
        if self.device_status.connected:
            statuses = self._get_pdus_status()
        else:
            statuses = self._get_pdus_status_db()

        for id, status in zip(self._pdus.keys(), statuses):
            self._pdus[id].status = status


class PDUError(BaseException):
    def __init__(self, controller: PDUController, text: str):
        super().__init__(f'{controller.name}:{controller.id}:{text}')