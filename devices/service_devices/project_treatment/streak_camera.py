"""
08/03/2020 Sergey DENISOV

"""
from pathlib import Path
from typing import Dict, Any, Union

from devices.service_devices.project_treatment.project_controller import ProjectController
from utilities.data.datastructures.mes_independent.measurments import Measurement


class Project_StreakCamera(ProjectController):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

