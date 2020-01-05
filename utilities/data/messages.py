import logging
from base64 import b64encode
from collections import deque
from dataclasses import dataclass, field
from json import dumps
from typing import NamedTuple, Dict, Any
from zlib import compress

from communication.interfaces import MessageInter
from utilities.data.datastructures.mes_independent import DeviceStatus
from utilities.myfunc import unique_id

module_logger = logging.getLogger(__name__)


# __repr__ function for MyDataClass and data classes
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
class ForwardMessage:
    forwarded: MessageInter

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
    messenger_id: str
    name: str = None
    type: str = None  # service, client, server
    class_type: str = None
    device_status: DeviceStatus = None
    public_sockets: dict = field(default_factory=dict)


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
    device_status: DeviceStatus = DeviceStatus()
    device_id: str = ''
    device_decription: dict = field(default_factory=dict)
    available_public_functions: dict = field(default_factory=dict)


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
class CheckClient:
    client_id: str


@dataclass(frozen=True, order=True)
class Unknown:
    comment: str = ''


@dataclass(frozen=True, order=True)
class Error:
    comments: str = ''


@dataclass(frozen=True, order=True)
class InfoViewUpdate:
    widget_name: str
    parameters: dict


@dataclass(frozen=True, order=True)
class Test:
    id: str = ''
    parameters: dict = field(default_factory=dict)


# General structure of message
@dataclass(order=True)
class MessageData:
    com: str # command
    info: object # DataClass


@dataclass(order=True)
class MessageBody:
    type: str
    sender_id: str
    receiver_id: str = ''


@dataclass(order=True)
class Message(MessageInter):
    body: MessageBody
    data: MessageData
    id: str = ''
    reply_to: str = ''
    crypted: bool = False

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, 'id', unique_id())

    def short(self):
        return {'sender_id':  self.body.sender_id,
                'rec_id': self.body.receiver_id,
                'data': self.data.com,
                'reply_to': self.reply_to,
                'id': self.id}

    def json_repr(self, compression=True):
        def message_to_json(msg: Message, compression: bool) -> bytes:
            try:
                json_str = dumps(repr(msg)).encode('utf-8')
                if compression:
                    json_str_c = compress(json_str)
                    json_str_c = b64encode(json_str_c)
                    return json_str_c
                else:
                    return json_str
            except Exception as e:
                module_logger.error(e)
                raise e

        return message_to_json(self, compression)


class MessageStructure(NamedTuple):
    type: str
    mes_class: object  # DataClass
    mes_name: str = ""

@dataclass
class Test():
    filed1: str = 'test'
    field2: Unknown = Unknown(comment='test')


# Test Messages correct
info = Test()
body = MessageBody('info', 'TestSender', 'TestReceiver')
data = MessageData(com='test1', info=info)
msgTest1 = Message(body, data)

info = Test()
body = MessageBody('demand', 'TestSender', 'TestReceiver')
data = MessageData(com='test2', info=info)
msgTest2 = Message(body, data)

info = Test()
body = MessageBody('reply', 'TestSender', 'TestReceiver')
data = MessageData(com='test3', info=info)
msgTest3 = Message(body, data)

info = Test()
body = MessageBody('reply', 'TestSender', 'TestReceiver')
data = MessageData(com='test3', info=info)
msgTest4 = Message(body, data)

msgs_correct = [msgTest1, msgTest2, msgTest3, msgTest4]



# Test Messages correct
info = Test()
body = MessageBody('test', 'TestSender', 'TestReceiver')
data = MessageData(com='test', info=info)
msgTest_incorrect = Message(body, data)

msgs_incorrect = [msgTest_incorrect]