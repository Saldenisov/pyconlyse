import pytest

from devices.service_devices.cameras import *
from tests.fixtures.services import *
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.camera_dataclass import *

one_service = []
#all_services = []
test_param = one_service


@pytest.mark.parametrize('cameractrl', test_param)
def test_func_stpmtr(cameractrl: CameraController):
    pass