"""Compatibility exports for legacy GUI opener imports.

Implementations live in :mod:`utilities.dataio` so non-GUI consumers do not
need to import the desktop controller package.
"""

# Load legacy shim modules eagerly, then bind their classes back onto this
# package. This keeps ``from gui.controllers.openers import ASCIIOpener`` a
# class even after callers import the historical submodule path directly.
from .ASCIIOpener import ASCIIOpener
from .HamamatsuFileOpener import CriticalInfoHamamatsu, HamamatsuFileOpener
from .Opener import CriticalInfo, Opener

try:
    from .H5Opener import H5Opener
except (ModuleNotFoundError, ImportError, AttributeError):
    H5Opener = None

from utilities.dataio import OPENER_ACCRODANCE, OpenersTypes

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
