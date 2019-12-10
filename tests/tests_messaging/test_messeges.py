import communication.messaging.message_utils as mu
from utilities.data.messages import *
from tests.tests_messaging.fixtures import my_server
import pytest


def test_msg_to_json(my_server):
    # Form message
    server = my_server
    msg = mu.gen_msg(com='test', device=server)
    # mes to json conversion
    try:
        json_msg = msg.json_repr(compression=False)
        json_msg_c = msg.json_repr()
        passed_mes_to_json = True
    except Exception as e:
        passed_mes_to_json = False
    finally:
        assert passed_mes_to_json
        assert isinstance(json_msg, bytes)
        assert isinstance(json_msg_c, bytes)

    # json str to mes conversion
    try:
        import json
        msg_out_c = mu.json_to_message(json_msg_c)
        msg_out = mu.json_to_message(json_msg)
        passed_json_to_mes = True
    except Exception as e:
        passed_json_to_mes = False
    finally:
        assert passed_json_to_mes
        assert msg == msg_out
        assert msg == msg_out_c


def stop_test_msg_verification(my_server):
    # Form message
    server = my_server
    msg = mu.gen_msg(com='test', device=server)
    assert isinstance(msg, Message)


