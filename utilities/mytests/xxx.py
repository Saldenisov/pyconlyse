from dataclasses import dataclass, asdict

@dataclass
class FuncOutput:
    func_res: bool
    comments: str

@dataclass
class FuncActivateOutput(FuncOutput):
    flag: bool


a = FuncActivateOutput(True, 'adas', False)

b= asdict(a)
print(b)
