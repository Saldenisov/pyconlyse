"""Compatibility import for the shared Hamamatsu data opener."""

from utilities.dataio.hamamatsu_file_opener import (
    CriticalInfoHamamatsu,
    HamamatsuFileOpener,
)

__all__ = ["CriticalInfoHamamatsu", "HamamatsuFileOpener"]
