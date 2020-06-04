from .HamamatsuFileOpener import *
from .ASCIIOpener import *
from .Opener import *

from enum import Enum


class OpenersTypes(Enum):
    Hamamatsu = 'Hamamatsu'
    ASCII = 'ASCII'

OPENER_ACCRODANCE = {'.his': OpenersTypes.Hamamatsu, '.img': OpenersTypes.Hamamatsu, '.dat': OpenersTypes.ASCII,
                     '.raw': OpenersTypes.ASCII}