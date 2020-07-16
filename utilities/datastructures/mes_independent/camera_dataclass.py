from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple, Union, NewType, Set

from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription


@dataclass(frozen=False)
class Camera:
    device_id: int
    name: str = ''
    friendly_name: str = ''


@dataclass(order=True, frozen=False)
class CameraEssentials:
    pass


@dataclass(order=True)
class CameraDescription(Desription):
    cameras: Dict[int, Camera]


@dataclass
class FuncActivateCameraInput(FuncInput):
    camera_id: int
    flag: bool
    com: str = 'activate_camera'


@dataclass
class FuncActivateCameraOutput(FuncOutput):
    cameras: Dict[int, CameraEssentials]
    com: str = 'activate_camera'


@dataclass
class FuncGetCameraControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetCameraControllerStateOutput(FuncGetControllerStateOutput):
    cameras: Dict[int, Camera] = None


@dataclass
class FuncGetImagesInput(FuncInput):
    camera_id: int
    n_images: int
    every_n_sec: int
    com: str = 'get_images'


@dataclass
class FuncGetImagesOutput(FuncOutput):
    image: Dict[int, list]  # Image is array converted to str, second field of List is timestamp
    com: str = 'get_images'


@dataclass(order=True, frozen=False)
class CamerasCtrlStatusMultiCameras:
    pass