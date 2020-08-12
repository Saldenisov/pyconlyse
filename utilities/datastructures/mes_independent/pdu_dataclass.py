from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Tuple, Union, NewType, Set
from pypylon import pylon
from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription


@dataclass
class PDU:
    device_id: int

    name: str

    state: Dict[str, str]
    status: int = 0

    def short(self):
        d = {}
        for key in PDUEssentials.__dataclass_fields__.keys():
            d[key] = getattr(self, key)
        return PDUEssentials(**d)


@dataclass
class PDUNetio(PDU):
    ip: str = ''
    mac: str = ''


@dataclass(order=True)
class PDUDescription(Desription):
    pdus: Dict[int, PDU]


@dataclass
class PDUEssentials:
    device_id: int
    name: str
    state: Dict[str, str]
    status: int = 0


@dataclass
class PDUEssentialsNetio(PDUEssentials):
    ip: str = ''
    mac: str = ''


@dataclass
class FuncActivatePDUInput(FuncInput):
    pdu_id: int
    flag: int
    com: str = 'activate_pdu'


@dataclass
class FuncActivatePDUOutput(FuncOutput):
    pdus: Dict[int, PDUEssentials]
    com: str = 'activate_pdu'


@dataclass
class FuncGetPDUControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetPDUControllerStateOutput(FuncGetControllerStateOutput):
   pdus: Dict[int, PDU] = None


@dataclass
class FuncGetPDUState(FuncInput):
    pdu_id: Union[int, List[int]]
    com: str = 'get_pdu_state'


@dataclass
class FuncGetPDUStateOutput(FuncOutput):
    pdus: Dict[int, PDUEssentials]
    com: str = 'get_pdu_state'


@dataclass
class FuncSetPDUState(FuncInput):
    pdu_id: Union[int, List[int]]
    state: Union[Dict[str, str], List[Dict[str, str]]]
    com: str = 'set_pdu_state'


@dataclass
class FuncSetPDUStateOutput(FuncOutput):
    pdus: Dict[int, PDUEssentials]
    com: str = 'set_pdu_state'
