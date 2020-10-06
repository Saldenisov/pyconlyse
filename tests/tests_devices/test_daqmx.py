from devices.service_devices.daqmx import DAQmxController
from tests.fixtures.services import *
from devices.datastruct_for_messaging import *
from devices.service_devices.daqmx.datastruct_for_messaging import *
from time import sleep
from typing import Dict
from .general_test import *
one_service = [daqmx_ni_test_non_fixture()]
#all_services = []
test_param = one_service


@pytest.mark.parametrize('daqmx', test_param)
def test_func_stpmtr(daqmx: DAQmxController):
    daqmx.start()
    power_on(daqmx)
    activate(daqmx)
    power_off(daqmx, success_expected=False)
    sleep(1)
    assert daqmx._hardware_devices['TRANCON-DAQ'].tasks[11].value > 0
    deactivate(daqmx)
    power_off(daqmx)
    daqmx.stop()
