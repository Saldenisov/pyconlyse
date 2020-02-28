from dataclasses import dataclass, field
from typing import List, Tuple, Union
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
