from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from typing import Dict, Union


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









