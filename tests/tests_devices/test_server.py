from devices.devices import Server


from tests.fixtures import server_test as server


def test_server(server: Server):
    server.start()
    assert server.device_status.active
    server.pause()
    server.stop()



