from dataclasses import dataclass, field
from utilities.data.general import DataClass_frozen, DataClass_unfrozen
from communication.interfaces import MessengerInter, ThinkerInter
from devices.interfaces import DeciderInter, ExecutorInter
from devices.interfaces import DeviceInter



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
class FuncErrorOutput:
    comments: str
    func_success: bool = False


@dataclass
class FuncInput:
    pass

@dataclass
class FuncOutput:
    comments: str
    func_success: bool


@dataclass
class FuncActivateInput(FuncInput):
    flag: bool


@dataclass
class FuncActivateOutput(FuncOutput):
    device_status: DeviceStatus


@dataclass
class FuncGetControllerStateInput(FuncInput):
    pass


@dataclass
class FuncGetControllerStateOutput(FuncOutput):
    device_status: DeviceStatus


@dataclass
class FuncPowerInput(FuncInput):
    flag: bool


@dataclass
class FuncPowerOutput(FuncOutput):
    device_status: DeviceStatus
