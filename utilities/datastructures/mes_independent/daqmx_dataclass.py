from utilities.datastructures.mes_independent.devices_dataclass import *
from utilities.datastructures.mes_independent.general import FuncInput, FuncOutput


@dataclass
class DAQmxChannel:
    id: Union[int, str]
    name: str
    type: str


@dataclass
class DAQmxCard(HardwareDevice):
    channels: Dict[Union[int, str], DAQmxChannel] = field(default_factory=dict)
    authentication: Tuple[str] = field(default_factory=tuple)

    def short(self):
        d = {}
        for key in DAQmxCardEssentials.__dataclass_fields__.keys():
            d[key] = getattr(self, key)
        return DAQmxCardEssentials(**d)


@dataclass
class DAQmxCardEssentials:
    pass


@dataclass
class DAQmxCardNIEssentials(DAQmxCardEssentials):
    pass