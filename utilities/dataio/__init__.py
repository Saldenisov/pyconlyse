"""Shared, GUI-independent experimental data readers."""

from enum import Enum

from .ascii_opener import ASCIIOpener
from .hamamatsu_file_opener import CriticalInfoHamamatsu, HamamatsuFileOpener
from .opener import CriticalInfo, Opener

try:
    from .h5_opener import H5Opener
    import h5py as _h5py

    if not hasattr(_h5py, "File"):
        H5Opener = None
except (ModuleNotFoundError, ImportError, AttributeError):
    H5Opener = None


class OpenersTypes(Enum):
    Hamamatsu = "Hamamatsu"
    ASCII = "ASCII"
    H5Opener = "H5"


OPENER_ACCRODANCE = {
    ".his": OpenersTypes.Hamamatsu,
    ".img": OpenersTypes.Hamamatsu,
    ".dat": OpenersTypes.ASCII,
    ".raw": OpenersTypes.ASCII,
}

if H5Opener is not None:
    OPENER_ACCRODANCE[".h5"] = OpenersTypes.H5Opener


__all__ = [
    "ASCIIOpener",
    "CriticalInfo",
    "CriticalInfoHamamatsu",
    "H5Opener",
    "HamamatsuFileOpener",
    "OPENER_ACCRODANCE",
    "Opener",
    "OpenersTypes",
]
