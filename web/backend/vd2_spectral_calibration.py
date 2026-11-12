"""Verified wavelength axes for the streak detector in camera-only mode."""
import json
import math
import os
from pathlib import Path
import re

import numpy as np


def camera_geometry(header):
    section = re.search(r"(?m)^\[Camera\][^\r\n]*", header)
    if not section:
        raise ValueError("HIS does not identify the camera geometry")
    fields = dict(re.findall(r'([A-Za-z]+)="([^"]*)"', section.group()))
    keys = ("CameraName", "SerialNumber", "BinningKeyVal", "HOffs", "HWidth", "VOffs", "VWidth")
    if any(key not in fields for key in keys):
        raise ValueError("HIS camera geometry is incomplete")
    return {key: fields[key] for key in keys}


def verified_wavelengths(header, machine, kymera_device):
    """Return the streak pixel calibration only for a matching optical configuration."""
    default = Path(__file__).resolve().parents[1] / "pump_probe" / "config" / "vd2_spectral_calibration_550nm.json"
    configured = os.environ.get("PYCONLYSE_VD2_SPECTRAL_CALIBRATION")
    profile = json.loads((Path(configured) if configured else default).read_text(encoding="utf-8"))
    optics = machine.get("devices", {}).get(kymera_device, {}).get("values", {})
    for key, expected in profile["kymera"].items():
        current = optics.get(key)
        if isinstance(expected, (int, float)):
            if type(current) not in (int, float) or not math.isclose(current, expected, abs_tol=0.05, rel_tol=0):
                raise ValueError(f"Spectral calibration does not match Kymera {key}")
        elif not isinstance(current, str) or current.casefold() != expected.casefold():
            raise ValueError(f"Spectral calibration does not match Kymera {key}")
    geometry = camera_geometry(header)
    if geometry != profile["camera"]:
        raise ValueError("Spectral calibration does not match the HIS camera geometry")
    axis = np.asarray(profile["wavelengths_nm"], dtype=float)
    diff = np.diff(axis)
    if (axis.shape != (int(geometry["HWidth"]),) or not np.isfinite(axis).all()
            or not (np.all(diff > 0) or np.all(diff < 0))):
        raise ValueError("Invalid streak wavelength calibration")
    return tuple(axis.tolist()), profile["id"]
