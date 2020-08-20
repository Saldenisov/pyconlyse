from dataclasses import dataclass, field
from typing import Any, Dict, List, Union
from pypylon import pylon
from utilities.datastructures.mes_independent.devices_dataclass import (DeviceStatus, FuncGetControllerStateInput,
                                                                        FuncGetControllerStateOutput)
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput, Desription


@dataclass
class Analog_Controls:
    GainAuto: str = 'Off'
    GainRaw: int = 0
    BlackLevelRaw: int = 0
    BalanceRatioRaw: int = 0


@dataclass
class AOI_Controls:
    Width: int = 0
    Height: int = 0
    OffsetX: int = 0
    OffsetY: int = 0


@dataclass
class Acquisition_Controls:
    TriggerSource: str = 'Line1'
    TriggerMode: str = 'Off'
    TriggerDelayAbs: int = 0
    ExposureTimeAbs: int = 100
    AcquisitionFrameRateAbs: int = 1
    AcquisitionFrameRateEnable: bool = True


@dataclass
class Image_Format_Control:
    PixelFormat: str = 'Mono8'  # Basic gray-scale


@dataclass
class Transport_Layer:
    GevSCPSPacketSize: int = 1500
    GevSCPD: int = 1000


@dataclass(frozen=False)
class Camera:
    device_id: int
    name: str = ''
    friendly_name: str = ''
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: int = 0  # 0, 1, 2

    def short(self):
        d = {}
        for key in CameraEssentials.__dataclass_fields__.keys():
            d[key] = getattr(self, key)
        return CameraEssentials(**d)


@dataclass(frozen=False)
class CameraBasler(Camera):
    pylon_camera: pylon.InstantCamera = None
    converter: pylon.ImageFormatConverter = None

    def no_pylon(self):
        d = {}
        for key in CameraBasler.__dataclass_fields__.keys():
            if key not in ['pylon_camera', 'converter']:
                d[key] = getattr(self, key)
        return CameraBasler(**d)


@dataclass(order=True, frozen=False)
class CameraEssentials:
    device_id: int
    name: str = ''
    friendly_name: str = ''
    parameters: Dict[str, int] = field(default_factory=dict)  # {"X": size in pixels, "Y": ..., 'OffsetX':...}
    status: int = 0


@dataclass(order=True)
class CameraDescription(Desription):
    cameras: Dict[int, Camera]


@dataclass
class FuncActivateCameraInput(FuncInput):
    camera_id: int
    flag: int
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
    every_n_sec: float
    demander_device_id: str
    com: str = 'get_images'

@dataclass
class FuncGetImagesPrepared(FuncOutput):
    camera_id: int
    ready: bool
    camera: CameraEssentials
    com: str = 'get_images_prepared'

@dataclass
class FuncGetImagesOutput(FuncOutput):
    image: List[int]
    timestamp: float
    description: str = ''
    com: str = 'get_images'
    crypted: bool = False


@dataclass
class FuncSetImageParametersInput(FuncInput):
    camera_id: int
    width: int
    height: int
    offset_x: int
    offset_y: int
    gain_mode: str
    gain: int
    blacklevel: int
    balance_ratio: int
    pixel_format: str
    com: str = 'set_image_parameters'


@dataclass
class FuncSetImageParametersOutput(FuncOutput):
    camera_id: int
    camera: CameraEssentials
    com: str = 'set_image_parameters'



@dataclass
class FuncSetSyncParametersInput(FuncInput):
    camera_id: int
    exposure_time: float
    trigger_mode: bool
    trigger_delay: float
    frame_rate: int = 1
    trigger_source: str = 'Line1'
    com: str = 'set_sync_parameters'


@dataclass
class FuncSetSyncParametersOutput(FuncOutput):
    camera_id: int
    camera: CameraEssentials
    com: str = 'set_sync_parameters'


@dataclass
class FuncSetTransportParametersInput(FuncInput):
    camera_id: int
    packet_size: int
    inter_packet_delay: int
    com: str = 'set_transport_parameters'


@dataclass
class FuncSetTransportParametersOutput(FuncOutput):
    camera_id: int
    camera: CameraEssentials
    com: str = 'set_transport_parameters'


@dataclass
class FuncStopAcquisitionInput(FuncInput):
    camera_id: int
    com: str = 'stop_acquisition'


@dataclass
class FuncStopAcquisitionOutput(FuncOutput):
    camera_id: int
    com: str = 'stop_acquisition'


@dataclass(order=True, frozen=False)
class CamerasCtrlStatusMultiCameras:
    cameras: Dict[int, Camera]
    device_status: DeviceStatus
    cameras_previous: Dict[int, Camera] = None
    device_status_previous: DeviceStatus = None

    def __post_init__(self):
        if not self.cameras_previous:
            self.cameras_previous = self.cameras
        if not self.device_status_previous:
            self.device_status_previous = self.device_status