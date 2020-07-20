from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Tuple, Union, NewType, Set

from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription


@dataclass
class Analog_Controls:
    GainAuto: bool = False
    GainRaw: int = 0
    BlackLevelRaw: int = 0
    BalanceRatioRaw: int = 0


@dataclass
class ImageFormat:
    Pixel_Format: str = 'Mono8'  # Basic gray-scale


@dataclass
class AOI_Controls:
    Width: int = 0
    Height: int = 0
    OffsetX: int = 0
    OffsetY: int = 0


@dataclass(frozen=False)
class Camera:
    device_id: int
    name: str = ''
    friendly_name: str = ''
    parameters: Dict[str, Any] = field(default_factory=dict)

    def short(self):
        return CameraEssentials(device_id=self.device_id, name=self.name, friendly_name=self.friendly_name,
                                image_parameters=self.image_parameters)


@dataclass(order=True, frozen=False)
class CameraEssentials:
    device_id: int
    name: str = ''
    friendly_name: str = ''
    image_parameters: Dict[str, int] = field(default_factory=dict)  # {"X": size in pixels, "Y": ..., 'OffsetX':...}


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