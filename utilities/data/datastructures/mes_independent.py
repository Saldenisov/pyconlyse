from dataclasses import dataclass
from utilities.data.general import DataClass_frozen, DataClass_unfrozen
from communication.interfaces import MessengerInter, ThinkerInter
from devices.interfaces import DeciderInter, ExecutorInter



@dataclass
class DeviceStatus(DataClass_unfrozen):
    on: bool
    active: bool
    paused: bool


@dataclass(frozen=True)
class DeviceParts(DataClass_frozen):
    messenger: MessengerInter
    thinker: ThinkerInter
    decider: DeciderInter
    executor: ExecutorInter
