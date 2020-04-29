from enum import Enum, Flag, auto
from dataclasses import dataclass

@dataclass
class DC:
    name: str = '1'
    value: int = 2

    @staticmethod
    def a():
        print(DC())


class MsgType(str, Enum):
    INFO = DC('info', 1)
    DEMAND = DC('demand', 2)
    REPLY = DC('reply', 3)

class A:
    b = ['a']

    def p(self):
        self.b.append('c')
        print(self.b)

if MsgType.REPLY in MsgType:
    print(1)