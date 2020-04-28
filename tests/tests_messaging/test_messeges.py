from devices.devices import Server
from utilities.data.messaging.messages import *
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import *
import pytest

from tests.fixtures.server import server
def test_messages(server: Server):

    info = Test(id='test_id', parameters={'param1': 1})
    msgTest1 = Message(com=MsgCommon.HEARTBEAT.msg_name, type=MsgType.BROADCASTED, info=info, sender_id="test_sender",
                       receiver_id='test_receiver', reply_to='', crypted=False)
    msg_bytes = msgTest1.msgpack_repr()
    msgTest1_back = Message.msgpack_bytes_to_msg(msg_bytes)

    assert msgTest1 == msgTest1_back



    #Msg generation testing
    # TODO: need to fill with all messages
    msg = server.generate_msg(msg_com=MsgCommon.AVAILABLE_SERVICES, available_services=server.available_services,
                              reply_to='', receiver_id='receiver_id')
    msg = server.generate_msg(msg_com=MsgCommon.ERROR, error_comments='test_error', reply_to='',
                              receiver_id='receiver_id')





