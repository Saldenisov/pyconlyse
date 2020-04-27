from devices.devices import Server
from utilities.data.messaging.messages import MsgCommon, Error
from utilities.data.datastructures.mes_independent import CmdStruct


from tests.fixtures.server import server


def test_server(server: Server):
    server.start()

    assert server.device_status.active
    server.pause()
    #Msg generation testing
    msg = server.generate_msg(msg_com=MsgCommon.AVAILABLE_SERVICES, parameters={})
    msg = server.generate_msg(msg_com=MsgCommon.ERROR, parameters={'error': Error('Yes')})

    server.stop()



