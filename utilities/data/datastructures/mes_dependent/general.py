from dataclasses import dataclass
from enum import Enum, auto
from time import time

import utilities.data.messages as mes
from utilities.data.general import DataClass_unfrozen


class ConnectionPermission(Enum):
    GRANTED = auto()
    DENIED = auto()
    TEMPORARY = auto()


class AccessLevel(Enum):
    GOD_LEVEL = auto()
    FULL_LEVEL = auto()
    READ_ONLY_LEVEL = auto()
    NONE_LEVEL = auto()


@dataclass(order=True)
class Connection(DataClass_unfrozen):
    device_info: mes.DeviceInfoMes = None
    # TODO: I do not know if session_key should be here
    session_key: bytes = b''
    permission: ConnectionPermission = ConnectionPermission.DENIED
    access_level: AccessLevel = AccessLevel.NONE_LEVEL


@dataclass(frozen=False, order=True)
class PendingDemand:
    message: mes.Message
    attempt: int = 0
    time: float = time()


@dataclass(frozen=False, order=True)
class PendingReply:
    message: mes.Message
    attempt: int = 0
    time: float = time()
