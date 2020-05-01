from typing import Union, List
from devices.devices import Server, Service
from communication.messaging.messages import *
from datastructures.mes_independent.stpmtr_dataclass import *
import pytest

from tests.fixtures.server import server
from tests.fixtures.services import stpmtr_emulate
def test_messages(server: Server, stpmtr_emulate: Service):
    def msg_bytes_back_assert(msgs: List[Union[MessageExt, MessageInt]]):
        msgs_bytes = []
        for msg in msgs:
            if isinstance(msg, MessageExt):
                msgs_bytes.append(msg.msgpack_repr())
            else:
                msgs_bytes.append(b'')
        for msg, msg_bytes in zip(msgs, msgs_bytes):
            if isinstance(msg, MessageExt):
                assert msg == MessageExt.msgpack_bytes_to_msg(msg_bytes)


    # Msg generation testing for Server
    # TODO: need to fill with all messages
    msgs = []

    msg_device_info = server.generate_msg(msg_com=MsgComInt.DEVICE_INFO_INT, sender_id='sender_id')


    msgs.append(msg_device_info)

    msg_available_services = server.generate_msg(msg_com=MsgComExt.AVAILABLE_SERVICES,
                                                 available_services=server.available_services,
                                                 reply_to='', receiver_id='receiver_id')

    # MessageExt to MessageInt conversion
    msg_available_services_int = msg_available_services.ext_to_int()

    msgs.append(msg_available_services)
    msg_error = server.generate_msg(msg_com=MsgComExt.ERROR, error_comments='test_error', reply_to='',
                                    receiver_id='receiver_id')
    msgs.append(msg_error)

    msg_welcome = server.generate_msg(msg_com=MsgComExt.WELCOME_INFO_SERVER, reply_to='', receiver_id='receiver_id')
    msgs.append(msg_welcome)


    # Msg conversion to bytes and back for Server
    msg_bytes_back_assert(msgs)


    # Msg generation testing for stpmtr_emulate
    stpmtr_emulate
    msgs = []

    msg_available_services = stpmtr_emulate.generate_msg(msg_com=MsgComExt.AVAILABLE_SERVICES,
                                                         available_services=server.available_services,
                                                         reply_to='', receiver_id='receiver_id')
    msgs.append(msg_available_services)
    msg_error = stpmtr_emulate.generate_msg(msg_com=MsgComExt.ERROR, error_comments='test_error', reply_to='',
                                            receiver_id='receiver_id')
    msgs.append(msg_error)

    msg_bytes_back_assert(msgs)







