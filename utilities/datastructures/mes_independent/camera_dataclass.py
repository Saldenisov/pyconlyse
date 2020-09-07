from threading import Thread
from typing import Union

from pypylon import pylon

from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput


@dataclass
class Controls:
    pass


@dataclass
class Analog_Controls(Controls):
    GainAuto: str = 'Off'
    GainRaw: int = 0
    BlackLevelRaw: int = 0
    BalanceRatioRaw: int = 0


@dataclass
class AOI_Controls(Controls):
    Width: int = 0
    Height: int = 0
    OffsetX: int = 0
    OffsetY: int = 0


@dataclass
class Acquisition_Controls(Controls):
    TriggerSource: str = 'Line1'
    TriggerMode: str = 'Off'
    TriggerDelayAbs: int = 0
    ExposureTimeAbs: int = 100
    AcquisitionFrameRateAbs: int = 1
    AcquisitionFrameRateEnable: bool = True


@dataclass
class Image_Format_Control(Controls):
    PixelFormat: str = 'Mono8'  # Basic gray-scale


@dataclass
class Transport_Layer(Controls):
    GevSCPSPacketSize: int = 1500
    GevSCPD: int = 1000


@dataclass(frozen=False)
class Camera(HardwareDevice):
    matrix_size: Tuple[int] = field(default_factory=tuple)
    parameters: Dict[str, Controls] = field(default_factory=dict)
    stpmtr_ctrl_id: str = ''

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
    parameters: Dict[str, Controls] = field(default_factory=dict)  # {"X": size in pixels, "Y": ..., 'OffsetX':...}
    status: int = 0


@dataclass
class ImageDemand:
    camera_id: int
    demander_id: str
    every_n_sec: int
    return_images: bool
    post_treatment: str
    treatment_param: dict
    history_post_treatment_n: int
    grabbing_thread: Thread = None


@dataclass
class FuncGetCameraControllerStateInput(FuncGetControllerStateInput):
    pass


@dataclass
class FuncGetCameraControllerStateOutput(FuncGetControllerStateOutput):
    cameras: Dict[int, Camera] = None


@dataclass
class FuncGetImagesInput(FuncInput):
    camera_id: int
    demander_device_id: str
    every_n_sec: float
    return_images: bool
    post_treatment: str
    treatment_param: dict
    history_post_treatment_n: int
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
    post_treatment_points: List[Tuple[int]]
    timestamp: float
    camera_id: int
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
class FuncStartTrackingInput(FuncInput):
    camera_id: int
    history_points: int
    tracking_type: str = 'center_gravity'  # Extend later number of tracking types
    com: str = 'start_tracking'


@dataclass
class FuncStartTrackingPrepared(FuncOutput):
    camera_id: int
    ready: bool
    camera: CameraEssentials
    com: str = 'start_tracking_prepared'


@dataclass
class FuncStartTrackingOutput(FuncOutput):
    camera_id: int
    points: List[Tuple[int]]
    history_points: List[Tuple[int]]
    tracking_type: str = 'center_gravity'  # Extend later number of tracking types
    com: str = 'start_tracking'


@dataclass
class FuncStopAcquisitionInput(FuncInput):
    camera_id: int
    com: str = 'stop_acquisition'


@dataclass
class FuncStopAcquisitionOutput(FuncOutput):
    camera_id: int
    com: str = 'stop_acquisition'


@dataclass(order=True, frozen=False)
class CtrlStatusMultiCameras:
    cameras: Dict[int, Union[Camera, CameraEssentials]]
    device_status: DeviceStatus
    cameras_previous: Dict[int, Camera] = None
    device_status_previous: DeviceStatus = None

    def __post_init__(self):
        if not self.cameras_previous:
            self.cameras_previous = self.cameras
        if not self.device_status_previous:
            self.device_status_previous = self.device_status
