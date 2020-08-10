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
    ip: str
    name: str
    state: Dict[str, str]
    status: int = 0


@dataclass
class PDUEssentials:
    ip: str
    name: str
    state: Dict[str, str]
    status: int = 0


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
class FuncSetPDUState(FuncInput):
    pdu_id: Union[int, List[int]]
    state: Union[Dict[str, str], List[Dict[str, str]]]
    com: str = 'set_pdu_state'


@dataclass
class FuncSetPDUStateOutput(FuncOutput):
    pdus: Dict[int, PDUEssentials]
    com: str = 'set_pdu_state'