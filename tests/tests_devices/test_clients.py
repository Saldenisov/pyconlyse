from devices.virtual_devices.clients import SuperUser


def test_superuser(superuser: SuperUser):
    assert superuser.device_status.active  # Power is always ON for client and it is active
    assert superuser.device_status.power
    superuser.start()
    assert superuser.device_status.active
    superuser.stop()


