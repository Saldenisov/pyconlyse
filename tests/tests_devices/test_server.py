from devices.devices import Server


def test_server(server: Server):
    server.start()
    assert server.device_status.active
    server.pause()
    server.stop()



