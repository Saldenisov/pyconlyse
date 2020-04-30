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


@dataclass(frozen=True)
class CmdStruct:
    name: str
    func_input: FuncInput
    func_output: FuncOutput