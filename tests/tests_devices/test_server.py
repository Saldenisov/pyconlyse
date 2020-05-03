from devices.devices import Server
from communication.messaging.messages import MsgComExt
from datastructures.mes_independent import CmdStruct


from tests.fixtures import server


def test_server(server: Server):
    server.start()
    assert server.device_status.active
    server.pause()
    server.stop()



