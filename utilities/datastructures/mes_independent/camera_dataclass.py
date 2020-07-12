from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Union, NewType, Set

from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription


@dataclass(frozen=False)
class Camera:
    pass

@dataclass(order=True, frozen=False)
class CameraEssentials:
    pass

@dataclass
class FuncActivateCameraInput(FuncInput):
    camera_id: int
    flag: bool
    com: str = 'activate_camera'


@dataclass
class FuncActivateCameraOutput(FuncOutput):
    cameras: Dict[int, CameraEssentials]
    com: str = 'activate_camera'