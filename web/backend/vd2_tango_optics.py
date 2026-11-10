"""VD2 instrument access for the camera-only HPD-TA profile."""
from contextlib import contextmanager
import math
import time


KYMERA_ATTRIBUTES = {
    "wavelength_nm": "wavelength_nm", "grating": "lines_per_mm",
    "blaze": "blaze_wavelength_nm", "ruling": "lines_per_mm",
    "exit_mirror": "exit_mirror", "turret": "turret",
    "slit_width_um": "active_input_slit_um", "spectrograph_shutter": "shutter",
    "focus_mirror": "focus_mirror", "side_entry_iris": "side_entry_iris",
}
SPEC_QUERIES = {
    "DevParamGet(Spec,Wavelength)": "wavelength_nm",
    "DevParamGet(Spec,Slit Width)": "slit_width_um",
    "DevParamGet(Spec,Shutter)": "spectrograph_shutter",
    "DevParamGet(Spec,Blaze)": "blaze",
    "DevParamGet(Spec,Ruling)": "ruling",
}
DG_CHANNELS = {f"delay_{channel.lower()}": channel for channel in "ABCDEFGH"}
DG_FIELDS = set(DG_CHANNELS) | {
    "delay_trigger_mode", "delay_repetition_rate", "delay_burst_mode",
    "delay_setting", "delay_ss_trigger", "delay_manual_control",
}
EXTERNAL_FIELDS = set(KYMERA_ATTRIBUTES) | DG_FIELDS
TRIGGER_SOURCES = {"Internal": 0, "Ext. rising": 1, "Ext. falling": 2}


def parameter_target(api, name):
    if not api.VD2_CAMERA_ONLY or name not in EXTERNAL_FIELDS:
        spec = api.WRITABLE_PARAMETERS[name]
        command = f"write_attribute:{spec['attribute']}" if "attribute" in spec else spec["command"]
        return api.STREAK_DEVICE, command
    if name in KYMERA_ATTRIBUTES:
        command = "SelectGratingRuling" if name == "grating" else f"write_attribute:{KYMERA_ATTRIBUTES[name]}"
        return api.KYMERA_DEVICE, command
    if name in DG_CHANNELS:
        return api.DG645_DEVICE, "set_delay"
    if name in {"delay_trigger_mode", "delay_repetition_rate", "delay_burst_mode"}:
        return api.DG645_DEVICE, "scpi_write"
    raise ValueError(f"{name} is a full-profile HPD-TA setting")


def _value(proxy, attribute):
    return proxy.read_attribute(attribute).value


def _proxy(api, device):
    proxy = api.DeviceProxy(device)
    proxy.set_timeout_millis(5000)
    if str(proxy.state()).split(".")[-1] != "ON":
        raise RuntimeError(f"{device} is not ON")
    return proxy


def _query(dg645, command):
    result = float(dg645.command_inout("scpi_query", command))
    if not math.isfinite(result):
        raise RuntimeError(f"DG645 returned invalid {command} readback")
    return result


def _set(dg645, command, query, expected):
    dg645.command_inout("scpi_write", command)
    if not math.isclose(_query(dg645, query), expected, rel_tol=0.0, abs_tol=1e-8):
        raise RuntimeError(f"DG645 did not verify {command}")


def burst_armed(dg645):
    mode = _query(dg645, "BURM?")
    if mode not in {0, 1}:
        raise RuntimeError(f"Unexpected DG645 BURM readback {mode}")
    return mode == 1


def _validate_five_hz_source(dg645):
    source = _query(dg645, "TSRC?")
    if source == 0 and math.isclose(_query(dg645, "TRAT?"), 5, rel_tol=0, abs_tol=1e-8):
        return
    if source not in {1, 2}:
        raise RuntimeError("Paired acquisition requires Internal 5 Hz or an external 5 Hz trigger")


def validate_paired_burst(dg645):
    _validate_five_hz_source(dg645)
    if _query(dg645, "BURC?") != 2 or not math.isclose(_query(dg645, "BURP?"), 0.1, abs_tol=1e-8):
        raise RuntimeError("Paired acquisition requires two DG645 pulses 100 ms apart")


def read_external(api, name, proxies=None):
    device = api.KYMERA_DEVICE if name in KYMERA_ATTRIBUTES else api.DG645_DEVICE
    if proxies is None:
        proxy = _proxy(api, device)
    else:
        if device not in proxies:
            proxies[device] = _proxy(api, device)
        proxy = proxies[device]
    if name in KYMERA_ATTRIBUTES:
        value = _value(proxy, KYMERA_ATTRIBUTES[name])
        return f"{float(value):g} g/mm" if name == "grating" else value
    if name in DG_CHANNELS:
        return float(proxy.command_inout("get_delay", DG_CHANNELS[name]).split(",")[1])
    if name == "delay_trigger_mode":
        source = _query(proxy, "TSRC?")
        if source == 5:
            return "Standby (Internal)"
        return next((key for key, value in TRIGGER_SOURCES.items() if value == source), f"TSRC {source:g}")
    if name == "delay_repetition_rate":
        return _query(proxy, "TRAT?") if _query(proxy, "TSRC?") in {0, 5} else None
    if name == "delay_burst_mode":
        return "On" if burst_armed(proxy) else "Off"
    raise ValueError(f"{name} is a full-profile HPD-TA setting")


def write_parameter(api, camera, name, value):
    device, command = parameter_target(api, name)
    if device == api.STREAK_DEVICE:
        if command.startswith("write_attribute:"):
            camera.write_attribute(command.split(":", 1)[1], value)
        else:
            camera.command_inout(command, value)
        return
    proxy = _proxy(api, device)
    if device == api.KYMERA_DEVICE:
        proxy.set_timeout_millis(45000)
        if name == "grating":
            proxy.command_inout(command, float(str(value).removesuffix(" g/mm")))
        else:
            if name in {"turret", "focus_mirror", "side_entry_iris"}:
                value = int(value)
            if name in {"wavelength_nm", "slit_width_um"} and not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            proxy.write_attribute(KYMERA_ATTRIBUTES[name], value)
        return
    if name in DG_CHANNELS:
        channel = DG_CHANNELS[name]
        seconds = float(value)
        if not math.isfinite(seconds):
            raise ValueError("DG645 delay must be finite")
        reference = proxy.command_inout("get_delay", channel).split(",")[0]
        proxy.command_inout("set_delay", f"{channel},{int(reference)},{seconds:.12g}")
    elif name == "delay_trigger_mode":
        if value not in TRIGGER_SOURCES:
            raise ValueError("Unknown DG645 trigger source")
        source = TRIGGER_SOURCES[value]
        if source == 0:
            pause_internal_clock(proxy)
        else:
            _set(proxy, f"TSRC {source}", "TSRC?", source)
    elif name == "delay_repetition_rate":
        rate = float(value)
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("DG645 repetition rate must be finite and positive")
        _set(proxy, f"TRAT {rate:.12g}", "TRAT?", rate)
    elif name == "delay_burst_mode":
        if value != "Off":
            raise ValueError("Burst is armed automatically by an ABS or BASE measurement")
        pause_internal_clock(proxy)



def run_camera_acquisition(api, camera, command):
    dg645 = _proxy(api, api.DG645_DEVICE)
    source = _query(dg645, "TSRC?")
    if source not in {0, 5}:
        camera.command_inout(command)
        return
    if command in {"StopAcquisition", "StopSequence"}:
        try:
            camera.command_inout(command)
        finally:
            pause_internal_clock(dg645)
        return
    live_started = False
    try:
        if source == 5:
            _set(dg645, "TSRC 0", "TSRC?", 0)
        camera.command_inout(command)
        live_started = command == "StartLive"
    finally:
        if not live_started:
            pause_internal_clock(dg645)


def pause_internal_clock(dg645):
    try:
        if _query(dg645, "TSRC?") != 5:
            _set(dg645, "TSRC 5", "TSRC?", 5)
    finally:
        if burst_armed(dg645):
            _set(dg645, "BURM 0", "BURM?", 0)


def _confirm_flash_lamp_power(api):
    lamp = _proxy(api, api.ZABER_PDU_DEVICE)
    ids = list(map(int, _value(lamp, "ids")))
    states = list(map(int, _value(lamp, "states")))
    if len(ids) != len(states) or len(set(ids)) != len(ids) or dict(zip(ids, states)).get(1) != 1:
        raise RuntimeError("VD2 flash lamp supply must be verified ON before warm-up")


@contextmanager
def measurement_clock(api, camera, request):
    if not api.VD2_CAMERA_ONLY:
        yield None
        return
    dg645 = _proxy(api, api.DG645_DEVICE)
    if _query(dg645, "TSRC?") not in {0, 5} or not math.isclose(
        _query(dg645, "TRAT?"), 5, rel_tol=0, abs_tol=1e-8
    ):
        raise RuntimeError("VD2 managed acquisition requires the internal 5 Hz clock")
    paired = request.phase in {"ABSORPTION", "BASE"}
    if paired and request.frames_per_his % 2:
        raise ValueError("Paired Burst recording requires an even frame count")
    api._verify_vd2_timing_ready(camera)
    if paired:
        _confirm_flash_lamp_power(api)
    acquisition_error = None
    try:
        pause_internal_clock(dg645)
        if paired:
            _set(dg645, "BURC 2", "BURC?", 2)
            _set(dg645, "BURP 0.1", "BURP?", 0.1)
            if _query(dg645, "BURD?") != 0:
                raise RuntimeError("Expected zero DG645 burst delay for paired recording")
            _set(dg645, "BURM 1", "BURM?", 1)
        _set(dg645, "TSRC 0", "TSRC?", 0)
        if paired:
            validate_paired_burst(dg645)
            time.sleep(10.0)
        yield 10 if paired else 5
    except Exception as exc:
        acquisition_error = exc
        raise
    finally:
        try:
            pause_internal_clock(dg645)
        except Exception as exc:
            prefix = f"{acquisition_error}; " if acquisition_error else ""
            raise RuntimeError(f"{prefix}DG645 pulse pause or Burst OFF unverified: {exc}") from exc


def verify_image_optics(settings, kymera_values):
    """Fail closed when HPD-TA still reports legacy spectral metadata."""
    actual_center = float(settings["wavelength_nm"])
    center = float(kymera_values["wavelength_nm"])
    ruling = float(kymera_values["lines_per_mm"])
    index = int(kymera_values["grating"])
    label = settings["grating"].lower().strip()
    try:
        correct_grating = (abs(float(label.removesuffix(" g/mm")) - ruling) <= 0.01
                           if label.endswith(" g/mm") else int(label) == index)
    except ValueError:
        correct_grating = False
    if not (math.isfinite(actual_center) and math.isfinite(center)
            and abs(actual_center - center) <= 0.1 and correct_grating):
        raise RuntimeError("HPD-TA wavelength/grating metadata do not match Tango Kymera")


def validate_saved_capture(api, request, machine_before, rate):
    if not api.VD2_CAMERA_ONLY:
        return
    from pathlib import Path
    import numpy as np
    from utilities.dataio.hamamatsu_file_opener import HamamatsuFileOpener
    from vd2_his_timing import verify_frame_rate

    try:
        if rate is not None:
            verify_frame_rate(request.his_path, request.frames_per_his, rate)
        kymera = machine_before["devices"][api.KYMERA_DEVICE]["values"]
        info = HamamatsuFileOpener().read_critical_info(Path(request.his_path))
        verify_image_optics(api.image_alignment_settings(info.header), kymera)
        wavelengths = np.asarray(info.wavelengths, dtype=float)
        if (str(info.scaling_xunit).strip('"').lower() != "nm"
                or wavelengths.size < 2 or not np.isfinite(wavelengths).all()
                or not (np.all(np.diff(wavelengths) > 0) or np.all(np.diff(wavelengths) < 0))):
            raise ValueError("HIS wavelength calibration must be finite and monotonic in nm")
    except Exception as exc:
        raise RuntimeError(f"VD2 frame timing or spectral metadata unverified; raw HIS retained: {exc}") from exc
