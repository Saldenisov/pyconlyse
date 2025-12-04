"""Configuration for the Treatment GUI.

This module centralises configuration related to the standalone Treatment GUI.
For now it only exposes the data folder used to browse and save files.

Default behaviour
-----------------
* If the environment variable ``TREATMENT_DATA_DIR`` is defined, its value is
  used as the data folder.
* Otherwise the default is the historical path ``E:\\`` used on the ELYSE
  acquisition machine.

The function ``get_data_folder()`` returns a :class:`pathlib.Path` instance
so callers can work with paths in a type-safe way.
"""

from __future__ import annotations

import os
from pathlib import Path

# Historical default on the main ELYSE machine
DEFAULT_DATA_FOLDER = Path("E:/")


def get_data_folder() -> Path:
    """Return the folder to use for Treatment data files.

    The logic is:
    1. If ``TREATMENT_DATA_DIR`` is set in the environment, use that.
    2. Otherwise return :data:`DEFAULT_DATA_FOLDER`.
    """

    override = os.getenv("TREATMENT_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return DEFAULT_DATA_FOLDER
