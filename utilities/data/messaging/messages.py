import logging
from base64 import b64encode
from collections import deque
from dataclasses import dataclass, field, asdict
from json import dumps
from msgpack import packb, unpackb
from typing import Any, NamedTuple, Dict, Union
from zlib import compress

from communication.interfaces import MessageInter
from devices.interfaces import DeviceType
from utilities.data.datastructures.mes_independent.devices_dataclass import DeviceStatus, FuncInput, FuncOutput
from utilities.data.datastructures.mes_independent import Desription

from utilities.myfunc import unique_id

module_logger = logging.getLogger(__name__)

# __repr__ func
# tion for MyDataClass and data classes
def f(obj: object) -> str:
    out = []
    if tuple in obj.__class__.__bases__:
        keys = obj._fields
    else:
        keys = obj.__dict__.keys()

    for key in keys:
        if obj.__getattribute__(key).__class__.__name__ in globals():
            elm = (obj.__getattribute__(key).__class__.__name__, obj.__getattribute__(key))
            out.append(elm)
        else:
            out.append(repr(obj.__getattribute__(key)))
    return str(out)


@dataclass(frozen=True, order=True)
class AvailableServices:
    running_services: dict
    all_services: dict = field(default_factory=dict)


@dataclass(frozen=True, order=True)
class AreYouAliveDemand:
    context: str = ''


@dataclass(frozen=True, order=True)
class AreYouAliveReply:
    context: str = ''
    extra: object = None


@dataclass(frozen=True, order=True)
class DoIt:
    com: str
    input: FuncInput


@dataclass(frozen=True, order=True)
class DoneIt:
    com: str
    result: FuncOutput


@dataclass(frozen=True, order=True)
class Forward_msg:
    service_id: str
    demand: dict  # {'com': com, 'parameters': {'name1':name1value, 'name2': name2value}}


@dataclass(order=True)
class MessengerInfoMes:
    id: str = ''
    public_key: str = ''
    public_sockets: dict = field(default_factory=dict)


@dataclass(frozen=True, order=True)
class EventInfoMes:
    event_id: str
    event_name: str
    device_id: str
    tick: float = 0.1
    n: float = 0.0
    sockets: dict = field(default_factory=dict)


@dataclass(order=True)
class DeviceInfoMes:
    device_id: str
    name: str
    type: DeviceType
    device_status: DeviceStatus
    public_key: bytes = b''
    public_sockets: dict = field(default_factory=dict)


@dataclass(order=True)
class WelcomeInfoServer:
    device_id: str
    session_key: str
    name: str
    device_status: DeviceStatus
    public_sockets: dict


@dataclass(frozen=True, order=True)
class ServerStatusMes:
    device_status: DeviceStatus
    services_running: dict = field(default_factory=dict)
    services_available: list = field(default_factory=list)


@dataclass(frozen=True, order=True)
class ServiceStatusMes:
    device_status: DeviceStatus


@dataclass(frozen=True, order=True)
class ServiceInfoMes:
    device_status: DeviceStatus
    device_id: str
    device_description: Desription
    available_public_functions: list = field(default_factory=list)


@dataclass(frozen=True, order=True)
class ClientStatusMes:
    device_status: DeviceStatus


@dataclass(frozen=True, order=True)
class ServerStatusExtMes:
    device_status: DeviceStatus
    services_running: dict = field(default_factory=dict)
    services_available: list = field(default_factory=list)
    events_running: dict = field(default_factory=dict)
    clients_running: dict = field(default_factory=dict)


@dataclass(frozen=True, order=True)
class ServerInfoQueKeysMes:
    queue_in_keys: deque = field(default_factory=deque)
    queue_out_keys: deque = field(default_factory=deque)
    queue_in_pending_keys: deque = field(default_factory=deque)


@dataclass(frozen=True, order=True)
class ShutDownMes:
    device_id: str
    reason: str = ""


@dataclass(frozen=True, order=True)
class DemandMes:
    device_id: str
    com: Dict[str, Any]


@dataclass(frozen=True, order=True)
class CheckService:
    service_id: str


@dataclass(frozen=True, order=True)
class Error:
    comments: str = ''


@dataclass(frozen=True, order=True)
class CheckClient:
    client_id: str


@dataclass(frozen=True, order=True)
class InfoViewUpdate:
    widget_name: str
    parameters: dict


@dataclass(frozen=True, order=True)
class PowerOnDemand:
    device_id: str
    power_on: bool


@dataclass(frozen=True, order=True)
class PowerOnReply:
    device_id: str
    power_on: bool
    comments: str = ""


@dataclass(frozen=True, order=True)
class Unknown:
    comment: str = ''


@dataclass(frozen=True, order=True)
class Test:
    id: str = ''
    parameters: dict = field(default_factory=dict)


# General structure of message
from utilities.data.messaging.message_types import MsgType, MessageStructure


class MsgCom:
    HEARTBEAT = MessageStructure('heartbeat', MsgType.INFO, EventInfoMes)
    SHUTDOWN = MessageStructure('shutdown', MsgType.INFO, ShutDownMes)
    WELCOME_INFO = MessageStructure('welcome_info', MsgType.REPLY, WelcomeInfoServer)
    ARE_YOU_ALIVE = MessageStructure('are_you_alive_reply', MsgType.DEMAND, None)


@dataclass(order=True)
class Message(MessageInter):
    com: MsgCom  # command
    type: MsgType
    info: dataclass  # DataClass
    sender_id: str
    receiver_id: str = ''
    id: str = ''
    reply_to: str = ''
    crypted: bool = False

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, 'id', unique_id())

    def short(self):
        t = str(self.data.info)
        l = len(t)
        if l > 300 and l < 1000:
            l = int(0.8*l)
        elif l > 1000:
            l = 300
        else:
            pass
        return {'path':  f'{self.sender_id}->{self.receiver_id}',
                'data': f'{self.com}: {t[0:l]}...',
                'reply_to': self.reply_to,
                'id': self.id}

    def json_repr_long(self, compression=True) -> bytes:
        try:
            json_str = dumps(repr(self)).encode('utf-8')
            if compression:
                json_str_c = compress(json_str)
                json_str_c = b64encode(json_str_c)
                return json_str_c
            else:
                return json_str
        except Exception as e:  # TODO replace with reasonable
            module_logger.error(e)
            return b''

    def json_repr(self, compression=True) -> bytes:
        try:
            msg_l = []
            for name in self.__annotations__:
                value = getattr(self, name)
                if name == 'info':
                    msg_l.append(type(value))
                    value = asdict(value)
                elif isinstance(value, MsgType):
                    value = value.value
                msg_l.append(value)
            json_str = dumps(repr(msg_l)).encode('utf-8')
            if compression:
                json_str_c = compress(json_str)
                json_str_c = b64encode(json_str_c)
                return json_str_c
            else:
                return json_str
        except Exception as e:  # TODO replace with reasonable
            module_logger.error(e)
            return b''

    def msgpack_repr(self) -> bytes:
        try:
            msg_l = []
            for name in self.__annotations__:
                value = getattr(self, name)
                if name == 'info':
                    msg_l.append(value.__class__.__name__)
                    value = asdict(value)
                elif isinstance(value, MsgType):
                    value = value.value
                msg_l.append(value)
            msgpack_repr = packb(msg_l)
            return msgpack_repr
        except ValueError as e:
            module_logger.error(e)
            return b''

