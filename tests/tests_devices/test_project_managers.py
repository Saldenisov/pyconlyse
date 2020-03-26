from devices.service_devices.project_treatment import ProjectManager, ProjectManager_StreakCamera
from utilities.data.datastructures.mes_independent import CmdStruct
from utilities.data.datastructures.mes_independent.devices_dataclass import (FuncActivateInput, FuncActivateOutput,
                                                                             FuncPowerInput, FuncPowerOutput)


from tests.fixtures.services import projectmanager_streakcamera_non_fixture

import pytest

one_service = [projectmanager_streakcamera_non_fixture()]
all_services = [projectmanager_streakcamera_non_fixture()]
test_param = all_services

@pytest.mark.parametrize('project_manager', test_param)
def test_func_stpmtr(project_manager: ProjectManager):
    pm = project_manager
    # Power TODO: to finilize
    res = pm.power(FuncPowerInput(True))
    assert pm.device_status.power
    # Activate TODO: to finilize
    res = pm.activate(FuncActivateInput(True))
    assert pm.device_status.active

