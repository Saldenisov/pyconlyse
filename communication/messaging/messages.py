import logging
from base64 import b64encode
from dataclasses import asdict
from enum import Enum
from msgpack import packb, unpackb
from json import dumps
from zlib import compress

from communication.interfaces import Message
from communication.messaging.message_types import MsgType, MessageInfoInt, MessageInfoExt
from datastructures.mes_independent.devices_dataclass import *
from utilities.errors.messaging_errors import MessageError
from utilities.myfunc import unique_id

module_logger = logging.getLogger(__name__)


class MsgComInt(Enum):
    DEVICE_INFO_INT = MessageInfoInt(DeviceInfoInt, set([]))
    HEARTBEAT = MessageInfoInt(HeartBeat, set(['event']))

    @property
    def msg_name(self):
        return self._name_

    @property
    def msg_type(self):
        value: MessageInfoExt = self.value
        return value.type


class MsgComExt(Enum):
    ALIVE = MessageInfoExt(MsgType.DIRECTED, None, set(['receiver_id']), True)
    AVAILABLE_SERVICES = MessageInfoExt(MsgType.DIRECTED, AvailableServices,
                                        set(['available_services']), True)
    DO_IT = MessageInfoExt(MsgType.DIRECTED, DoIt, set(['receiver_id', 'func_input']), True)
    DONE_IT = MessageInfoExt(MsgType.DIRECTED, DoneIt, set(['receiver_id', 'reply_to', 'func_output']), True)
    ERROR = MessageInfoExt(MsgType.DIRECTED, MsgError, set(['error_comments', 'reply_to', 'receiver_id']), False)
    HEARTBEAT = MessageInfoExt(MsgType.BROADCASTED, HeartBeat, set(['event']), False)
    HEARTBEAT_FULL = MessageInfoExt(MsgType.BROADCASTED, HeartBeatFull, set(['event']), False)
    SHUTDOWN = MessageInfoExt(MsgType.BROADCASTED, ShutDown, set(['reason']), False)
    WELCOME_INFO_DEVICE = MessageInfoExt(MsgType.DIRECTED, WelcomeInfoDevice, set(['receiver_id', 'event']), False)
    WELCOME_INFO_SERVER = MessageInfoExt(MsgType.DIRECTED, WelcomeInfoServer, set(['reply_to', 'receiver_id']), False)

    @property
    def msg_name(self):
        return self._name_

    @property
    def msg_crypted(self):
        value: MessageInfoExt = self.value
        return value.crypted

    @property
    def msg_type(self):
        value: MessageInfoExt = self.value
        return value.type


@dataclass(order=True)
class MessageInt(Message):
    """
    !!! Better not to change order of the parameters  !!!
    """
    com: str  # command name
    info: dataclass  # DataClass
    sender_id: str


@dataclass(order=True)
class MessageExt(Message):
    """
    !!! Better not to change order of the parameters  !!!
    """
    com: str  # command name
    crypted: bool
    info: dataclass  # DataClass
    receiver_id: str
    reply_to: str
    sender_id: str
    #type: MsgType  # temporary disabled TODO: to think what to do with it
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
                'datastructures': f'{self.com}: {t[0:l]}...',
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

    def ext_to_int(self) -> MessageInt:
        return MessageInt(com=self.com, info=self.info, sender_id=self.sender_id)

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
        except (ValueError, TypeError) as e:
            module_logger.error(e)
            return b''

    @staticmethod
    def msgpack_bytes_to_msg(mes_bytes: bytes) -> Message:
        try:
            mes_unpacked = unpackb(mes_bytes)
            info_class = eval(mes_unpacked[2])
            mes_unpacked.pop(2)
            info = info_class(**mes_unpacked[2])
            mes_unpacked.pop(2)
            mes_unpacked.insert(2, info)
            parameters = {}
            for param_name, param in zip(MessageExt.__annotations__, mes_unpacked):
                parameters[param_name] = param
            return MessageExt(**parameters)
        except Exception as e:
            raise MessageError(f'Error {e} in msgpack_bytes_to_msg')
