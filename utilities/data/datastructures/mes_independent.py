from dataclasses import dataclass, field
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


@dataclass(order=True, frozen=False)
class AxisStpMtr:
    name: str = ''
    position: float = ''
    status: int = 0
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    preset_values: List[Union[int, float]] = field(default_factory=list)


@dataclass(order=True, frozen=True)
class StpMtrDescription:
    axes: Dict[int, AxisStpMtr]
    info: str
    GUI_title: str


@dataclass(order=True, frozen=False)
class StpMtrCtrlStatusMultiAxes:
    axes: Dict[int, AxisStpMtr]
    device_status: DeviceStatus
    start_stop: list = field(default_factory=list)


@dataclass(order=True, frozen=False)
class FuncActivateOutput:
    flag: bool
    func_res: bool
    comments: str


@dataclass(order=True, frozen=False)
class FuncActivateAxisOutput:
    axis_id: int
    flag: Union[bool, None]
    func_res: bool
    comments: str


@dataclass(order=True, frozen=False)
class FuncGetPosOutput:
    axis_id: int
    pos: Union[int, float]
    func_res: bool
    comments: str


@dataclass(order=True, frozen=False)
class FuncMoveAxisToOutput:
    axis_id: int
    pos: Union[int, float]
    how: str
    func_res: bool
    comments: str


@dataclass(order=True, frozen=False)
class FuncStopAxisOutput:
    axis_id: int
    func_res: bool
    comments: str


@dataclass(order=True, frozen=False)
class FuncGetStpMtrControllerStateOutput:
    device_status: DeviceStatus
    axes: Dict[int, AxisStpMtr]
    func_res: bool
    comments: str


@dataclass(order=True, frozen=False)
class FuncPowerOutput:
    device_id: str
    flag: bool
    func_res: bool
    comments: str
