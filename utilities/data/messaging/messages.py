import logging
from base64 import b64encode
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from json import dumps
from msgpack import packb, unpackb
from typing import Any, NamedTuple, Dict
from zlib import compress

from communication.interfaces import MessageInter
from errors.messaging_errors import MessageError
from devices.interfaces import DeviceType, DeviceId
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
    available_services: Dict[DeviceId, str]


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


@dataclass(order=True)
class MessengerInfoMes:
    id: str = ''
    public_key: str = ''
    public_sockets: dict = field(default_factory=dict)


@dataclass(frozen=True, order=True)
class HeartBeat:
    event_n: int
    event_tick: float
    device_id: str
    device_public_sockets: dict
    device_public_key: bytes


@dataclass(order=True)
class WelcomeInfoDevice:
    """
    Must be remembered that WelcomeInfoDevice.device_public_key must be crypted with Server public key and will be
    decrypted on Server side by Server private key, a only after that session_key will be created and used between
    Server and Device communication.
    """
    device_id: str
    device_name: str
    device_type: DeviceType
    device_status: DeviceStatus
    device_public_key: bytes
    device_public_sockets: dict


@dataclass(order=True)
class WelcomeInfoServer:
    """
    Must be remembered that WelcomeInfoServer must be crypted with Device public key and will be decrypted on
    Device side by Device private key, a only after that session_key will be used in communication between
    Server and Device.
    """
    device_id: str
    device_session_key: str
    device_name: str
    device_status: DeviceStatus
    device_public_sockets: dict


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
class ShutDown:
    device_id: str
    reason: str = ""


@dataclass(frozen=True, order=True)
class DemandMes:
    device_id: str
    com: Dict[str, Any]


@dataclass(frozen=True, order=True)
class CheckService:
    service_id: str


@dataclass
class Error:
    comments: str


@dataclass(frozen=True, order=True)
class MsgError:
    error_comments: str = ''


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
from utilities.data.messaging.message_types import MsgType, MessageInfo
import sys

class MsgCommon(Enum):
    ALIVE = MessageInfo('alive', MsgType.DIRECTED, None, set(), True)
    AVAILABLE_SERVICES = MessageInfo('available_services', MsgType.DIRECTED, AvailableServices,
                                     set(['available_services']), True)
    ERROR = MessageInfo('error', MsgType.DIRECTED, MsgError, set(['error_comments', 'reply_to', 'receiver_id']), True)
    HEARTBEAT = MessageInfo('heartbeat', MsgType.BROADCASTED, HeartBeat, set(['event']), False)
    SHUTDOWN = MessageInfo('shutdown', MsgType.BROADCASTED, ShutDown, set(['reason']), False)
    TEST_ONE = MessageInfo('test', MsgType.DIRECTED, Test, set(), False)
    WELCOME_INFO_DEVICE = MessageInfo('welcome_info_device', MsgType.DIRECTED, WelcomeInfoDevice,
                                      set(['reply_to', 'receiver_id']), False)
    WELCOME_INFO_SERVER = MessageInfo('welcome_info_server', MsgType.DIRECTED, WelcomeInfoServer,
                                      set(['reply_to', 'receiver_id']), False)

    @property
    def msg_name(self):
        value: MessageInfo = self.value
        return value.name

    @property
    def msg_crypted(self):
        value: MessageInfo = self.value
        return value.crypted

    @property
    def msg_type(self):
        value: MessageInfo = self.value
        return value.type


@dataclass(order=True)
class Message(MessageInter):
    """
    !!! Better not to change order of the parameters  !!!
    """
    com: str  # command name
    crypted: bool
    info: dataclass  # DataClass
    receiver_id: str
    reply_to: str
    sender_id: str
    type: MsgType
    id: str = ''

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, 'id', unique_id())

    def short(self):
        t = str(self.info)
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
        """
        Considered to by better in performance and size compared to json representation
        :return: string of bytes when success or b'' if error
        """
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

    @staticmethod

    def msgpack_bytes_to_msg(mes_bytes: bytes) -> MessageInter:
        try:
            mes_unpacked = unpackb(mes_bytes)
            info_class = eval(mes_unpacked[2])
            mes_unpacked.pop(2)
            info = info_class(**mes_unpacked[2])
            mes_unpacked.pop(2)
            mes_unpacked.insert(2, info)
            parameters = {}
            for param_name, param in zip(Message.__annotations__, mes_unpacked):
                parameters[param_name] = param
            return Message(**parameters)
        except Exception as e:
            raise MessageError(f'Error {e} in msgpack_bytes_to_msg')


from base64 import b64decode
from json import loads
from zlib import decompress

def msg_verification(msg: Message) -> bool:
    # TODO: add functionality
    return True

