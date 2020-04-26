from enum import Enum, Flag, auto

class MsgType(str, Enum):
    INFO = 'info'
    DEMAND = 'demand'
    REPLY = 'reply'

print(MsgType('info'))