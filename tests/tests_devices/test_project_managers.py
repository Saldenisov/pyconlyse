from pathlib import Path
from devices.service_devices.project_treatment import ProjectManager_controller
from devices.service_devices.project_treatment.openers import Opener, HamamatsuFileOpener
from utilities.data.datastructures.mes_independent import CmdStruct
from utilities.data.datastructures.mes_independent.devices_dataclass import (FuncActivateInput, FuncActivateOutput,
                                                                             FuncPowerInput, FuncPowerOutput)
from utilities.data.datastructures.mes_independent.projects_dataclass import (FuncReadFileTreeInput,
                                                                              FuncReadFileTreeOutput)

import logging
module_logger = logging.getLogger(__name__)

from tests.fixtures.services import projectmanager_non_fixture

import pytest

one_service = [projectmanager_non_fixture()]
all_services = [projectmanager_non_fixture()]
test_param = all_services

@pytest.mark.parametrize('project_manager', test_param)
def test_func_project_manager(project_manager: ProjectManager_controller):
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

    res = pm.get_file_tree(func_input=FuncReadFileTreeInput)
    assert isinstance(res, FuncReadFileTreeOutput)
    assert len(res.files) == 629
    print(res.file_tree)

@pytest.mark.openers
@pytest.mark.parametrize('opener', [HamamatsuFileOpener()])
def test_opener(opener: Opener):
    files = [Path("C:\\dev\\pyconlyse\\prev_projects\\DATAFIT\\test.img"),
             Path('C:\\dev\\DATA\\M1043.his'),
             Path('C:\\dev\\DATA\\B1043.his')]

    for file in files:
        opener.fill_critical_info(file)
        assert file in opener.paths
        map = opener.read_map(file)
        assert map
        map = opener.read_map(file, map_index=10)
        assert map
        measurement_counter = 0
        for measurement in opener.give_all_maps(file):
            measurement_counter += 1
        print(measurement_counter)



