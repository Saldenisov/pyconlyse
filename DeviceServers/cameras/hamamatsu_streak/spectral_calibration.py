"""Verified wavelength axes for the streak detector in camera-only mode."""
import json
import math
import os
from pathlib import Path
import re

import numpy as np


SETTING_TOLERANCE_NM = 0.05


def camera_geometry(header):
    section = re.search(r"(?:^|[\r\n])\[Camera\][^\r\n\[]*", header)
    if not section:
        raise ValueError("HIS does not identify the camera geometry")
    fields = dict(re.findall(r'([A-Za-z]+)="([^"]*)"', section.group()))
    keys = ("CameraName", "SerialNumber", "BinningKeyVal", "HOffs", "HWidth", "VOffs", "VWidth")
    if any(key not in fields for key in keys):
        raise ValueError("HIS camera geometry is incomplete")
    return {key: fields[key] for key in keys}


def load_spectral_calibration(path=None):
    default = Path(__file__).resolve().parents[3] / "web" / "pump_probe" / "config" / "vd2_spectral_calibration_hg_20261116.json"
    configured = path or os.environ.get("PYCONLYSE_VD2_SPECTRAL_CALIBRATION")
    profile = json.loads((Path(configured) if configured else default).read_text(encoding="utf-8"))
    if "profiles" in profile:
        profiles = profile["profiles"]
        if not isinstance(profiles, list) or not profiles or any(not isinstance(item, dict) for item in profiles):
            raise ValueError("Invalid collection of wavelength profiles")
        for item in profiles:
            _validate_profile(item)
            if "grating" not in item["kymera"] or "blaze_wavelength_nm" not in item["kymera"]:
                raise ValueError("A wavelength profile requires a physical grating and blaze")
        if len({item["id"] for item in profiles}) != len(profiles):
            raise ValueError("Duplicate wavelength profile identity")
        return profile
    return _validate_profile(profile)


def _validate_profile(profile):
    if not isinstance(profile["id"], str) or not profile["id"].strip() or not profile["kymera"]:
        raise ValueError("Invalid streak spectral calibration identity")
    width = int(profile["camera"]["HWidth"])
    if "wavelength_settings" in profile:
        if "wavelength_nm" in profile["kymera"] or "wavelengths_nm" in profile:
            raise ValueError("Use either a scanned profile or a fixed wavelength table")
        settings = _scanned_tables(profile, width)
        for entry, (setting, axis) in zip(profile["wavelength_settings"], settings):
            if "valid_columns" in entry:
                _column_limits(entry["valid_columns"], width)
            entry["center_pixel"], entry["dispersion_nm_per_pixel"] = _center_and_dispersion(axis, setting)
    else:
        axis = wavelength_table(profile["wavelengths_nm"], width)
        setting = profile["kymera"].get("wavelength_nm")
        if setting is not None and min(axis[0], axis[-1]) <= setting <= max(axis[0], axis[-1]):
            profile["center_pixel"], profile["dispersion_nm_per_pixel"] = _center_and_dispersion(axis, setting)
    return profile


def _column_limits(bounds, width):
    if (not isinstance(bounds, (list, tuple)) or len(bounds) != 2
            or any(type(value) is not int for value in bounds)
            or not 0 <= bounds[0] < bounds[1] < width):
        raise ValueError("Invalid measured detector columns")
    return tuple(bounds)


def wavelength_table(values, width):
    with np.errstate(over="ignore", invalid="ignore"):
        axis = np.asarray(values, dtype="<f4")
    diff = np.diff(axis) if axis.ndim == 1 else np.array([])
    if (width < 2 or axis.shape != (width,) or not np.isfinite(axis).all()
            or not (np.all(diff > 0) or np.all(diff < 0))):
        raise ValueError("Invalid streak wavelength calibration")
    return axis


def _center_and_dispersion(axis, setting):
    """Locate the readback wavelength in zero-based columns of the recorded image."""
    pixels = np.arange(len(axis))
    ordered_axis, ordered_pixels = (axis, pixels) if axis[0] < axis[-1] else (axis[::-1], pixels[::-1])
    if not ordered_axis[0] <= setting <= ordered_axis[-1]:
        raise ValueError("Kymera setting is outside its measured wavelength table")
    pixel = float(np.interp(setting, ordered_axis, ordered_pixels))
    left = min(int(pixel), len(axis) - 2)
    return pixel, float(axis[left + 1] - axis[left])


def _scanned_tables(profile, width):
    settings = []
    for entry in profile["wavelength_settings"]:
        setting = entry["wavelength_nm"]
        if type(setting) not in (int, float) or not math.isfinite(setting) or setting <= 0:
            raise ValueError("Invalid Kymera wavelength in scan")
        axis = wavelength_table(entry["wavelengths_nm"], width)
        if not min(axis[0], axis[-1]) <= setting <= max(axis[0], axis[-1]):
            raise ValueError("Kymera setting is outside its measured wavelength table")
        if settings and (setting <= settings[-1][0]
                         or (axis[0] < axis[-1]) != (settings[-1][1][0] < settings[-1][1][-1])):
            raise ValueError("Kymera scan settings must increase and all tables must have the same direction")
        settings.append((setting, axis))
    if not settings:
        raise ValueError("Kymera wavelength scan is empty")
    return settings


def _axis_for_setting(settings, readback):
    if type(readback) not in (int, float) or not math.isfinite(readback):
        raise ValueError("Kymera wavelength readback is unavailable")
    first_setting, first_axis = settings[0]
    last_setting, last_axis = settings[-1]
    if not first_setting - SETTING_TOLERANCE_NM <= readback <= last_setting + SETTING_TOLERANCE_NM:
        raise ValueError("Kymera wavelength is outside the measured calibration scan")
    if readback <= first_setting:
        return first_axis
    if readback >= last_setting:
        return last_axis
    for (lower, lower_axis), (upper, upper_axis) in zip(settings, settings[1:]):
        if readback <= upper:
            if readback == upper:
                return upper_axis
            fraction = (readback - lower) / (upper - lower)
            # Interpolate the same detector columns across settings. Each
            # measured table can have its own offset, dispersion and curvature.
            return (1 - fraction) * lower_axis.astype(float) + fraction * upper_axis


def _matching_optics(profile, optics):
    for key, expected in profile["kymera"].items():
        current = optics.get(key)
        if isinstance(expected, (int, float)):
            if type(current) not in (int, float) or not math.isclose(
                current, expected, abs_tol=SETTING_TOLERANCE_NM, rel_tol=0
            ):
                return key
        elif not isinstance(current, str) or current.casefold() != expected.casefold():
            return key
    return None


def _valid_columns(entries, readback, width):
    if not any("valid_columns" in entry for entry in entries):
        return None
    if not all("valid_columns" in entry for entry in entries):
        raise ValueError("Measured columns must be declared at every calibration setting")
    for index, entry in enumerate(entries):
        if readback <= entry["wavelength_nm"]:
            right = _column_limits(entry["valid_columns"], width)
            if index == 0 or readback == entry["wavelength_nm"]:
                return right
            left = _column_limits(entries[index - 1]["valid_columns"], width)
            # Use only the detector span covered at both bracketing settings.
            return _column_limits((max(left[0], right[0]), min(left[1], right[1])), width)
    return _column_limits(entries[-1]["valid_columns"], width)


def _matches_camera(header, expected, image_shape):
    if image_shape is None or re.search(r"(?:^|[\r\n])\[Camera\]", header):
        return camera_geometry(header) == expected

    # HPD-TA IMG omits the Camera section. For a frame from this device server,
    # certify the recorded ROI and binning using the native Acquisition section.
    match = re.search(r"(?:^|[\r\n])\[Acquisition\][^\r\n\[]*", header)
    if not match:
        return False
    fields = dict(re.findall(r'([A-Za-z]+)="([^"]*)"', match.group()))
    binning = tuple(int(value) for value in expected["BinningKeyVal"].split("x"))
    origin = (int(expected["HOffs"]) * binning[0], int(expected["VOffs"]) * binning[1])
    shape = int(expected["HWidth"]), int(expected["VWidth"])
    return (
        tuple(image_shape) == shape
        and fields.get("pntBinning") == f"{binning[0]},{binning[1]}"
        and fields.get("pntOrigCh") == f"{origin[0]},{origin[1]}"
        and fields.get("areSource") == f"0,0,{shape[0]},{shape[1]}"
        and ",miMirrorRotate=0" in match.group() + ","
    )


def wavelength_calibration(header, machine, kymera_device, *, image_shape=None):
    """Use the camera's profile with the optical settings recorded at capture."""
    machine = machine or {}
    profile = machine.get("streak_spectral_calibration")
    if profile is None:
        # Compatibility with snapshots from before the camera exported its profile.
        profile = load_spectral_calibration()
    if not isinstance(profile, dict) or not profile:
        raise ValueError("Camera spectral calibration is unavailable")
    optics = machine.get("devices", {}).get(kymera_device, {}).get("values", {})
    if "profiles" in profile:
        matches = [item for item in profile["profiles"] if not _matching_optics(item, optics)]
        if len(matches) != 1:
            raise ValueError("No unique wavelength profile matches the recorded Kymera grating and optics")
        profile = matches[0]
    else:
        mismatch = _matching_optics(profile, optics)
        if mismatch is not None:
            raise ValueError(f"Spectral calibration does not match Kymera {mismatch}")
    if not _matches_camera(header, profile["camera"], image_shape):
        layout = "HIS" if image_shape is None else "IMG"
        raise ValueError(f"Spectral calibration does not match the {layout} camera geometry")
    width = int(profile["camera"]["HWidth"])
    bounds = None
    if "wavelength_settings" in profile:
        settings = _scanned_tables(profile, width)
        readback = optics.get("wavelength_nm")
        values = _axis_for_setting(settings, readback)
        bounds = _valid_columns(profile["wavelength_settings"], readback, width)
    else:
        values = profile["wavelengths_nm"]
    axis = wavelength_table(values, width)
    return tuple(axis.tolist()), profile["id"], bounds


def verified_wavelengths(header, machine, kymera_device):
    axis, identity, _ = wavelength_calibration(header, machine, kymera_device)
    return axis, identity
