

import pytest


def test_import_testing():
    from communication.messaging.messengers import Messenger
    from communication.logic.thinkers_logic import Thinker
    from communication.logic.thinkers_logic import ServerCmdLogic
    from communication.messaging.messengers import ServerMessenger
    from communication.logic.logic_functions import task_in_reaction, task_out_reaction, pending_demands
    from devices.soft.deciders import ServerDecider
    from devices.devices import Device
    from devices.soft.deciders import Decider
    from utilities.data.messages import Message

    import utilities.data.datastructures.mes_dependent
    import utilities.data.datastructures.mes_independent
