from time import sleep
from collections import OrderedDict as od
from communication.messaging.messengers import *
from communication.messaging.message_utils import MsgGenerator
from devices.devices import Server, Service
from devices.virtualdevices.clients import SuperUser
from devices.service_devices.stepmotors.stpmtr_emulate import StpMtrCtrl_emulate
from tests.fixtures import *
from tests.tests_messaging.auxil import clean_test_queues, start_devices, stop_devices
from communication.messaging.messages import MessageExt
from datastructures.mes_independent.devices_dataclass import *
from datastructures.mes_independent.stpmtr_dataclass import *

import pytest


devices = [server_test_non_fixture(), stpmtr_emulate_test_non_fixture()]


@pytest.mark.messengers
@pytest.mark.parametrize('device', devices)
def test_messenger_basics(device: Device):
    """
    Test function designed to test functionality of 3 types of messengers: Client, Service and Server
    Thinker operation will be paused, only messenger will be active in some stages of the test
    """
    # get messenger of the device
    messenger: Messenger = device.messenger
    assert not messenger.active
    assert messenger.paused
    messenger.start()
    assert messenger.active
    assert not messenger.paused

    messenger.pause()
    assert messenger.active
    assert messenger.paused

    messenger.unpause()
    assert messenger.active
    assert not messenger.paused

    assert messenger.id == device.id

    if device.type is DeviceType.SERVER:
        assert PUB_Socket_Server in messenger.public_sockets
        assert PUB_Socket_Server in messenger.addresses
        assert FRONTEND_Server in messenger.public_sockets
        assert FRONTEND_Server in messenger.public_sockets
        assert BACKEND_Server in messenger.addresses
        assert BACKEND_Server in messenger.addresses

    else:
        assert PUB_Socket in messenger.public_sockets
        assert PUB_Socket in messenger.addresses
        assert PUB_Socket_Server in messenger.addresses

    messenger.stop()
    assert not messenger.active
    assert messenger.paused