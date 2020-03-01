from dataclasses import dataclass

@dataclass
class FuncOutput:
    func_res: bool
    comments: str

@dataclass
class FuncActivateOutput(FuncOutput):
    flag: bool


a = FuncActivateOutput()
