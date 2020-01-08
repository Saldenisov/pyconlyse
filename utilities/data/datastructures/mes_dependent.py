from collections import OrderedDict
from dataclasses import dataclass
from time import time
from typing import Dict

import utilities.data.messages as mes
from utilities.data.general import DataClass_unfrozen
from utilities.data.messages import Message


@dataclass(order=True)
class Connection(DataClass_unfrozen):
<<<<<<< HEAD
    heartbeat_info: mes.EventInfoMes = None
=======
>>>>>>> stpmtr_newport
    device_info: mes.DeviceInfoMes = None


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


class OrderedDictMod(OrderedDict):

    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name

    def __setitem__(self, key, value):
        if key not in self:
            super().__setitem__(key, value)
        else:
            raise KeyError(f'Key: {key} already exists in {self.name}    {self}')


class OrderedDictMesTypeCounter(OrderedDict):

    def __init__(self, name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = name
        self.mes_types: Dict[str, int] = {}

    def __setitem__(self, key, value):
        if key not in self:
            super().__setitem__(key, value)
            if isinstance(value, Message):
                msg: Message = value
            elif isinstance(value, PendingDemand) or isinstance(value, PendingReply):
                msg = value.message
            else:
                raise TypeError(f'Wrong type is passed {type(value)}')
            if msg.body.type in self.mes_types:
                self.mes_types[msg.body.type] += 1
            else:
                self.mes_types[msg.body.type] = 1
        else:
            raise KeyError(f'Key: {key} already exists in {self.name}')

    def __delitem__(self, key):
        try:
            value = self[key]
            super().__delitem__(key)
            if isinstance(value, Message):
                msg: Message = value
            elif isinstance(value, PendingDemand) or isinstance(value, PendingReply):
                msg = value.message

            mes_type = msg.body.type
            if self.mes_types[mes_type] == 1:
                del self.mes_types[mes_type]
            else:
                self.mes_types[mes_type] -= 1
        except (Exception, KeyError) as e:
            raise e
