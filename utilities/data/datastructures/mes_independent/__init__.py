# all file should be imported or MsgGenerarot will not be able to work
from .devices_dataclass import *
from .measurments_dataclass import *
from .stpmtr_dataclass import *

from dataclasses import dataclass


@dataclass(frozen=True)
class CmdStruct:
    name: str
    func_input: FuncInput
    func_output: FuncOutput