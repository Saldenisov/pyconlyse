from enum import Enum

from .ASCIIOpener import *
from .HamamatsuFileOpener import *
from .H5Opener import H5Opener
from .Opener import *


class OpenersTypes(Enum):
    Hamamatsu = 'Hamamatsu'
    ASCII = 'ASCII'
    H5Opener = 'H5'


OPENER_ACCRODANCE = {'.his': OpenersTypes.Hamamatsu, '.img': OpenersTypes.Hamamatsu, '.dat': OpenersTypes.ASCII,
                     '.raw': OpenersTypes.ASCII, '.h5': OpenersTypes.H5Opener}