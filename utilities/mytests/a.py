from enum import Enum, Flag, auto
from dataclasses import dataclass
from types import  DynamicClassAttribute

@dataclass
class DC:
    name: str = '1'
    value: int = 2


class MsgType(Enum):
    INFO = DC('info', 1)
    DEMAND = DC('demand', 2)
    REPLY = DC('reply', 3)

    @property
    def name(self):
        return self.value.name


print(MsgType.INFO.name)

