import sys
from collections import OrderedDict
from pathlib import Path
from time import sleep

import pytest

import communication.messaging.message_utils as mu
import devices.devices as dev
import utilities.data.messages as mes
from communication.messaging.messengers import ServerMessenger, ClientMessenger, ServiceMessenger

address_server = {'frontend': 'tcp://127.0.0.1:5554', 'backend': 'tcp://127.0.0.1:5555',
                  'publisher': 'tcp://127.0.0.1:5600'}

addresses_for_service = {'server_frontend': 'tcp://127.0.0.1:5554', 'server_backend': 'tcp://127.0.0.1:5555',
                         'server_publisher': 'tcp://127.0.0.1:5556', 'publisher': 'tcp: // 127.0.0.1:5601'}

addresses_for_client = {'server_frontend': 'tcp://127.0.0.1:5554', 'server_backend': 'tcp://127.0.0.1:5555',
                        'server_publisher': 'tcp://127.0.0.1:5556', 'publisher': 'tcp: // 127.0.0.1:5602'}


@pytest.fixture
def my_server():
    app_folder = Path(__file__).resolve().parents[2]
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    server = dev.DeviceFactory.make_device(cls=dev.Server,
                                           name='Server',
                                           db_path=Path(app_folder / 'DB' / 'Devices.db'))
    return server


@pytest.fixture
def my_stpmtrservice():
    app_folder = Path(__file__).resolve().parents[2]
    sys.path.append(str(Path(__file__).resolve().parents[1]))

    path = Path(__file__).resolve()

    from devices.devices import Service
    from communication.logic.thinkers import StpMtrCtrlServiceCmdLogic

    service = dev.DeviceFactory.make_device(device_id='b8b10026214c373bffe2b2847a9538dd',
                                        db_path=Path(Path(app_folder) / 'DB' / 'Devices.db'))

    return service


@pytest.fixture
def server_messenger() -> ServerMessenger:
    return ServerMessenger(name='Server',
                           addresses=address_server,
                           parent=None,
                           pub_option=True)


@pytest.fixture
def service_messenger() -> ServiceMessenger:
    sm = ServiceMessenger(name='Service1',
                          addresses=addresses_for_service,
                          parent=None,
                          pub_option=True)
    sm.subscribe_sub(address=addresses_for_service['server_publisher'])
    return sm


@pytest.fixture
def client_messenger() -> ClientMessenger:
    cm = ClientMessenger(name='Client1',
                         addresses=addresses_for_client,
                         parent=None,
                         pub_option=True)
    cm.subscribe_sub(address=addresses_for_service['server_publisher'])
    return cm


@pytest.fixture
def standard_OrderedDict():
    ords = OrderedDict() # standard OrderedDict
    ords['first_added'] = 10
    ords['second_added'] = 20
    ords['last_added'] = 30
    return ords


@pytest.fixture
def form_test_msg():
    # Form message
    info = mes.Test()
    body = mes.MessageBody('info', 'TestSender', 'TestReceiver')
    data = mes.MessageData(com='test', info=info)
    return mes.Message(body, data)


@pytest.fixture
def all_messages_generation(my_server, form_test_msg):
    from devices.devices import Server
    server: Server = my_server
    commands = mu.commands
    msg_i = form_test_msg
    messages = []
    for com in commands:
        messages.append(mu.gen_msg(com, device=server, msg_i=msg_i, service_id='123'))
    return messages