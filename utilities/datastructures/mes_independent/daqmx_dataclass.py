from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput
from weakref import ref, ReferenceType


@dataclass
class DAQmxTask:
    channel: str
    name: str
    type: str


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