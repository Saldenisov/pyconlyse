from dataclasses import dataclass
from typing import NamedTuple
from enum import Enum, auto



class MsgType(str, Enum):
    INFO = 'info'
    DEMAND = 'demand'
    REPLY = 'reply'


class MessageStructure(NamedTuple):
    name: str
    type: MsgType
    info_class: dataclass  # DataClass
