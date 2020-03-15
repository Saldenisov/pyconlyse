from time import sleep

from communication.logic.thinkers_logic import ThinkerEvent
from communication.messaging.message_utils import gen_msg

address_server = {'frontend': 'tcp://127.0.0.1:5554', 'backend': 'tcp://127.0.0.1:5555',
                  'publisher': 'tcp://127.0.0.1:5556'}


#
def STOP_test_server_service_messengers(server_messenger, service_messenger):
    event: ThinkerEvent = ThinkerEvent(name='heartbeat_test',
                                       external_name='heartbeat_external',
                                       event_id='event_id',
                                       parent= None,
                                       logic_func=None)
    msg_hb = gen_msg('heartbeat', server_messenger, event=event)
    server_messenger.start()
    service_messenger.connect()
    service_messenger.start()
    server_messenger.send_msg(msg_hb)
    sleep(.1)
    assert service_messenger.msg_received.data.com == 'heartbeat'
    service_messenger.msg_received = ''
    server_messenger.send_msg(msg_hb)
    sleep(.1)
    assert service_messenger.msg_received.data.com == 'heartbeat'
    service_messenger.stop()
    server_messenger.stop()








