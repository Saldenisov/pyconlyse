import pytest

from devices.service_devices.pdu import *
from tests.fixtures.services import *
from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.pdu_dataclass import *

one_service = [pdu_netio_test_non_fixture()]
#all_services = []
test_param = one_service


@pytest.mark.parametrize('pdu', test_param)
def test_func_stpmtr(pdu: PDUController):
    pdu.start()

    ACTIVATE = FuncActivateInput(flag=True)

    res: FuncActivateOutput = pdu.activate(ACTIVATE)

    pdu.stop()