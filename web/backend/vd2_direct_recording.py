"""Record finite VD2 sequences through the synchronized Tango DCAM buffer."""

from dataclasses import replace
from datetime import datetime, timezone
from functools import lru_cache
import json
import os
from pathlib import Path
import re
import struct
from time import monotonic, sleep
from uuid import uuid4

import numpy as np

from DeviceServers.cameras.hamamatsu_streak.spectral_calibration import wavelength_calibration
from vd2_his_timing import verify_frame_rate
from vd2_measurement_protocol import Vd2ProtocolError


TIME_CALIBRATION_PATH = Path(__file__).resolve().parents[1] / "pump_probe/config/vd2_dcam_time_axis_1us.json"
FRAME_METADATA_BYTES = struct.calcsize("<qq")


@lru_cache(maxsize=1)
def _time_calibration():
    return json.loads(TIME_CALIBRATION_PATH.read_text(encoding="utf-8"))


def recording_axes(configuration):
    profile = _time_calibration()
    camera = configuration["camera"]
    x0, x1, y0, y1, xbin, ybin = camera["roi"]
    model, serial = camera["model"].strip(), str(camera["serial"]).strip()
    if re.fullmatch(r"[0-9]+", serial):
        serial = f"S/N: {serial}"
    geometry = {"CameraName": model, "SerialNumber": serial, "BinningKeyVal": f"{xbin} x {ybin}",
                "HOffs": str(x0 // xbin), "HWidth": str((x1 - x0) // xbin),
                "VOffs": str(y0 // ybin), "VWidth": str((y1 - y0) // ybin)}
    if (geometry != profile["camera"] or (x0 % xbin or y0 % ybin)
            or configuration["time_range"] != profile["time_range"] or profile["unit"] != "us"):
        raise Vd2ProtocolError("DCAM does not match the calibrated 1 us camera geometry")
    delays = np.asarray(profile["values_us"], dtype="<f4")
    if (delays.shape != (int(geometry["VWidth"]),) or not np.isfinite(delays).all()
            or delays[0] != 0 or not np.all(np.diff(delays) > 0)):
        raise Vd2ProtocolError("Invalid calibrated 1 us time axis")
    header = "[Camera]," + ",".join(f'{key}="{value}"' for key, value in geometry.items()) + "\r\n"
    optics_device = configuration["kymera_device"]
    machine = {"devices": {optics_device: {"values": configuration["optics"]}}}
    spectral = wavelength_calibration(header, machine, optics_device)
    return header, spectral, delays, profile


def _native_header(width, height, count, time_ms, comments=0):
    fixed = bytearray(64)
    struct.pack_into("<2s7H", fixed, 0, b"IM", comments, width, height, 0, 0, 3, count)
    struct.pack_into("<d", fixed, 22, time_ms)
    return fixed


def _native_comment(header, spectral, delays, profile):
    wavelengths, spectral_id, bounds = spectral
    if bounds is None:
        raise Vd2ProtocolError("The spectral calibration must identify its measured detector span")
    low, high = bounds
    labels = (header + '[Scaling],ScalingXType=2,ScalingXScale=1,ScalingXUnit="nm",'
              'ScalingXScalingFile="#{x:07d},{width:04d}",ScalingYType=2,ScalingYScale=1,'
              'ScalingYUnit="us",ScalingYScalingFile="#{y:07d},{height:04d}"\r\n'
              f'[PyConlyseSpectral],ID="{spectral_id}",ValidColumns="{low},{high}"\r\n'
              f'[PyConlyseTime],OriginalFirst="{profile["original_first_us"]}",ID="{profile["id"]}"\r\n')
    x_table = np.asarray(wavelengths, dtype="<f4").tobytes()
    y_table = delays.tobytes()
    size = len(labels.format(x=0, y=0, width=len(wavelengths), height=len(delays)).encode("ascii"))
    x_pos = 64 + size
    comments = labels.format(x=x_pos, y=x_pos + len(x_table), width=len(wavelengths), height=len(delays))
    return comments.encode("ascii") + x_table + y_table


def _write_sequence(path, count, axes, frames, rate):
    header, spectral, delays, profile = axes
    width, height = len(spectral[0]), len(delays)
    comment = _native_comment(header, spectral, delays, profile)
    previous_stamp = previous_time = None
    with path.open("xb") as stream:
        for index in range(count):
            timestamp, stamp, pixels = next(frames)
            if timestamp < 0 or stamp < 0 or (previous_stamp is not None and
                    (stamp != previous_stamp + 1 or abs((timestamp - previous_time) / 1000 - 1000 / rate) > 5)):
                raise Vd2ProtocolError(f"DCAM frame cadence or stamp invalid at frame {index + 1}")
            if pixels.shape != (height, width) or pixels.dtype != np.dtype("<u2"):
                raise Vd2ProtocolError("DCAM frame dimensions or pixel type changed")
            stream.write(_native_header(width, height, count, timestamp / 1000, len(comment) if index == 0 else 0))
            if index == 0:
                stream.write(comment)
            # The native reader interprets 16-bit pixels as signed. Store raw
            # unsigned detector counts in its 32-bit format to preserve every value.
            stream.write(pixels.astype("<i4").tobytes())
            previous_stamp, previous_time = stamp, timestamp
        stream.flush()
        os.fsync(stream.fileno())
    if count > 1:
        verify_frame_rate(path, count, rate)


def _sequence_frames(ccd, axes):
    width, height = len(axes[1][0]), len(axes[2])
    while True:
        deadline = monotonic() + 5
        while monotonic() < deadline:
            encoding, raw = ccd.ReadSequenceFrame()
            if encoding != "vd2-frame-v1":
                raise Vd2ProtocolError("Unrecognized DCAM sequence encoding")
            if len(raw):
                if len(raw) != FRAME_METADATA_BYTES + width * height * 2:
                    raise Vd2ProtocolError("Incomplete DCAM sequence frame")
                yield (*struct.unpack_from("<qq", raw),
                       np.frombuffer(raw, dtype="<u2", offset=FRAME_METADATA_BYTES).reshape(height, width))
                break
            sleep(.015)
        else:
            raise Vd2ProtocolError("No new synchronized DCAM frame in 5 seconds")


def _machine(configuration, axes):
    optics = configuration["optics"]
    camera = configuration["camera"]
    delays = configuration["delays"]
    exposure = f'{camera["exposure_ms"]:.9g} ms'
    values = {"time_range": configuration["time_range"], "streak_mode": "Operate",
              "gate_mode": "Normal", "mcp_gain": camera.get("mcp_gain", 0), "acquire_exposure_time": exposure,
              "analog_integration_count": 1, "delay_trigger_mode": "Internal",
              "delay_a": delays["a"], "delay_e": delays["e"],
              "wavelength_nm": optics["wavelength_nm"], "grating": optics["grating"]}
    return {"captured_at": datetime.now(timezone.utc).isoformat(), "readout_backend": "tango",
            "streak_control": {"connected": True, "application_running": True, "values": values},
            "direct_tango": configuration,
            "vd2_clock": {"trigger_source": configuration["dg_trigger_source"],
                          "ccd_trigger": configuration["ccd_trigger"], "base_rate_hz": configuration["rate_hz"],
                          "nominal_capture_rate_hz": configuration["rate_hz"]},
            "time_calibration": {"id": axes[3]["id"], "source_sha256": axes[3]["source_sha256"]},
            "spectral_calibration": {"id": axes[1][1], "valid_columns": list(axes[1][2])}}


def _wait_ready(coordinator, phase, *, dark_checkout=False):
    deadline = monotonic() + 20
    expected = "live" if phase == "BRUIT" or dark_checkout else "measurement_ready"
    while monotonic() < deadline:
        state = json.loads(coordinator.GetState())
        if state["state"] != "RUNNING":
            raise Vd2ProtocolError(state["error"] or "Direct Tango sequence stopped")
        if state["phase"] == expected:
            return
        sleep(.15)
    raise Vd2ProtocolError("VD2 did not verify the synchronized trigger and warm-up")


def record_direct_phase(request, coordinator, ccd, update, record, verify_bruit):
    if not 1 <= request.frames_per_his <= 65535:
        raise Vd2ProtocolError("Direct recording accepts 1–65535 HIS frames")
    destination = Path(request.his_path)
    staged = destination.with_name(f".vd2-direct-{uuid4().hex}.his")
    try:
        configuration = json.loads(coordinator.StartPhase(request.phase))
        try:
            axes = recording_axes(configuration)
            machine = _machine(configuration, axes)
            verify_bruit(machine)
            _wait_ready(coordinator, request.phase, dark_checkout=configuration.get("dark_checkout", False))
            rate = configuration["rate_hz"]
            record("acquiring", machine_before=machine)
            update(status="acquiring", capture_rate=rate, capture_started_at=datetime.now(timezone.utc).isoformat())
            ccd.BufferSequence(request.frames_per_his)
            _write_sequence(staged, request.frames_per_his, axes, _sequence_frames(ccd, axes), rate)
            update(status="saving")
            final_configuration = json.loads(coordinator.PhaseConfiguration())
            if final_configuration != configuration:
                raise Vd2ProtocolError("Optical, time or trigger settings changed during VD2 recording")
        finally:
            coordinator.StopLive()
        if os.name == "nt":
            staged.rename(destination)
        else:
            os.link(staged, destination)
        spectral_axis, spectral_id, coverage = axes[1]
        return replace(request, spectral_axis_nm=spectral_axis, spectral_calibration_id=spectral_id,
                       spectral_valid_columns=coverage, direct_rate_hz=rate), _machine(final_configuration, axes)
    finally:
        staged.unlink(missing_ok=True)
