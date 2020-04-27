from dataclasses import dataclass
from typing import NamedTuple, List, Set
from enum import Enum, auto



class MsgType(str, Enum):
    INFO = 'info'
    DEMAND = 'demand'
    REPLY = 'reply'


class MessageInfo(NamedTuple):
    name: str
    type: MsgType
    info_class: dataclass  # DataClass
    must_have_param: Set[str]  # Set of parameters names must be present in param dict for device.generate_msg()
    crypted: bool
