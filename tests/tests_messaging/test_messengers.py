from typing import List

import utilities.data.messages as mes
from communication.messaging.messengers import ServerMessenger
from tests.tests_messaging.fixtures import server_messenger, service_messenger, client_messenger
import pytest


def test_Messengers_Basics(server_messenger, service_messenger, client_messenger):
    server_messenger: ServerMessenger = server_messenger
    service_messenger: service_messenger = service_messenger
    client_messenger: client_messenger = client_messenger
    from time import sleep

    server_messenger._backendpool.add(service_messenger.id)
    server_messenger._frontendpool.add(client_messenger.id)

    msgs_correct: List[mes.Message] = mes.msgs_correct
    msg = msgs_correct[2]
    msg.body.receiver_id = service_messenger.id
    msgs_correct[2] = msg

    msg = msgs_correct[3]
    msg.body.receiver_id = client_messenger.id
    msgs_correct[3] = msg

    server_messenger.start()
    service_messenger.start()
    client_messenger.start()
    assert server_messenger.active
    assert service_messenger.active
    assert client_messenger.active

    # Testing1 server_messenger sending
    for msg in msgs_correct:
        server_messenger.send_msg(msg)
        server_messenger.add_msg_out(msg)
    assert len(server_messenger._msg_out) == 4
    sleep(0.05)
    assert len(server_messenger._msg_out) == 0

    # Testing2 service_messenger sending
    server_messenger.pause()
    for msg in msgs_correct:
        server_messenger.add_msg_out(msg)
    assert len(server_messenger._msg_out) == 4
    sleep(0.04)
    assert len(server_messenger._msg_out) == 4
    server_messenger.unpause()
    sleep(0.51)
    assert len(server_messenger._msg_out) == 0

    # Testing service_messenger sending
    for msg in msgs_correct:
        service_messenger.send_msg(msg)
        service_messenger.add_msg_out(msg)
    assert len(service_messenger._msg_out) == 4
    sleep(0.05)
    assert len(service_messenger._msg_out) == 0

    # Testing client_messenger sending
    for msg in msgs_correct:
        client_messenger.send_msg(msg)
        client_messenger.add_msg_out(msg)
    assert len(client_messenger._msg_out) == 4
    sleep(0.05)
    assert len(client_messenger._msg_out) == 0

    server_messenger.stop()
    service_messenger.stop()
    client_messenger.stop()
    assert not server_messenger.active and not server_messenger.paused
    assert not service_messenger.active and not service_messenger.paused
    assert not client_messenger.active and not client_messenger.paused
