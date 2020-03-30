from pathlib import Path
from devices.service_devices.project_treatment import ProjectManager
from utilities.data.datastructures.mes_independent import CmdStruct
from utilities.data.datastructures.mes_independent.devices_dataclass import (FuncActivateInput, FuncActivateOutput,
                                                                             FuncPowerInput, FuncPowerOutput)


from tests.fixtures.services import projectmanager_non_fixture

import pytest

one_service = [projectmanager_non_fixture()]
all_services = [projectmanager_non_fixture()]
test_param = all_services

@pytest.mark.parametrize('project_manager', test_param)
def test_func_stpmtr(project_manager: ProjectManager):
    pm = project_manager
    # Test Data and Project folder paths
    assert isinstance(pm.projects_path, Path)
    assert isinstance(pm.data_path, Path)
    assert 'dev\\Projects' in str(pm.projects_path)
    assert 'dev\\DATA' in str(pm.data_path)

    # Power TODO: to finilize
    res = pm.power(FuncPowerInput(True))
    assert pm.device_status.power
    # Activate TODO: to finilize
    res = pm.activate(FuncActivateInput(True))
    assert pm.device_status.active

