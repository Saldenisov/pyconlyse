from pathlib import Path
from devices.service_devices.project_treatment import ProjectManager_controller
from devices.service_devices.project_treatment.openers import Opener, HamamatsuFileOpener
from utilities.myfunc import file_md5
from utilities.data.datastructures.mes_independent import CmdStruct
from utilities.data.datastructures.mes_independent.devices_dataclass import (FuncActivateInput, FuncActivateOutput,
                                                                             FuncPowerInput, FuncPowerOutput)
from utilities.data.datastructures.mes_independent.projects_dataclass import *

import logging
module_logger = logging.getLogger(__name__)

from tests.fixtures.services import projectmanager_default_non_fixture

import pytest

one_service = [projectmanager_default_non_fixture()]
all_services = [projectmanager_default_non_fixture()]
test_param = all_services

@pytest.mark.parametrize('project_manager', test_param)
def test_func_project_manager(project_manager: ProjectManager_controller):
    pm = project_manager
    # Test Data and Project folder paths
    assert isinstance(pm.data_path, Path)
    assert 'dev\\DATA' in str(pm.data_path)

    # Power TODO: to finilize
    res = pm.power(FuncPowerInput(True))
    assert pm.device_status.power
    # Activate TODO: to finilize
    res = pm.activate(FuncActivateInput(True))
    assert pm.device_status.active

    # Verify state of controller
    res: ProjectManagerControllerState = pm.state
    assert res.operators_len == 6
    assert res.files_len == 639
    assert res.projects_len == 3
    assert res.db_md5_sum == file_md5(pm.database_path)

    # Get Controller state
    res: FuncGetProjectManagerControllerStateOutput = pm.get_controller_state(FuncGetProjectManagerControllerStateInput())
    assert res.state.db_md5_sum == file_md5(pm.database_path)


    # Get Files
    res: FuncGetFilesOutput = pm.get_files(FuncGetFilesInput())
    assert isinstance(res, FuncGetFilesOutput)
    assert len(res.files) == 639

    res: FuncGetFilesOutput = pm.get_files(FuncGetFilesInput(author_email='daniel.adjei@universite-paris-saclay.fr'))
    assert len(res.files) == 1

    res: FuncGetFilesOutput = pm.get_files(FuncGetFilesInput(operator_email='daniel.adjei@universite-paris-saclay.fr'))
    assert len(res.files) == 82

    res: FuncGetFilesOutput = pm.get_files(FuncGetFilesInput(operator_email=
                                                             ['sergey.denisov@universite-paris-saclay.fr',
                                                              'daniel.adjei@universite-paris-saclay.fr']))
    assert len(res.files) == 421

    # Get Projects
    res: FuncGetProjectsOutput = pm.get_projects(FuncGetProjectsInput())
    assert isinstance(res, FuncGetProjectsOutput)
    assert len(res.projects_names) == 3

    res: FuncGetProjectsOutput = pm.get_projects(FuncGetProjectsInput(author_email=
                                                                      'sergey.denisov@universite-paris-saclay.fr'))
    assert len(res.projects_names) == 2

    res: FuncGetProjectsOutput = pm.get_projects(FuncGetProjectsInput(operator_email=
                                                                      ['sergey.denisov@universite-paris-saclay.fr',
                                                                       'daniel.adjei@universite-paris-saclay.fr']))
    assert len(res.projects_names) == 3

    # Get operators
    res: FuncGetOperatorsOutput = pm.get_operators(FuncGetOperatorsInput())
    assert isinstance(res, FuncGetOperatorsOutput)
    assert len(res.operators) == 6



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



