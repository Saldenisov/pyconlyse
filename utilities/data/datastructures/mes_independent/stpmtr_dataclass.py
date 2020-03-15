from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union
from utilities.data.datastructures.mes_independent.devices_dataclass import DeviceStatus, FuncInput, FuncOutput


@dataclass(frozen=False)
class AxisStpMtr:
    id: int
    name: str = ''
    limits: Tuple[Union[int, float]] = field(default_factory=tuple)
    position: float = ''
    preset_values: List[Union[int, float]] = field(default_factory=list)
    status: int = 0

    def short(self):
        return AxisStpMtrEssentials(id=self.id, position=self.position, status=self.status)


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

    def __post_init__(self):
        self.device_status = self.device.device_status
        super().__post_init__()


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


