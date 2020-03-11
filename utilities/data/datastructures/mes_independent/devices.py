from dataclasses import dataclass
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


from datetime import datetime


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
class FuncPowerInput(FuncInput):
    device_id: str
    flag: bool


@dataclass
class FuncPowerOutput(FuncOutput):
    device_id: str
    device_status: DeviceStatus
