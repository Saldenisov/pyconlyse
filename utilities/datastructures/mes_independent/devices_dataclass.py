from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Union

from communication.interfaces import MessengerInter, ThinkerInter
from communication.messaging.message_types import AccessLevel, Permission
from devices.interfaces import DeviceType, DeviceId
from devices.interfaces import ExecutorInter
from utilities.datastructures import DataClass_frozen, DataClass_unfrozen
from utilities.datastructures.mes_independent.general import *


@dataclass(frozen=True)
class DeviceParts(DataClass_frozen):
    messenger: MessengerInter
    thinker: ThinkerInter
    executor: ExecutorInter


@dataclass
class HardwareDevice:
    device_id: int
    name: str = ''
    friendly_name: str = ''
    status: int = 0  # 0, 1, 2


class HardwareDeviceDict(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device_id = {}

    def __setitem__(self, key_id, device: HardwareDevice):
        device_id = device.device_id
        if device_id not in self.device_id:
            super().__setitem__(key_id, device)
            self.device_id[device_id] = key_id
        else:
            raise KeyError(f'Hardware Device id: {device_id} already exists in {self.device_id}')

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            if key in self.device_id:
                return super().__getitem__(self.device_id[key])
            else:
                raise KeyError('Neither device_id nor device_seq_id are present in the dictionary.')

    def __delitem__(self, key):
        try:
            device: HardwareDevice = self[key]
            device_id = device.device_id
            super().__delitem__(key)
            del self.device_id[device_id]
        except KeyError:
            device_id = key
            if device_id in self.device_id:
                key = self.device_id[device_id]
                del self.device_id[device_id]
                super().__delitem__(key)
            else:
                raise KeyError(f'Key {key} is not present in the dictionary.')

    def __contains__(self, item):
        if super().__contains__(item):
            return True
        else:
            if item in self.device_id:
                return super().__contains__(self.device_id[item])


@dataclass
class DeviceStatus(DataClass_unfrozen):
    active: bool = False
    connected: bool = False
    messaging_on: bool = False
    messaging_paused: bool = False
    power: bool = False


@dataclass(frozen=True, order=True)
class AvailableServices:
    available_services: Dict[DeviceId, str]


@dataclass(frozen=True, order=True)
class DoIt:
    com: str
    input: FuncInput


@dataclass(frozen=True, order=True)
class DoneIt:
    com: str
    result: FuncOutput


@dataclass(order=True)
class Description:
    info: str
    GUI_title: str


@dataclass(order=True)
class ServiceDescription(Description):
    hardware_devices: HardwareDevice
    class_name: str


@dataclass(order=True)
class ServerDescription(Description):
    pass


@dataclass(order=True)
class ClientDescription:
    pass


@dataclass
class HeartBeat:
    device_id: str
    event_n: float
    event_id: str


@dataclass
class HeartBeatFull:
    device_id: str
    device_name: str
    device_type: DeviceType
    device_public_key: bytes
    device_public_sockets: Dict[str, str]
    event_id: str
    event_name: str
    event_n: int
    event_tick: float


@dataclass(order=True)
class WelcomeInfoDevice:
    """
    Must be remembered that WelcomeInfoDevice.device_public_key must be crypted with Server public key and will be
    decrypted on Server side by Server private key, a only after that session_key will be created and used between
    Server and Device communication.
    """
    device_id: str
    device_name: str
    device_type: DeviceType
    device_public_key: bytes
    device_public_sockets: Dict[str, str]
    event_id: str
    event_name: str
    event_tick: float
    password_checksum: bytes = b''


@dataclass(order=True)
class WelcomeInfoServer:
    """
    Must be remembered that WelcomeInfoServer must be crypted with Device public key and will be decrypted on
    Device side by Device private key, a only after that session_key will be used in communication between
    Server and Device.
    """
    password_checksum: bytes = b''
    session_key: bytes = b''


@dataclass(frozen=True, order=True)
class DeviceInfoInt:
    active_connections: List[Tuple[DeviceId, DeviceType]]  # [(receiver_id, DeviceType), ...]
    available_public_functions: List[CmdStruct]
    device_id: str
    device_status: DeviceStatus
    device_description: Description
    events_running: List[str]  # event names


@dataclass(frozen=True, order=True)
class DeviceInfoExt:
    #available_public_functions: List[CmdStruct]
    device_id: str
    device_description: Union[ServiceDescription, ClientDescription, ServerDescription]
    device_status: DeviceStatus


@dataclass(frozen=True, order=True)
class ServerInfoQueKeysMes:
    queue_in_keys: deque = field(default_factory=deque)
    queue_out_keys: deque = field(default_factory=deque)
    queue_in_pending_keys: deque = field(default_factory=deque)


@dataclass(frozen=True, order=True)
class ShutDown:
    device_id: str
    reason: str = ""


@dataclass(frozen=True, order=True)
class MsgError:
    comments: str = ''


@dataclass
class FuncActivateInput(FuncInput):
    flag: bool
    com: str = 'activate'


@dataclass
class FuncActivateOutput(FuncOutput):
    device_status: DeviceStatus
    com: str = 'activate'


@dataclass
class FuncAliveInput(FuncInput):
    com: str = 'are_you_alive'


@dataclass
class FuncAliveOutput(FuncOutput):
    device_id: str
    event_n: float
    event_id: str
    com: str = 'are_you_alive'


@dataclass
class FuncAvailableServicesInput(FuncInput):
    com: str = 'get_available_services'


@dataclass
class FuncAvailableServicesOutput(FuncOutput):
    device_id: DeviceId
    device_available_services: Dict[DeviceId, str]
    com: str = 'get_available_services'


@dataclass
class FuncGetControllerStateInput(FuncInput):
    com: str = 'get_controller_state'


@dataclass
class FuncGetControllerStateOutput(FuncOutput):
    device_status: DeviceStatus
    com: str = 'get_controller_state'


@dataclass
class FuncPowerInput(FuncInput):
    flag: bool
    com: str = 'power'


@dataclass
class FuncPowerOutput(FuncOutput):
    device_status: DeviceStatus
    com: str = 'power'


@dataclass
class FuncServiceInfoInput(FuncInput):
    com: str = 'service_info'


@dataclass
class FuncServiceInfoOutput(FuncOutput):
    device_id: DeviceId
    service_info: DeviceInfoExt
    com: str = 'service_info'


@dataclass(order=True)
class Connection(DataClass_unfrozen):
    device_id: str
    device_name: str
    device_type: DeviceType
    device_public_key: bytes
    device_public_sockets: Dict[str, str]
    event_id: str
    event_name: str
    event_tick: float
    access_level: AccessLevel = AccessLevel.NONE
    session_key: bytes = b''
    permission: Permission = Permission.DENIED
    password_checksum: bytes = b''
