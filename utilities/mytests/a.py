from enum import Enum, Flag, auto
from dataclasses import dataclass

@dataclass
class DC:
    name: str = '1'
    value: int = 2


class MsgType(str, Enum):
    INFO = DC('info', 1)
    DEMAND = DC('demand', 2)
    REPLY = DC('reply', 3)



print(MsgType['DEMAND'] not in MsgType)

