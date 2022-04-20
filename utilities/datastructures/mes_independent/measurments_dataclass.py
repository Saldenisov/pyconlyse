from dataclasses import dataclass
from typing import Tuple, Union

import numpy
import numpy as np


# Tango


@dataclass
class Scalar:
    value: float
    dtype: str

@dataclass
class Array:
    value: bytes
    shape: tuple
    dtype: str


@dataclass
class ArchiveData:
    tango_device: str  # Tango Device name
    data_timestamp: float
    dataset_name: str
    data: Union[Scalar, Array]


@dataclass
class DataXY:
    name: str
    X: numpy.ndarray
    Y: numpy.ndarray


@dataclass
class DataXYb:
    name: str
    X: b''
    Y: b''
    Xdtype: str
    Ydtype: str



# Cursors
@dataclass
class Cursors2D:
    x1: Tuple[int, float] = (0, 0)
    x2: Tuple[int, float] = (0, 0)
    y1: Tuple[int, float] = (0, 0)
    y2: Tuple[int, float] = (0, 0)


#Experimental Data structures
@dataclass
class Measurement:
    """
    General measurement class
    """
    type: str  # Pulse-Probe, Pulse-Pump-Probe
    comments: str
    author: str
    timestamp: float
    data: np.ndarray
    wavelengths: np.array
    timedelays: np.array
    time_scale: str


@dataclass
class Hamamatsu(Measurement):
    pass


@dataclass
class HamamatsuIMG(Hamamatsu):
    pass


@dataclass
class HamamatsuHIS(Hamamatsu):
    n_maps: int


@dataclass
class StroboscopicPulseProbeRaw(Measurement):
    """
    raw key=timedelay
    [[Signal_0]
     [Reference_0]
     [Signal_electron_pulse]
     [Reference_electron]
     [Noise_signal]
     [Noise_reference]
     ...x n times
     ]
    """
    pass


#CameraReadings
@dataclass
class CameraReadings:
    data: np.ndarray
    time_stamp: float
    description: str
    X: np.array = None
    Y: np.array = None

    def __post_init__(self):
        if not self.X:
            self.X = np.arange(self.data.shape[1])
        if not self.Y:
            self.Y = np.arange(self.data.shape[0])
