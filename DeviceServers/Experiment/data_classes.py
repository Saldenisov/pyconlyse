from dataclasses import dataclass, field
from taurus import Device
from typing import List, Dict
from enum import Enum

class ExpType(Enum):
    PP = 1  # Pump-probe
    PPP1 = 2  # Simple 3P experiment
    STREAK = 3
    PPP2 = 4  # Complex 3P experiment


@dataclass
class TranslationStages:
    sc: Device = None
    samples: Device = None
    opa: Device = None


@dataclass
class SampleHolder:
    device: Device = None
    positions: List = field(default_factory=list)


@dataclass
class ExperimentalSettings:
    pp: int = 5
    oz: float = 0.0
    points: int = 20
    step: float = 2.0
    rz: float = 90.0
    delays: List[float] = field(default_factory=list)


@dataclass
class DetectionSettings:
    bg: int = 50000
    pulse_diff: float = 0.05
    detection_type: ExpType = ExpType.PP


@dataclass
class Settings:
    exp_settings: ExperimentalSettings = ExperimentalSettings()
    detection_settings: DetectionSettings = DetectionSettings()


@dataclass
class ProjectDescription:
    project_name: str
    holder_name: str
    holder_email: str
    description: str
    date_creation: str
    grant: str
    extra: Dict[str, str]


@dataclass
class Measurement:
    measurement_name: str
    exptype: ExpType
    project_name: str
    operator_id: int
    operator_email: str
    settings: str  # Dict[str, Any]
    data: bytearray
    raw_data: str # List[int] where values are timestamps
    time_delays: bytearray  # np.array
    wavelength: bytearray  # np.array
