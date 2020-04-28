from utilities.data.messaging.messages import *
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import *
import pytest


def test_messages():

    info = Test(id='test_id', parameters={'param1': 1})
    msgTest1 = Message(com=MsgCommon.HEARTBEAT.com_name, type=MsgType.BROADCASTED, info=info, sender_id="test_sender",
                       receiver_id='test_receiver', reply_to='', crypted=False)
    print(msgTest1.msgpack_repr())





