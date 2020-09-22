from dataclasses import dataclass, field
from typing import Union, Dict, Tuple
from devices.devices_dataclass import HardwareDevice, FuncGetControllerStateInput, FuncGetControllerStateOutput
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput


@dataclass
class PDUOutput:
    id: Union[int, str]
    name: str
    state: int


@dataclass
class PDU(HardwareDevice):
    outputs: Dict[Union[int, str], PDUOutput] = field(default_factory=dict)
    authentication: Tuple[str] = field(default_factory=tuple)

    def short(self):
        d = {}
        for key in PDUEssentials.__dataclass_fields__.keys():
            d[key] = getattr(self, key)
        return PDUEssentials(**d)


@dataclass
class PDUNetioOutput(PDUOutput):
    action: int
    delay: int


@dataclass
class PDUNetio(PDU):
    ip_address: str = ''
    mac_address: str = ''


@dataclass
class PDUEssentials:
    device_id: int
    name: str
    friendly_name: str
    status: int = 0


@dataclass
class PDUNetioEssentials(PDUEssentials):
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
class FuncGetPDUStateInput(FuncInput):
    pdu_id: int
    com: str = 'get_pdu_state'


@dataclass
class FuncGetPDUStateOutput(FuncOutput):
    pdu: PDU
    com: str = 'get_pdu_state'


@dataclass
class FuncSetPDUStateInput(FuncInput):
    pdu_id: int
    pdu_output_id: Union[int, str]
    output: Union[PDUOutput, int]
    com: str = 'set_pdu_state'


@dataclass
class FuncSetPDUStateOutput(FuncOutput):
    pdu: PDU
    com: str = 'set_pdu_state'
