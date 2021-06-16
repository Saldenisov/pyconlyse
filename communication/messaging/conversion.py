import logging

from communication.messaging.messages import Coding, MessageExt
from utilities.errors.messaging_errors import MessageError
from base64 import b64decode
from msgpack import unpackb
from json import loads
from zlib import decompress
from devices.datastruct_for_messaging import *

module_logger = logging.getLogger(__name__)


def bytes_to_msg(mes_bytes: bytes, coding: Coding = Coding.JSON) -> MessageExt:
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
            try:
                mes_dc = loads(decompress(b64decode(mes_bytes)))
                mes = eval(mes_dc)
                return mes
            except Exception as e:
                raise MessageError(f'Error: "{e}" in bytes_to_msg coding {coding}`. Msg={mes_bytes}')
    else:
        module_logger.info(f'{Coding.MSGPACK} is not realy working for all types of messages')
        raise MessageError(f'Wrong coding type passed {coding}. Choose between {Coding.JSON} and {Coding.MSGPACK}')


def bytes_to_info(info_bytes: bytes, coding: Coding = Coding.JSON) -> MessageExt:
    if coding is Coding.JSON:
        try:
            info_str = loads(info_bytes)
            return eval(info_str)
        except Exception as e:
            print(e, info_bytes)
            try:
                info_dc = loads(decompress(b64decode(info_bytes)))
                info = eval(info_dc)
                return info
            except Exception as e:
                raise MessageError(f'Error: "{e}" in bytes_to_info coding {coding}`. Info={info_bytes}')
    else:
        module_logger.info(f'{Coding.MSGPACK} is not realy working for all types of messages')
        raise MessageError(f'Wrong coding type passed {coding}. Choose between {Coding.JSON} and {Coding.MSGPACK}')