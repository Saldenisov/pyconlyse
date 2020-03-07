from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from typing import Dict, List, Tuple, Union
from utilities.data.general import DataClass_frozen, DataClass_unfrozen
from communication.interfaces import MessengerInter, ThinkerInter
from devices.interfaces import DeciderInter, ExecutorInter


@dataclass
class DeviceStatus(DataClass_unfrozen):
    active: bool = False
    connected: bool = False
    messaging_on: bool = False
    messaging_paused: bool = False
    power: bool = False


@dataclass(frozen=True)
class DeviceParts(DataClass_frozen):
    messenger: MessengerInter
    thinker: ThinkerInter
    decider: DeciderInter
    executor: ExecutorInter


@dataclass(frozen=False)
class AxisStpMtr:
    id: int
    name: str = ''
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    position: float = ''
    preset_values: List[Union[int, float]] = field(default_factory=list)
    status: int = 0

    def short(self):
        return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.position)


@dataclass(order=True, frozen=False)
class AxisStpMtrEssentials:
    id: int
    position: float
    status: int


@dataclass(order=True, frozen=True)
class StpMtrDescription:
    axes: Dict[int, AxisStpMtr]
    info: str
    GUI_title: str


@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    axes: Dict[int, AxisStpMtrEssentials]
    device_status: DeviceStatus
    axes_previous: Dict[int, AxisStpMtrEssentials] = None
    device_status_previous: DeviceStatus = None
    start_stop: list = field(default_factory=list)


#Experimental Data structures
@dataclass
class Experiment:
    type: str  # Pulse-Probe, Pulse-Pump-Probe
    comments: str
    author: str
    date: datetime


@dataclass
class Map2D(Experiment):
    data: np.ndarray
    wavelengths: np.array
    timedelays: np.array
    time_scale: str


@dataclass
class StroboscopicPulseProbeRaw(Experiment):
    """
    raw key=timedelay
    [[Signal_0]
     [Reference_0]
     [Signal_electron_pulse]
     [Reference_electron]
     [Noise_signal]
     [Noise_reference]
     ...x n times
     ]
    """
    raw: Dict[float, np.ndarray]
    wavelength: np.array
    timedelays: np.array
    time_scale: str


#Function for devices
@dataclass
class FuncInput:

    def __post_init__(self):
        object.__setattr__(self, 'time_stamp', datetime.timestamp(datetime.now()))


@dataclass
class FuncOutput:
    func_success: bool
    comments: str

    def __post_init__(self):
        object.__setattr__(self, 'time_stamp', datetime.timestamp(datetime.now()))


@dataclass
class FuncActivateInput(FuncInput):
    flag: bool


@dataclass
class FuncActivateOutput(FuncOutput):
    device_status: DeviceStatus


@dataclass
class FuncActivateAxisInput(FuncInput):
    axis_id: int
    flag: bool


@dataclass
class FuncActivateAxisOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


@dataclass
class FuncGetStpMtrControllerStateInput(FuncInput):
    pass


@dataclass
class FuncGetStpMtrControllerStateOutput(FuncOutput):
    axes: Dict[int, AxisStpMtr]
    device_status: DeviceStatus


@dataclass
class FuncGetPosInput(FuncInput):
    pass


@dataclass
class FuncGetPosOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


@dataclass
class FuncMoveAxisToInput(FuncInput):
    axis_id: int
    pos: Union[int, float]
    how: str


@dataclass
class FuncMoveAxisToOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


@dataclass
class FuncStopAxisInput(FuncInput):
    axis_id: int


@dataclass
class FuncStopAxisOutput(FuncOutput):
    axes: Dict[int, AxisStpMtrEssentials]


@dataclass
class FuncPowerInput(FuncInput):
    device_id: str
    flag: bool


@dataclass
class FuncPowerOutput(FuncOutput):
    device_id: str
    device_status: DeviceStatus
