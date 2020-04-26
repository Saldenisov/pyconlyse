from utilities.data.messaging import *
from utilities.data.datastructures.mes_independent.stpmtr_dataclass import *
import pytest


def test_messages():

    info = DoIt(com='do_something', input=FuncGetPosInput(axis_id=1))
    msgTest1 = Message(com='test', type=MsgType.INFO, info=info, sender_id="test_sender",
                       receiver_id='test_receiver')
    from sys import getsizeof
    print(getsizeof(msgTest1.json_repr()))
    print(getsizeof(msgTest1.msgpack_repr()))





