"""Capture a dark C13440 readout sequence through DCAM without HPD-TA."""

import argparse
import json
from pathlib import Path

import numpy as np
import psutil


READOUT_MODEL = "C13440-20CU"
FRAME_COUNT = 10
EXPOSURE_S = 0.025
REMOTE_PROCESSES = {"hpdta.exe", "hpdta8.exe", "hpdta95.exe", "taremoteex.exe"}


def require_exclusive_readout():
    if any((process.info["name"] or "").casefold() in REMOTE_PROCESSES
           for process in psutil.process_iter(["name"])):
        raise RuntimeError("Close HPD-TA and TaRemoteEx before opening DCAM")


def open_readout():
    from pylablib.devices import DCAM

    require_exclusive_readout()
    count = DCAM.get_cameras_number()
    if count != 1:
        raise RuntimeError(f"Expected one DCAM readout camera, found {count}")
    camera = DCAM.DCAMCamera(idx=0)
    try:
        device = camera.get_device_info()
        if READOUT_MODEL not in device.model.upper():
            raise RuntimeError(f"Expected {READOUT_MODEL}, found {device.model}")
        return camera, device
    except Exception:
        camera.close()
        raise


def capture_blank(camera, device):
    original_trigger = camera.get_trigger_mode()
    original_exposure = camera.get_exposure()
    try:
        if camera.set_trigger_mode("int") != "int":
            raise RuntimeError("DCAM internal sensor trigger did not verify")
        camera.set_exposure(EXPOSURE_S)
        exposure = camera.get_exposure()
        if not np.isclose(exposure, EXPOSURE_S, rtol=0, atol=0.001):
            raise RuntimeError(f"Unexpected DCAM exposure readback: {exposure} s")
        roi = camera.get_roi()
        frames, info = camera.grab(
            nframes=FRAME_COUNT, frame_timeout=3.0, missing_frame="none", return_info=True
        )
    finally:
        try:
            camera.set_exposure(original_exposure)
        finally:
            camera.set_trigger_mode(original_trigger)

    if len(frames) != FRAME_COUNT or len(info) != FRAME_COUNT or any(frame is None for frame in frames):
        raise RuntimeError("DCAM sequence contains missing frames")
    pixels = np.stack(frames)
    if pixels.ndim != 3 or pixels.dtype != np.dtype("uint16"):
        raise RuntimeError(f"Unexpected DCAM image layout: {pixels.shape} {pixels.dtype}")
    timestamps_us = np.asarray([entry.timestamp_us for entry in info], dtype=np.int64)
    stamps = np.asarray([entry.framestamp for entry in info], dtype=np.int64)
    if np.any(np.diff(stamps) != 1):
        raise RuntimeError("DCAM frame stamps are not consecutive")
    metadata = {
        "source": "dcam", "trigger": "sensor_internal",
        "model": device.model, "serial": device.serial_number,
        "camera_version": device.camera_version, "exposure_s": exposure,
        "roi": list(roi), "shape": list(pixels.shape), "pixel_dtype": str(pixels.dtype),
    }
    return pixels, timestamps_us, stamps, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="New .npz destination for raw frames and diagnostic metadata")
    args = parser.parse_args()
    if args.output.suffix.lower() != ".npz" or args.output.exists():
        parser.error("output must be a new .npz file")
    if not args.output.parent.is_dir():
        parser.error("output parent directory must exist")
    camera, device = open_readout()
    with camera:
        pixels, timestamps_us, stamps, metadata = capture_blank(camera, device)
    result = save_blank(args.output, pixels, timestamps_us, stamps, metadata)
    print(json.dumps(result))


def save_blank(output, pixels, timestamps_us, stamps, metadata):
    with output.open("xb") as stream:
        try:
            np.savez_compressed(stream, frames=pixels, timestamps_us=timestamps_us,
                                framestamps=stamps, metadata_json=json.dumps(metadata))
        except Exception:
            stream.close()
            output.unlink()
            raise
    return {**metadata, "output": str(output),
            "frame_intervals_us": np.diff(timestamps_us).tolist()}


if __name__ == "__main__":
    main()
