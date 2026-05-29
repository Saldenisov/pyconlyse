from enum import Enum

from .ASCIIOpener import *
from .HamamatsuFileOpener import *
from .Opener import *

try:
    from .H5Opener import H5Opener
    import h5py as _h5py

    if not hasattr(_h5py, "File"):
        H5Opener = None
except (ModuleNotFoundError, ImportError, AttributeError):
    H5Opener = None


class OpenersTypes(Enum):
    Hamamatsu = 'Hamamatsu'
    ASCII = 'ASCII'
    H5Opener = 'H5'


OPENER_ACCRODANCE = {
    '.his': OpenersTypes.Hamamatsu,
    '.img': OpenersTypes.Hamamatsu,
    '.dat': OpenersTypes.ASCII,
    '.raw': OpenersTypes.ASCII,
}

if H5Opener is not None:
    OPENER_ACCRODANCE['.h5'] = OpenersTypes.H5Opener
