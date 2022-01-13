from dataclasses import dataclass


@dataclass
class FuncInput:
    pass

@dataclass
class FuncOutput:
    comments: str
    func_success: bool


@dataclass(frozen=True)
class CmdStruct:
    #name: str
    func_input: FuncInput
    func_output: FuncOutput
    func_prepared: FuncOutput = None

    @property
    def name(self):
        return self.func_input.com

    @property
    def name_prepared(self):
        if self.func_prepared:
            return self.func_prepared.com
        else:
            return ''
