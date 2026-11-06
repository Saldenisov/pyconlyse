"""Read calibrated axes from a new HPD-TA IMG snapshot, without guessed scales."""
import re
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def image_alignment_settings(header):
    """Stable calibration identity from the current image, not Tango's cache."""
    settings = {}
    labels = {"time_range": "Time Range", "wavelength_nm": "Wavelength", "grating": "Grating"}
    labels.update({label: label for label in ("ScalingXScale", "ScalingYScale", "ScalingXUnit", "ScalingYUnit",
                                            "ScalingXScalingFile", "ScalingYScalingFile")})
    for key, label in labels.items():
        match = re.search(r'(?:^|[,\r\n])\s*' + re.escape(label) + r'=(?:"([^"]*)"|([^,\r\n]+))', header)
        if not match:
            raise ValueError(f"Current image is missing {label}")
        settings[key] = (match.group(1) if match.group(1) is not None else match.group(2)).strip()
    return settings


def alignment_calibration_key(settings, width, height):
    value = json.dumps([settings, int(width), int(height)], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def image_intensity_settings(header):
    """Identity of display mapping and acquisition settings for reference comparison.

    Display pixels are not detector counts. Retain native LUT, camera exposure,
    averaging, and external-device settings so changing gain cannot mimic a drop.
    Dates, comments, scaling and frame counters do not belong to this identity.
    """
    # HPD-TA concatenates sections directly (e.g. SubType=0[DisplayLUT]).
    sections = re.split(r"\[([^\]]+)\]", header)
    selected = {}
    for index in range(1, len(sections) - 1, 2):
        name, values = sections[index], sections[index + 1]
        if name in {"DisplayLUT", "Acquisition", "ExternalDevices"}:
            selected[name] = values.strip(",\r\n ")
        elif name == "Camera":
            # Ignore sensor temperature/status and other changing diagnostics.
            camera = {}
            for match in re.finditer(r'(?:^|,)\s*([^=,]+)=("[^"]*"|[^,\r\n]+)', values):
                key, value = match.groups()
                if key.strip() in {"CameraName", "SerialNumber", "Binning", "BinningKeyVal", "ScanMode", "ScanSpeed", "HOffs", "HWidth", "VOffs", "VWidth", "TriggerMode", "TriggerPolarity"}:
                    camera[key.strip()] = value.strip()
            selected[name] = camera
    if "DisplayLUT" not in selected or "Acquisition" not in selected:
        raise ValueError("Current image is missing display LUT or acquisition settings")
    return selected


def alignment_measurement_key(settings, width, height, average_settings=None):
    """Keep automatic per-frame contrast bounds out of the averaging context.

    The full intensity key still identifies each exact display mapping. The
    measurement context tracks operator settings; automatic LUT limits are
    transient display outputs, not a new ROI or acquisition configuration.
    """
    selected = dict(settings)
    lut = dict((match.group(1).strip(), match.group(2).strip()) for match in
               re.finditer(r'(?:^|,)\s*([^=,]+)=("[^"]*"|[^,\r\n]+)', str(settings.get("DisplayLUT", ""))))
    if lut.get("AutoLutInLiveMode") in {"1", "-1"}:
        lut.pop("LowerValue", None)
        lut.pop("UpperValue", None)
    selected["DisplayLUT"] = lut
    if average_settings is not None:
        selected["live_average"] = average_settings
    return alignment_calibration_key(selected, width, height)


def read_alignment_axes(path):
    import numpy as np
    from utilities.dataio.hamamatsu_file_opener import HamamatsuFileOpener

    info = HamamatsuFileOpener().read_critical_info(Path(path))
    axes = {}
    for name, length in (("wavelengths", info.wavelengths_length),
                         ("timedelays", info.timedelays_length)):
        values = np.asarray(getattr(info, name), dtype=float)
        if (values.shape != (length,) or length < 2 or not np.isfinite(values).all()
                or not (np.all(np.diff(values) > 0) or np.all(np.diff(values) < 0))):
            raise ValueError(f"Current image {name} calibration is invalid")
        axes[name] = values.tolist()
    wavelength_unit = str(info.scaling_xunit).strip('"').lower()
    time_unit = str(info.scaling_yunit).strip('"').replace("µ", "u").lower()
    if wavelength_unit != "nm" or time_unit not in {"ps", "ns", "us", "ms", "s"}:
        raise ValueError(f"Unverified image units: {wavelength_unit}, {time_unit}")
    settings = {}
    for key, label in (("time_range", "Time Range"), ("wavelength_nm", "Wavelength"),
                       ("grating", "Grating")):
        pattern = r'(?:^|[,\r\n])\s*' + re.escape(label) + r'="([^"]+)"'
        match = re.search(pattern, info.header)
        settings[key] = match.group(1) if match else ""
    return {**axes, "acquisition_settings": settings,
            "width": int(info.wavelengths_length),
            "height": int(info.timedelays_length), "wavelength_unit": "nm",
            "time_unit": time_unit, "source": "current_hpdta_img",
            "captured_at": datetime.now(timezone.utc).isoformat()}
