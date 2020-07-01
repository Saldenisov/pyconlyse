from enum import Enum

from .ASCIIOpener import *
from .HamamatsuFileOpener import *
from .Opener import *


class OpenersTypes(Enum):
    Hamamatsu = 'Hamamatsu'
    ASCII = 'ASCII'

OPENER_ACCRODANCE = {'.his': OpenersTypes.Hamamatsu, '.img': OpenersTypes.Hamamatsu, '.dat': OpenersTypes.ASCII,
                     '.raw': OpenersTypes.ASCII}