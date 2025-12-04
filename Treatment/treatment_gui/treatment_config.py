"""Configuration for the forked Treatment GUI.

Copied from ``gui.treatment_config`` so that Treatment-specific
behaviour can evolve independently from the legacy GUI code.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _load_config() -> dict[str, Any]:
    """Load Treatment config from ``Treatment/config.json`` if it exists.

    The config file is expected to live next to ``main.py``::

        Treatment/
          main.py
          config.json

    Returns an empty dict if the file is missing or invalid.
    """

    # ``app_folder`` is the Treatment/ folder containing ``main.py``.
    app_folder = Path(__file__).resolve().parents[1]
    config_path = app_folder / "config.json"

    if not config_path.is_file():
        return {}

    try:
        with config_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception:
        # On any error, ignore and fall back to env/defaults.
        return {}

    return {}


def get_data_folder() -> Path:
    """Return the folder to use for Treatment data files.

    Resolution order::

        1. Environment variable ``TREATMENT_DATA_DIR`` (if set).
        2. ``Treatment/config.json`` key ``TreatmentDataFolder`` (if present).
        3. User home directory ``~/TreatmentData`` as a generic fallback.
    """

    # 1) Environment variable override
    override = os.getenv("TREATMENT_DATA_DIR")
    if override:
        return Path(override).expanduser()

    # 2) config.json setting
    cfg = _load_config()
    cfg_path = cfg.get("TreatmentDataFolder")
    if isinstance(cfg_path, str) and cfg_path.strip():
        return Path(cfg_path).expanduser()

    # 3) Generic fallback (no hard-coded drive letter)
    return Path.home() / "TreatmentData"
