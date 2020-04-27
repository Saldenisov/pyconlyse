from abc import ABC
from enum import Enum
from typing import NewType


DeviceId = NewType('DeviceId', str)

class DeviceType(str, Enum):
    """
    Basic types of devices: Client, Server, Service
    """
    CLIENT = 'client'
    SERVER = 'server'
    SERVICE = 'service'


class DeviceInter(ABC):
    pass


class ExecutorInter(ABC):
    pass