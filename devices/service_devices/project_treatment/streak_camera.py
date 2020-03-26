"""
08/03/2020 Sergey DENISOV

"""
from pathlib import Path
from typing import Dict, Any, Union, Tuple

from devices.service_devices.project_treatment.projectmanager import ProjectManager
from utilities.data.datastructures.mes_independent import FuncGetControllerStateInput, FuncGetControllerStateOutput
from utilities.data.datastructures.mes_independent.measurments_dataclass import Measurement


class ProjectManager_StreakCamera(ProjectManager):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _check_if_active(self) -> Tuple[bool, str]:
        pass

    def _check_if_connected(self) -> Tuple[bool, str]:
        pass

    def get_controller_state(self, func_input: FuncGetControllerStateInput) -> FuncGetControllerStateOutput:
        pass

    def open(self, measurement: Union[Path, Measurement]):
        pass

    def save(self, file_path: Path):
        pass

    def available_public_functions(self) -> Dict[str, Dict[str, Union[Any]]]:
        return super().available_public_functions()

    def description(self) -> Dict[str, Any]:
        return super().description()

    def activate(self, flag: bool):
        super().activate(flag)

