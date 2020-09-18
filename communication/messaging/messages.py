import logging
from base64 import b64encode, b64decode
from copy import deepcopy
from dataclasses import asdict
from json import dumps, loads
from datetime import datetime
from zlib import compress, decompress

from msgpack import packb, unpackb

from communication.interfaces import Message
from communication.messaging.message_types import MsgType, MessageInfoInt, MessageInfoExt
from utilities.datastructures.mes_independent import *
from utilities.errors.messaging_errors import MessageError
from utilities.myfunc import unique_id

module_logger = logging.getLogger(__name__)


class MsgComInt(Enum):
    DEVICE_INFO_INT = MessageInfoInt(DeviceInfoInt)
    DONE_IT = MessageInfoInt(DoneIt)
    FYI = MessageInfoInt(FYI)
    HEARTBEAT = MessageInfoInt(HeartBeat)
    ERROR = MessageInfoInt(MsgError)

    @property
    def msg_name(self):
        return self._name_

    @property
    def msg_info_class(self):
        value: MessageInfoInt = self.value
        return value.info_class


class MsgComExt(Enum):
    AVAILABLE_SERVICES = MessageInfoExt(MsgType.DIRECTED, AvailableServices, ['available_services'], True)
    DO_IT = MessageInfoExt(MsgType.DIRECTED, DoIt, ['receiver_id', 'func_input'], True)
    DONE_IT = MessageInfoExt(MsgType.DIRECTED, DoneIt, ['receiver_id', 'reply_to', 'func_output'], True)
    ERROR = MessageInfoExt(MsgType.DIRECTED, MsgError, ['comments', 'reply_to', 'receiver_id'], False)
    HEARTBEAT = MessageInfoExt(MsgType.BROADCASTED, HeartBeat, ['event'], False)
    HEARTBEAT_FULL = MessageInfoExt(MsgType.BROADCASTED, HeartBeatFull, ['event'], False)
    SHUTDOWN = MessageInfoExt(MsgType.DIRECTED, ShutDown, ['reason', 'receiver_id'], True)
    WELCOME_INFO_DEVICE = MessageInfoExt(MsgType.DIRECTED, WelcomeInfoDevice, ['receiver_id', 'event'], False)
    WELCOME_INFO_SERVER = MessageInfoExt(MsgType.DIRECTED, WelcomeInfoServer, ['reply_to', 'receiver_id'], False)

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
    com: str  # command name
    info: dataclass  # DataClass
    sender_id: str
    time_creation: float = 0
    time_bonus: float = 0.0
    forwarded_from: str = ''
    forward_to: str = ''
    receiver_id: str = ''
    id: str = ''

    def fyi_repr(self):
        if self.com == MsgComInt.FYI.msg_name:
            t = []
            info: FYI = self.info
            if info.func_name:
                t.append(f'COM: {info.func_name}')
            if info.func_success:
                t.append(f'Success: {info.func_success}')
            if info.func_success:
                t.append(f'{info.comments}')
            if self.forwarded_from:
                t.append(f'SENDER*: {self.forwarded_from[0:15]}...')
            else:
                if self.sender_id:
                    t.append(f'SENDER: {self.sender_id[0:15]}...')
                else:
                    t.append(f'SENDER: ?___?')

            if self.forward_to:
                t.append(f'RECEIVER*: {self.forward_to[0:15]}...')
            else:
                t.append(f'RECEIVER: {self.receiver_id[0:15]}...')

            return '. '.join(t)
        else:
            return self.__repr__()

    def __post_init__(self):
        if not self.time_creation:
            self.time_creation = datetime.timestamp(datetime.now())


class Coding(Enum):
    JSON = 0
    MSGPACK = 1


@dataclass(order=True)
class MessageExt(Message):
    com: str  # command name
    crypted: bool
    info: dataclass  # DataClass
    receiver_id: str
    reply_to: str
    sender_id: str
    forward_to: str = ''
    forwarded_from: str = ''
    id: str = ''

    def __post_init__(self):
        if not self.id:
            object.__setattr__(self, 'id', unique_id())

    def copy(self, **kwargs):
        msg_copy = deepcopy(self)
        for key, value in kwargs.items():
            try:
                getattr(msg_copy, key)
                object.__setattr__(msg_copy, key, value)
            except AttributeError:
                pass
        return msg_copy

    def short(self):
        t = str(self.info)
        lenght_message = len(t)
        if 300 < lenght_message < 1000:
            lenght_message = int(0.8*lenght_message)
        elif lenght_message > 1000:
            lenght_message = 300
        else:
            pass
        if not self.forwarded_from and not self.forward_to:
            return {'path':  f'{self.sender_id}->{self.receiver_id}',
                    'datastructures': f'{self.com}: {t[0:lenght_message]}...',
                    'reply_to': self.reply_to,
                    'id': self.id}
        elif self.forward_to:
            return {'path':  f'{self.sender_id}->{self.receiver_id}: FORWARD_TO->{self.forward_to}',
                    'datastructures': f'{self.com}: {t[0:lenght_message]}...',
                    'reply_to': self.reply_to,
                    'id': self.id}
        elif self.forwarded_from:
            return {'path':  f'{self.sender_id}->{self.receiver_id}: FORWARDED_FROM->{self.forwarded_from}',
                    'datastructures': f'{self.com}: {t[0:lenght_message]}...',
                    'reply_to': self.reply_to,
                    'id': self.id}

    def ext_to_int(self) -> MessageInt:
        return MessageInt(com=self.com, info=self.info, sender_id=self.sender_id, forwarded_from=self.forwarded_from)

    def fyi(self):
        func_name, func_success, comments = '', None, ''
        if hasattr(self.info, 'func_success'):
            func_success = self.info.func_success
        if hasattr(self.info, 'comments'):
            comments = self.info.comments
        if hasattr(self.info, 'com'):
            func_name = self.info.com

        info: FYI = FYI(func_name, func_success, comments)
        time_bonus = 0
        if self.com == MsgComExt.ERROR.msg_name:
            time_bonus = 5
        elif self.com == MsgComExt.DO_IT.msg_name:
            time_bonus = 2
        elif self.com == MsgComExt.DONE_IT.msg_name:
            time_bonus = 2
        elif self.com == MsgComExt.HEARTBEAT.msg_name:
            time_bonus = 0
        elif self.com == MsgComExt.WELCOME_INFO_SERVER.msg_name:
            time_bonus = 3
        return MessageInt(com=MsgComInt.FYI.msg_name, info=info, sender_id=self.sender_id,
                          receiver_id=self.receiver_id, forward_to=self.forward_to,
                          forwarded_from=self.forwarded_from, id=self.id, time_bonus=time_bonus)

    def byte_repr(self, coding: Coding = Coding.JSON, compression=True) -> bytes:
        """
        Considered to by better in performance and size compared to json representation
        :return: string of bytes when success or b'' if error
        """
        if coding is Coding.MSGPACK:
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
                module_logger.error(f'{e}:{self.short()}')
                return b''
        elif coding is Coding.JSON:
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

    @staticmethod
    def bytes_to_msg(mes_bytes: bytes, coding: Coding = Coding.JSON):
        if coding is Coding.MSGPACK:  # MSGPACK is not realy working for all type of messages
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
            except TypeError as e:
                raise MessageError(f'Error: "{e}" in bytes_to_msg coding {coding}`. Msg={mes_bytes}')
        elif coding is Coding.JSON:
            try:
                mes_str = loads(mes_bytes)
                return eval(mes_str)
            except Exception as e:
                print(e, mes_bytes)
                try:
                    mes_dc = loads(decompress(b64decode(mes_bytes)))
                    mes = eval(mes_dc)
                    return mes
                except Exception as e:
                    raise MessageError(f'Error: "{e}" in bytes_to_msg coding {coding}`. Msg={mes_bytes}')
        else:
            module_logger.info(f'{Coding.MSGPACK} is not realy working for all types of messages')
            raise MsgError(f'Wrong coding type passed {coding}. Choose between {Coding.JSON} and {Coding.MSGPACK}')
