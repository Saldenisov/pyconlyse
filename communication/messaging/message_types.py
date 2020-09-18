from dataclasses import dataclass
from enum import Enum, auto
from typing import NamedTuple, List


class Permission(Enum):
    NONE = auto()
    GRANTED = auto()
    DENIED = auto()
    TEMPORARY = auto()


class AccessLevel(Enum):
    GOD = auto()
    FULL = auto()
    READ_ONLY = auto()
    NONE = auto()


class MsgType(str, Enum):
    BROADCASTED = 'broadcasted'
    DIRECTED = 'directed'


class MessageInfoInt(NamedTuple):
    info_class: dataclass  # DataClass


class MessageInfoExt(NamedTuple):
    type: MsgType
    info_class: dataclass  # DataClass
    must_have_param: List[str]  # Set of parameters names must be present in param dict for device.generate_msg()
    crypted: bool
