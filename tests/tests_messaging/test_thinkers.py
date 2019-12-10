from time import sleep
from communication.messaging.message_utils import gen_msg
import utilities.data.messages as mes
from devices.devices import Server, Service
from tests.tests_messaging.fixtures import my_server, my_stpmtrservice

import pytest


def test_stpmtr_service_thinker(my_server: Server, my_stpmtrservice: Service):
    server: Server = my_server
    service: Service = my_stpmtrservice
    server_info = my_server.info()

    # generate server HB
    msg_hb_server: mes.Message = gen_msg(com='heartbeat', device=server)
    """
    msg 'hello server' is generated and added to task_out queue
    server heartbeat event is registered
    server info is added to connections of Service
    """
    service.thinker.react_info(msg_hb_server)
    assert server.id in service.connections
    assert 'server_heartbeat' in service.thinker.events

    # greetings, i.e., 'welcome' msg is not arrived from Server yet
    assert not service.connections[server.id].greetings

    _, msg_hello = service.thinker._tasks_out.popitem()
    # 'welcome' msg is generated based on msg 'hello' from service
    msg_welcome = gen_msg('welcome', device=server, msg_i=msg_hello)
    service.thinker.react_reply(msg_welcome)
    # now greetings are received from Server
    assert service.connections[server.id].greetings

    # Server heartbeat event is not active thus timeout counter is active in service 'server_heartbeat' event loop
    sleep(0.25)
    # after 0.25s it should count at least 2 timeout, default event.tick is set to 100ms
    assert service.thinker.events['server_heartbeat'].counter_timeout > 1
    sleep(1)
    # after 1s counter_timeout > 10, thus Serive.thinker.react_internal will delete info about Server from Service
    assert 'server_heartbeat' not in service.thinker.events
    assert server.id not in service.connections

    service.start()
    service.messenger.paused = True
    msg_hb_server: mes.Message = gen_msg(com='heartbeat', device=server)
    """
    task_in.teck is 0.1ms default, thus msg_hb_server will reach Thinker.react_info rapidly, 'hello server' msg will be
    generated and transfered to add_task_out, which has 0.1ms default tick
    """
    service.thinker.add_task_in(msg_hb_server)
    sleep(0.01)
    assert len(service.messenger._msg_out) == 1
    # after 50ms Service.Thinker.event(pending_demands) did not go one cycle, default event.tick is 200ms
    key, items = list(service.thinker._demands_pending_answer.items())[0]
    assert service.thinker._demands_pending_answer[key].attempt == 0
    sleep(0.3)
    # after 300ms second loop starts, giving attempt=2
    assert service.thinker._demands_pending_answer[key].attempt == 2
    sleep(0.4)
    assert len(list(service.thinker._demands_pending_answer.items())) == 0

    msg_hb_server: mes.Message = gen_msg(com='heartbeat', device=server)
    service.thinker.add_task_in(msg_hb_server)
    sleep(0.01)

    service.stop()


def test_stpmtr_service_thinker___(my_server: Server, my_stpmtrservice: Service):
    server: Server = my_server
    service: Service = my_stpmtrservice

    server.start()
    service.start()
    sleep(1)
    assert server.id in service.connections
    assert 'server_heartbeat' in service.thinker.events
    sleep(1)
    assert service.connections[server.id].greetings
    assert service.id in server.services_running

    # service.thinker.pause()
    service.messenger.pause()
    sleep(1.2)
    # assert f'service_heartbeat:{service.id}' not in server.thinker.events

    # service.thinker.unpause()
    service.messenger.unpause()

    # assert f'service_heartbeat:{service.id}' in server.thinker.events
    service.stop()
    sleep(.2)
    server.stop()
