from devices.virtualdevices.clients import SuperUser
from datastructures.mes_independent import CmdStruct


from tests.fixtures.clients import superuser


def test_superuser(superuser: SuperUser):
    superuser.start()

    assert superuser.device_status.active

    superuser.stop()


