import pytest


def test_import_testing():
    from communication.messaging.messengers import Messenger
    from communication.logic.thinkers_logic import Thinker
    from communication.logic.thinkers_logic import ServerCmdLogic
    from communication.messaging.messengers import ServerMessenger, ClientMessenger, ServiceMessenger
    from communication.logic.logic_functions import task_in_reaction, task_out_reaction, pending_demands
    from communication.messaging.messages import Message
    from devices.devices import Device
    import gui.controllers
    import gui.models
    import gui.views
    import datastructures.mes_dependent.general
    import datastructures.mes_dependent.dicts
    import datastructures.mes_independent.general
    import datastructures.mes_independent.devices_dataclass
    import datastructures.mes_independent.measurments_dataclass
    import datastructures.mes_independent.projects_dataclass
    import datastructures.mes_independent.stpmtr_dataclass
