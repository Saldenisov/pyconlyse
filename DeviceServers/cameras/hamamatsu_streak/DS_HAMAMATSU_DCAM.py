"""Standalone Tango device for the C13440 USB sensor in a streak system."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
import json
import math
import struct
import time

import numpy as np
from tango import AttrWriteType, DevLong64, DevState, DevUShort
from tango.server import Device, attribute, command

from DeviceServers.cameras.hamamatsu_streak.dcam_readout_probe import (
    READOUT_MODEL,
    open_readout,
)
from DeviceServers.cameras.hamamatsu_streak.c13410_usb import C13410Usb, configure_synchronized_sweep
from DeviceServers.instruments.dg645.vd2_timing import timing_for_range


SDK_TIMEOUT_S = 5.0
OPEN_TIMEOUT_S = 25.0
SWEEP_SENSOR_PROPERTIES = {
    "TRIGGER ACTIVE": 1,     # Edge
    "TRIGGER POLARITY": 2,   # Falling
    "TRIGGER TIMES": 1,
    "TRIGGER DELAY": 0,
    "READOUT SPEED": 2,
    "TRIGGER GLOBAL EXPOSURE": 5,  # Global reset starts exposure for all rows together.
}


class DS_HAMAMATSU_DCAM(Device):
    """Explicitly open, run and close a direct DCAM readout session."""

    def init_device(self):
        super().init_device()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dcam-tango")
        self._pending = None
        self._camera = None
        self._model = ""
        self._prior_trigger = None
        self._prior_sweep_properties = {}
        self._sweep_head = None
        self._sweep_shutter_requested = False
        self._sweep_token = None
        self._sweep_frame = None
        self._sweep_frame_count = 0
        self._sweep_vrt_count = 0
        self._capture_buffer = None
        self._capture_remaining = 0
        self._detector_size = ()
        self._sensor_roi = ()
        self._exposure_ms = None
        self._timestamp_us = -1
        self._frame_stamp = -1
        self.set_state(DevState.OFF)
        self.set_status("DCAM closed. Use OpenReadout to connect.")

    def delete_device(self):
        self._sweep_token = None
        try:
            # Teardown, including Tango Init, waits for release before reinitializing.
            self._worker.submit(self._close).result()
        finally:
            self._worker.shutdown(wait=True)
            super().delete_device()

    def _sdk(self, operation, *args, timeout=None):
        # Never enqueue a request behind a native call with an unresolved outcome.
        if self._pending is not None and not self._pending.done():
            raise RuntimeError("Previous DCAM call is still running")
        self._pending = self._worker.submit(operation, *args)
        timeout = SDK_TIMEOUT_S if timeout is None else timeout
        try:
            return self._pending.result(timeout=timeout)
        except TimeoutError as exc:
            self._sweep_token = None
            self.set_state(DevState.FAULT)
            message = f"DCAM {operation.__name__} timed out after {timeout:g} s"
            self.set_status(message)
            raise RuntimeError(message) from exc
        except Exception as exc:
            self._sweep_token = None
            self.set_state(DevState.FAULT)
            self.set_status(f"DCAM {operation.__name__} failed: {exc}")
            raise

    @command
    def OpenReadout(self):
        if self.get_state() == DevState.FAULT:
            raise RuntimeError("CloseReadout must resolve the previous DCAM failure")
        if self._camera is None:
            self._sdk(self._open, timeout=OPEN_TIMEOUT_S)
            self.set_state(DevState.ON)
            self.set_status("DCAM connected. Sensor acquisition idle.")

    def _open(self):
        camera, info = open_readout()
        self._camera = camera
        if info.model.strip().upper() != READOUT_MODEL:
            camera.close()
            self._camera = None
            raise RuntimeError(f"Expected {READOUT_MODEL}, got {info.model}")
        self._detector_size = tuple(camera.get_detector_size())
        self._sensor_roi = tuple(camera.get_roi())
        self._exposure_ms = self._read_exposure_ms()
        self._model = info.model
        self._serial = info.serial_number

    @command(dtype_out=str)
    def ReadoutConfiguration(self):
        if self._camera is None:
            raise RuntimeError("DCAM is closed")
        return json.dumps({"model": self._model, "serial": self._serial,
                           "roi": self._sensor_roi, "exposure_ms": self._exposure_ms})

    @command
    def CloseReadout(self):
        self._sweep_token = None
        self._sdk(self._close)
        self.set_state(DevState.OFF)
        self.set_status("DCAM closed.")

    def _close(self):
        try:
            self._stop()
        finally:
            if self._camera is not None:
                self._camera.close()
                self._camera = None
                self._prior_trigger = None
                self._prior_sweep_properties.clear()
                self._model = ""
                self._serial = ""
                self._detector_size = ()
                self._sensor_roi = ()
                self._exposure_ms = None
                self._clear_frame_metadata()

    @command
    def StartLive(self):
        if self.get_state() == DevState.RUNNING:
            return
        if self.get_state() != DevState.ON:
            raise RuntimeError("OpenReadout and resolve any DCAM fault before StartLive")
        self._sdk(self._start)
        self.set_state(DevState.RUNNING)
        self.set_status("DCAM sensor is acquiring with its internal trigger.")

    def _start(self):
        self._clear_frame_metadata()
        self._prior_trigger = self._camera.get_trigger_mode()
        try:
            if self._camera.set_trigger_mode("int") != "int":
                raise RuntimeError("DCAM internal trigger did not verify")
            self._camera.start_acquisition(mode="sequence", nframes=8)
        except Exception:
            self._stop()
            raise

    @command
    def StartSynchronizedLive(self):
        """Acquire a synchronized Live stream at 1 us."""
        self._start_synchronized_live("1 us")

    @command(dtype_in=str)
    def StartSynchronizedLiveAt(self, time_range):
        """Acquire a synchronized Live stream at an explicitly calibrated range."""
        self._start_synchronized_live(timing_for_range(time_range).time_range)

    def _start_synchronized_live(self, time_range):
        self._require_idle()
        if not math.isclose(self._exposure_ms, 10.0, abs_tol=0.05):
            raise RuntimeError("Set ExposureMs to 10 before starting the synchronized sweep")
        self._sdk(self._start_synchronized, time_range)
        self.set_state(DevState.RUNNING)
        self.set_status(f"External CCD trigger, C13410 {time_range} Operate, VRT after each acquired frame.")
        token = object()
        self._sweep_token = token
        self._worker.submit(self._poll_synchronized_frame, token)

    def _start_synchronized(self, time_range):
        self._clear_frame_metadata()
        self._sweep_frame = None
        self._sweep_frame_count = 0
        self._sweep_vrt_count = 0
        self._sweep_head = head = C13410Usb()
        try:
            configure_synchronized_sweep(head, time_range)
            camera = self._camera
            camera.clear_acquisition()
            self._prior_trigger = camera.get_trigger_mode()
            if camera.set_trigger_mode("ext") != "ext":
                raise RuntimeError("DCAM external trigger did not verify")
            for name, value in SWEEP_SENSOR_PROPERTIES.items():
                current = camera.get_attribute_value(name)
                if current != value:
                    self._prior_sweep_properties[name] = current
                    camera.set_attribute_value(name, value)
                if camera.get_attribute_value(name) != value:
                    raise RuntimeError(f"DCAM {name} did not verify")
            camera.start_acquisition(mode="sequence", nframes=8)
            self._sweep_shutter_requested = True
            head.write("SHT O")
            if head.read("SHT") != "SHT O":
                raise RuntimeError("C13410 shutter did not verify Open")
            head.rearm()
            self._sweep_vrt_count = 1
        except Exception:
            self._stop()
            raise

    def _poll_synchronized_frame(self, token):
        if self._sweep_token is not token:
            return
        try:
            newest = self._camera.read_oldest_image(peek=False, return_info=True)
            if self._sweep_token is not token:
                return
            if newest is None:
                time.sleep(0.005)
            else:
                pixels, info = newest
                self._validate_frame(pixels, info)
                stamp = int(info.framestamp)
                if self._sweep_frame is not None and stamp != self._sweep_frame[1] + 1:
                    raise RuntimeError(f"DCAM skipped a synchronized frame at stamp {stamp}")
                self._sweep_head.rearm()
                self._sweep_vrt_count += 1
                self._sweep_frame_count += 1
                self._sweep_frame = (int(info.timestamp_us), stamp, pixels.copy(order="C"))
                if self._capture_remaining:
                    if len(self._capture_buffer) == self._capture_buffer.maxlen:
                        raise RuntimeError("DCAM recording buffer overflowed; sequence incomplete")
                    self._capture_buffer.append(self._sweep_frame)
                    self._capture_remaining -= 1
        except Exception as error:
            self._sweep_token = None
            detail = str(error)
            try:
                self._stop()
            except Exception as cleanup_error:
                detail += f". Acquisition cleanup failed: {cleanup_error}"
            self.set_state(DevState.FAULT)
            self.set_status(f"Synchronized sweep failed: {detail}")
            return
        if self._sweep_token is token:
            self._worker.submit(self._poll_synchronized_frame, token)

    @attribute(name="SweepFrameCount", dtype=DevLong64)
    def sweep_frame_count(self):
        return self._sweep_frame_count

    @attribute(name="SweepVrtCount", dtype=DevLong64)
    def sweep_vrt_count(self):
        """Acknowledged VRT commands, including the initial rearm."""
        return self._sweep_vrt_count

    @command(dtype_in=int)
    def BufferSequence(self, count):
        if self.get_state() != DevState.RUNNING or not 1 <= count <= 65535:
            raise RuntimeError("A synchronized sweep and 1–65535 frames are required")
        self._sdk(self._begin_sequence, count)

    def _begin_sequence(self, count):
        if self._sweep_head is None or self._capture_buffer is not None:
            raise RuntimeError("DCAM synchronized sequence is unavailable or already started")
        self._capture_buffer = deque(maxlen=32)
        self._capture_remaining = count

    @command(dtype_out="DevEncoded")
    def ReadSequenceFrame(self):
        if self.get_state() != DevState.RUNNING:
            raise RuntimeError("DCAM synchronized sequence is not running")
        frame = self._sdk(self._take_sequence_frame)
        if frame is None:
            return "vd2-frame-v1", b""
        timestamp, stamp, pixels = frame
        return "vd2-frame-v1", struct.pack("<qq", timestamp, stamp) + pixels.astype("<u2", copy=False).tobytes()

    def _take_sequence_frame(self):
        if self._capture_buffer is None:
            raise RuntimeError("DCAM sequence has not started")
        return self._capture_buffer.popleft() if self._capture_buffer else None

    @command
    def StopLive(self):
        self._sweep_token = None
        if self._camera is not None:
            self._sdk(self._stop)
            if self.get_state() == DevState.RUNNING:
                self.set_state(DevState.ON)
                self.set_status("DCAM connected. Sensor acquisition idle.")

    def _stop(self):
        errors = []
        self._capture_buffer = None
        self._capture_remaining = 0
        synchronized = self._sweep_head is not None
        if synchronized:
            try:
                if self._sweep_shutter_requested:
                    self._sweep_head.write("SHT C")
                    if self._sweep_head.read("SHT") != "SHT C":
                        raise RuntimeError("C13410 shutter close did not verify")
                    self._sweep_shutter_requested = False
            except Exception as exc:
                errors.append(exc)
            if not self._sweep_shutter_requested:
                try:
                    self._sweep_head.close()
                    self._sweep_head = None
                except Exception as exc:
                    errors.append(exc)
        if self._prior_trigger is not None:
            try:
                if synchronized or self._prior_sweep_properties:
                    # Global exposure mode can only be changed with DCAM buffers released.
                    self._camera.clear_acquisition()
                else:
                    self._camera.stop_acquisition()
                for name, value in self._prior_sweep_properties.items():
                    self._camera.set_attribute_value(name, value)
                    if self._camera.get_attribute_value(name) != value:
                        raise RuntimeError(f"DCAM could not restore {name}")
                self._prior_sweep_properties.clear()
                if self._camera.set_trigger_mode(self._prior_trigger) != self._prior_trigger:
                    raise RuntimeError("DCAM previous trigger mode did not verify")
                self._prior_trigger = None
            except Exception as exc:
                errors.append(exc)
        self._sweep_frame = None
        self._clear_frame_metadata()
        if errors:
            raise RuntimeError(". ".join(str(error) for error in errors))

    def _require_idle(self):
        if self.get_state() != DevState.ON:
            raise RuntimeError("Settings require an open, idle readout. StopLive first.")

    @command(dtype_in=(int,), dtype_out=(int,))
    def SetROI(self, bounds):
        """Set [x0, x1, y0, y1, bin] in unbinned pixels. Return applied ROI with both bin factors."""
        self._require_idle()
        if len(bounds) != 5:
            raise ValueError("SetROI requires [x0, x1, y0, y1, bin]")
        x0, x1, y0, y1, binning = bounds
        width, height = self._detector_size
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height and binning in (1, 2, 4)):
            raise ValueError(f"ROI must be within {width}×{height} with binning 1, 2, or 4")
        return self._sdk(self._apply_roi, x0, x1, y0, y1, binning)

    def _apply_roi(self, x0, x1, y0, y1, binning):
        self._camera.set_roi(x0, x1, y0, y1, binning, binning)
        self._sensor_roi = tuple(self._camera.get_roi())
        self._exposure_ms = self._read_exposure_ms()
        self._clear_frame_metadata()
        return self._sensor_roi

    @attribute(name="DetectorSize", dtype=(int,), max_dim_x=2)
    def detector_size(self):
        """Width and height of the full detector in unbinned pixels."""
        return self._detector_size

    @attribute(name="SensorROI", dtype=(int,), max_dim_x=6)
    def sensor_roi(self):
        """DCAM readback [x0, x1, y0, y1, x bin, y bin], with exclusive ends."""
        return self._sensor_roi

    @attribute(name="ExposureMs", dtype=float, access=AttrWriteType.READ_WRITE,
               fset="write_exposure_ms", unit="ms")
    def exposure_ms(self):
        """Actual DCAM exposure, including SDK rounding."""
        if self._exposure_ms is None:
            raise RuntimeError("OpenReadout before reading exposure")
        return self._exposure_ms

    def write_exposure_ms(self, value):
        self._require_idle()
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Exposure must be finite and positive")
        self._sdk(self._apply_exposure, value)

    def _apply_exposure(self, value):
        self._camera.set_exposure(value / 1000.0)
        self._exposure_ms = self._read_exposure_ms()

    def _read_exposure_ms(self):
        exposure = float(self._camera.get_exposure()) * 1000
        if not math.isfinite(exposure) or exposure <= 0:
            raise RuntimeError(f"Invalid exposure readback: {exposure} ms")
        return exposure

    @attribute(name="AcquisitionActive", dtype=bool)
    def acquisition_active(self):
        """Current SDK acquisition status. A fault can leave status unknown."""
        if self.get_state() == DevState.FAULT:
            raise RuntimeError("DCAM acquisition status is unverified after a fault")
        if self.get_state() == DevState.OFF:
            return False
        return self._sdk(self._camera.acquisition_in_progress)

    def _clear_frame_metadata(self):
        self._timestamp_us = -1
        self._frame_stamp = -1

    @attribute(name="Model", dtype=str)
    def model(self):
        return self._model

    @attribute(name="RawFrame", dtype=((DevUShort,),), max_dim_x=2048, max_dim_y=2048)
    def raw_frame(self):
        if self.get_state() != DevState.RUNNING:
            raise RuntimeError("StartLive before reading RawFrame")
        raw = self._sdk(self._latest_frame)
        if raw is None:
            raise RuntimeError("Waiting for a DCAM frame")
        return raw

    def _latest_frame(self):
        if self._sweep_head is not None:
            if self._sweep_frame is None:
                return None
            self._timestamp_us, self._frame_stamp, pixels = self._sweep_frame
            return pixels
        result = self._camera.read_newest_image(peek=True, return_info=True)
        if result is None:
            return None
        pixels, info = result
        self._validate_frame(pixels, info)
        result = pixels.copy(order="C")
        self._timestamp_us = int(info.timestamp_us)
        self._frame_stamp = int(info.framestamp)
        return result

    def _validate_frame(self, pixels, info):
        x0, x1, y0, y1, x_bin, y_bin = self._sensor_roi
        expected_shape = ((y1 - y0) // y_bin, (x1 - x0) // x_bin)
        if pixels.shape != expected_shape or pixels.dtype != np.dtype("uint16") or info is None:
            raise RuntimeError("Unexpected DCAM raw frame layout or metadata")

    @attribute(name="FrameTimestampUs", dtype=DevLong64)
    def frame_timestamp_us(self):
        """DCAM timestamp of the last successful RawFrame read, or -1."""
        return self._timestamp_us

    @attribute(name="FrameStamp", dtype=DevLong64)
    def frame_stamp(self):
        """DCAM stamp of the last successful RawFrame read, or -1."""
        return self._frame_stamp


if __name__ == "__main__":
    DS_HAMAMATSU_DCAM.run_server()
