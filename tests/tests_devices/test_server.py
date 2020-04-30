from devices.devices import Server
from utilities.data.messaging.messages import MsgComExt, Error
from utilities.data.datastructures.mes_independent import CmdStruct


from tests.fixtures.server import server


def test_server(server: Server):
    server.start()

    assert server.device_status.active
    server.pause()


    server.stop()



