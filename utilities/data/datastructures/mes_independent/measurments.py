from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from typing import Dict


#Experimental Data structures
@dataclass
class Measurement:
    type: str  # Pulse-Probe, Pulse-Pump-Probe
    comments: str
    author: str
    date: datetime


@dataclass
class Map2D(Measurement):
    data: np.ndarray
    wavelengths: np.array
    timedelays: np.array
    time_scale: str


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
    raw: Dict[float, np.ndarray]
    wavelength: np.array
    timedelays: np.array
    time_scale: str









