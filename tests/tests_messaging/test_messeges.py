from typing import Union, List
from devices.devices import Server, Service
from utilities.data.messaging.messages import *
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import *
import pytest

from tests.fixtures.server import server
from tests.fixtures.services import stpmtr_emulate
def test_messages(server: Server, stpmtr_emulate: Service):
    def msg_bytes_back_assert(msgs: List[Message]):
        msgs_bytes = []
        for msg in msgs:
            msgs_bytes.append(msg.msgpack_repr())
        for msg, msg_bytes in zip(msgs, msgs_bytes):
            assert msg == Message.msgpack_bytes_to_msg(msg_bytes)



    # Msg generation testing for Server
    # TODO: need to fill with all messages
    msgs = []

    msg_available_services = server.generate_msg(msg_com=MsgCommon.AVAILABLE_SERVICES,
                                                 available_services=server.available_services,
                                                 reply_to='', receiver_id='receiver_id')
    msgs.append(msg_available_services)
    msg_error = server.generate_msg(msg_com=MsgCommon.ERROR, error_comments='test_error', reply_to='',
                                    receiver_id='receiver_id')
    msgs.append(msg_error)

    msg_welcome = server.generate_msg(msg_com=MsgCommon.WELCOME_INFO_SERVER, reply_to='', receiver_id='receiver_id')
    msgs.append(msg_welcome)

    # Msg conversion to bytes and back for Server
    msg_bytes_back_assert(msgs)


    # Msg generation testing for stpmtr_emulate
    stpmtr_emulate
    msgs = []

    msg_available_services = stpmtr_emulate.generate_msg(msg_com=MsgCommon.AVAILABLE_SERVICES,
                                                         available_services=server.available_services,
                                                         reply_to='', receiver_id='receiver_id')
    msgs.append(msg_available_services)
    msg_error = stpmtr_emulate.generate_msg(msg_com=MsgCommon.ERROR, error_comments='test_error', reply_to='',
                              receiver_id='receiver_id')
    msgs.append(msg_error)

    msg_bytes_back_assert(msgs)







