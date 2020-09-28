from copy import deepcopy
from devices.devices_dataclass import *
from weakref import ReferenceType
from nidaqmx.task import Task


@dataclass
class DAQmxTask:
    channel: str
    name: str
    task_type: str
    value: Any = None


@dataclass
class DAQmxTask_NI(DAQmxTask):
    task_ni: Task = None


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
class DAQmxCard_NI(DAQmxCard):

    def no_tasks(self):
        ignore = ['tasks']
        d = {}
        for key in DAQmxCard_NI.__dataclass_fields__.keys():
            if key not in ignore:
                d[key] = getattr(self, key)
            elif key == 'tasks':
                tasks = {}
                for task_id, task_NI in self.tasks.items():
                    c = {}
                    for key_in_task in DAQmxTask_NI.__dataclass_fields__.keys():
                        if key_in_task != 'task_ni':
                            c[key_in_task] = getattr(task_NI, key_in_task)
                    tasks[task_id] = DAQmxTask_NI(**c)
                d[key] = tasks
        return DAQmxCard_NI(**d)


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
