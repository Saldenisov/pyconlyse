from dataclasses import dataclass


@dataclass(frozen=True)
class CmdStruct:
    name: str
    parameters: dict