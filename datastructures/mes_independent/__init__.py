# all file should be imported or MsgGenerarot will not be able to work
from dataclasses import dataclass


@dataclass
class FuncInput:
    pass

@dataclass
class FuncOutput:
    comments: str
    func_success: bool


@dataclass(frozen=True, order=True)
class Desription:
    info: str
    GUI_title: str


from .devices_dataclass import *
from .measurments_dataclass import *
from .stpmtr_dataclass import *
from .projects_dataclass import *


@dataclass(frozen=True)
class CmdStruct:
    name: str
    func_input: FuncInput
    func_output: FuncOutput
