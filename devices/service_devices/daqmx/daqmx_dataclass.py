from devices.devices_dataclass import *
from weakref import ReferenceType
from nidaqmx.task import Task


@dataclass
class DAQmxTask:
    channel: str
    name: str
    type: str


@dataclass
class NIDAQmxTask:
    task: Task = None


@dataclass
class DAQmxCard(HardwareDevice):
    tasks: Dict[Union[int, str], DAQmxTask] = field(default_factory=dict)
    channel_settings: Dict[str, List[str]] = field(default_factory=dict)
    device_ref: ReferenceType = None

    def short(self):
        d = {}
        for key in DAQmxCardEssentials.__dataclass_fields__.keys():
            d[key] = getattr(self, key)
        return DAQmxCardEssentials(**d)


@dataclass
class NIDAQmxCard(DAQmxCard):
    pass


@dataclass
class DAQmxCardEssentials(DAQmxTask):
    pass


@dataclass
class DAQmxCardNIEssentials(DAQmxCardEssentials):
    pass


@dataclass
class FuncReadChannelInput(FuncInput):
    daqmx_id: int
    channel_id: int
    com: str = 'read_channel'


@dataclass
class FuncReadChannelOutput(FuncOutput):
    daqmx_id: int
    channel_id: int
    value: Union[int, float, bool]
    com: str = 'read_channel'


@dataclass
class FuncWriteChannelInput(FuncInput):
    daqmx_id: int
    channel_id: int
    value: Union[int, float, bool]
    com: str = 'write_channel'


@dataclass
class FuncWriteChannelOutput(FuncOutput):
    daqmx_id: int
    channel_id: int
    value: Union[int, float, bool]
    com: str = 'write_channel'


@dataclass
class FuncSetChannelTypeInput(FuncInput):
    daqmx_id: int
    channel_id: int
    channel_type: str
    com: str = 'set_channel_type'


@dataclass
class FuncSetChannelTypeOutput(FuncOutput):
    daqmx_id: int
    channel_id: int
    channel_type: str
    com: str = 'set_channel_type'
