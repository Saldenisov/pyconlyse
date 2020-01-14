from devices.devices import Server
from tests.tests_messaging.fixtures import my_server, my_stpmtrservice
from devices.devices import Service


def test_server(my_server):
    server: Server = my_server
    assert not server.device_status.power
    server.start()
    assert server.device_status.power
    assert server.device_status.active
    server.pause()
    assert server.device_status.messaging_paused
    server.unpause()
    assert not server.device_status.messaging_paused
    server.stop()
    assert not server.device_status.active


def test_stpmtrservice(my_stpmtrservice: Service):
    service: Service = my_stpmtrservice
    assert not service.device_status.power
    service.start()
    assert service.device_status.power
    assert service.device_status.active
    service.pause()
    assert service.device_status.messaging_paused
    service.unpause()
    assert not service.device_status.messaging_paused
    service.stop()
    assert not service.device_status.active
