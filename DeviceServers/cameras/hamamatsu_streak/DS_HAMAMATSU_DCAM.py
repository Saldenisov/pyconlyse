"""Standalone Tango device for the C13440 USB sensor in a streak system."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
from tango import DevLong64, DevState, DevUShort
from tango.server import Device, attribute, command

from DeviceServers.cameras.hamamatsu_streak.dcam_readout_probe import (
    READOUT_MODEL,
    open_readout,
)


SDK_TIMEOUT_S = 5.0


class DS_HAMAMATSU_DCAM(Device):
    """Explicitly open, run and close a direct DCAM readout session."""

    def init_device(self):
        super().init_device()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dcam-tango")
        self._pending = None
        self._camera = None
        self._model = ""
        self._prior_trigger = None
        self._timestamp_us = -1
        self._frame_stamp = -1
        self.set_state(DevState.OFF)
        self.set_status("DCAM closed. Use OpenReadout to connect.")

    def delete_device(self):
        try:
            # Teardown, including Tango Init, waits for release before reinitializing.
            self._worker.submit(self._close).result()
        finally:
            self._worker.shutdown(wait=True)
            super().delete_device()

    def _sdk(self, operation):
        # Never enqueue a request behind a native call with an unresolved outcome.
        if self._pending is not None and not self._pending.done():
            raise RuntimeError("Previous DCAM call is still running")
        self._pending = self._worker.submit(operation)
        try:
            return self._pending.result(timeout=SDK_TIMEOUT_S)
        except TimeoutError as exc:
            self.set_state(DevState.FAULT)
            message = f"DCAM {operation.__name__} timed out after {SDK_TIMEOUT_S:g} s"
            self.set_status(message)
            raise RuntimeError(message) from exc
        except Exception as exc:
            self.set_state(DevState.FAULT)
            self.set_status(f"DCAM {operation.__name__} failed: {exc}")
            raise

    @command
    def OpenReadout(self):
        if self.get_state() == DevState.FAULT:
            raise RuntimeError("CloseReadout must resolve the previous DCAM failure")
        if self._camera is None:
            self._sdk(self._open)
            self.set_state(DevState.ON)
            self.set_status("DCAM connected. Sensor acquisition idle.")

    def _open(self):
        camera, info = open_readout()
        self._camera = camera
        if info.model.strip().upper() != READOUT_MODEL:
            camera.close()
            self._camera = None
            raise RuntimeError(f"Expected {READOUT_MODEL}, got {info.model}")
        self._model = info.model

    @command
    def CloseReadout(self):
        self._sdk(self._close)
        self.set_state(DevState.OFF)
        self.set_status("DCAM closed.")

    def _close(self):
        if self._camera is not None:
            try:
                self._stop()
            finally:
                self._camera.close()
                self._camera = None
                self._prior_trigger = None
                self._model = ""
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
    def StopLive(self):
        if self._camera is not None:
            self._sdk(self._stop)
            if self.get_state() == DevState.RUNNING:
                self.set_state(DevState.ON)
                self.set_status("DCAM connected. Sensor acquisition idle.")

    def _stop(self):
        if self._prior_trigger is not None:
            self._camera.stop_acquisition()
            prior_trigger = self._prior_trigger
            if self._camera.set_trigger_mode(prior_trigger) != prior_trigger:
                raise RuntimeError("DCAM previous trigger mode did not verify")
            self._prior_trigger = None
        self._clear_frame_metadata()

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
        result = self._camera.read_newest_image(peek=True, return_info=True)
        if result is None:
            return None
        pixels, info = result
        if (pixels.ndim != 2 or not all(0 < size <= 2048 for size in pixels.shape)
                or pixels.dtype != np.dtype("uint16") or info is None):
            raise RuntimeError("Unexpected DCAM raw frame layout or metadata")
        result = pixels.copy(order="C")
        self._timestamp_us = int(info.timestamp_us)
        self._frame_stamp = int(info.framestamp)
        return result

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
