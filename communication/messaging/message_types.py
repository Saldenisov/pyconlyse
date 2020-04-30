from dataclasses import dataclass
from typing import NamedTuple, Set
from enum import Enum, auto


class ConnectionPermission(Enum):
    GRANTED = auto()
    DENIED = auto()
    TEMPORARY = auto()


class AccessLevel(Enum):
    GOD_LEVEL = auto()
    FULL_LEVEL = auto()
    READ_ONLY_LEVEL = auto()
    NONE_LEVEL = auto()


class MsgType(str, Enum):
    BROADCASTED = 'broadcasted'
    DIRECTED = 'directed'


class MessageInfoInt(NamedTuple):
    name: str
    info_class: dataclass  # DataClass
    must_have_param: Set[str]  # Set of parameters names must be present in param dict for device.generate_msg()


class MessageInfoExt(NamedTuple):
    name: str
    type: MsgType
    info_class: dataclass  # DataClass
    must_have_param: Set[str]  # Set of parameters names must be present in param dict for device.generate_msg()
    crypted: bool
