from collections import OrderedDict
from dataclasses import dataclass
from time import time
from typing import Dict

import utilities.data.messages as mes
from utilities.data.general import DataClass_unfrozen
from utilities.data.messages import Message


@dataclass(order=True)
class Connection(DataClass_unfrozen):
    device_info: mes.DeviceInfoMes = None
    # TODO: I do not know if session_key should be here
    session_key: bytes = b''


@dataclass(frozen=False, order=True)
class PendingDemand:
    message: Message
    attempt: int = 0
    time: float = time()


@dataclass(frozen=False, order=True)
class PendingReply:
    message: Message
    attempt: int = 0
    time: float = time()


