from devices.virtualdevices.clients import SuperUser
from datastructures.mes_independent import CmdStruct


from tests.fixtures.clients import superuser_test as superuser


def test_superuser(superuser: SuperUser):
    assert superuser.device_status.active  # Power is always ON for client and it is active
    assert superuser.device_status.power
    superuser.start()
    assert superuser.device_status.active
    superuser.stop()


