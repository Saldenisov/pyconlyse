"""Coordinate the direct VD2 optical instruments without HPD-TA."""

import json
import math
from time import monotonic

from tango import DevState, DeviceProxy
from tango.server import Device, command, device_property

from DeviceServers.instruments.dg645.vd2_timing import apply_timing, timing_for_range, verify_timing


SENSOR_ROI = (352, 1632, 516, 1532, 2)
GRATING_BLAZE_NM = {1: 300, 2: 800, 3: 500}
LAMP_WARMUP_S = 10
WARMUP_FRAME_COUNT = LAMP_WARMUP_S * 5


class DS_VD2(Device):
    """Own a VD2 Live session and the devices that it starts."""

    head_device = device_property(dtype=str, default_value="vd2/head/c13410")
    ccd_device = device_property(dtype=str, default_value="vd2/camera/dcam")
    dg645_device = device_property(dtype=str, default_value="manip/sync/DG645")
    kymera_device = device_property(dtype=str, default_value="manip/CR/ANDOR_KYMERA1")
    lamp_pdu_device = device_property(dtype=str, default_value="manip/VD2/PDU_VD2")

    def init_device(self):
        super().init_device()
        self._camera = None
        self._clock = None
        self._kymera = None
        self._time_range = "1 us"
        self._optics = {}
        self._warmup_until = None
        self._warmup_frame = None
        self._fault = ""
        self.set_state(DevState.ON)
        self.set_status("VD2 idle")

    def delete_device(self):
        try:
            self._release()
        finally:
            super().delete_device()

    @staticmethod
    def _proxy(name, timeout=6000):
        device = DeviceProxy(name)
        device.set_timeout_millis(timeout)
        return device

    def _require_idle(self):
        if any(device is not None for device in (self._camera, self._clock, self._kymera)):
            raise RuntimeError("Stop the current VD2 operation first")
        if self._proxy(self.ccd_device).state() != DevState.OFF:
            raise RuntimeError("The VD2 CCD is already in use")

    @staticmethod
    def _query(generator, name):
        return float(generator.command_inout("scpi_query", name))

    @classmethod
    def _set_clock(cls, generator, source):
        generator.command_inout("scpi_write", f"TSRC {source}")
        if cls._query(generator, "TSRC?") != source:
            raise RuntimeError("DG645 did not verify its trigger source")

    @command(dtype_in=str, dtype_out=str)
    def SetTimeRange(self, value):
        return self._set_time_range(value)

    def _set_time_range(self, value):
        self._require_idle()
        profile = timing_for_range(value)
        head = self._proxy(self.head_device)
        dg = self._proxy(self.dg645_device)
        if dg.state() != DevState.ON or self._query(dg, "BURM?") != 0:
            raise RuntimeError("DG645 must be ON with Burst off")
        actual = head.command_inout("ConfigureSweep", profile.time_range)
        if actual != profile.time_range:
            raise RuntimeError(f"C13410 did not verify {profile.time_range}")
        apply_timing(dg, profile)
        self._time_range = actual
        return actual

    @command(dtype_in=float, dtype_out=float)
    def SetWavelength(self, value):
        self._require_idle()
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Choose a positive, finite wavelength")
        ky = self._proxy(self.kymera_device, 30000)
        if ky.shutter != "Closed":
            raise RuntimeError("Close the Kymera shutter before changing wavelength")
        ky.wavelength_nm = value
        actual = float(ky.wavelength_nm)
        if not math.isclose(value, actual, abs_tol=.1):
            raise RuntimeError("Kymera wavelength did not verify")
        self._optics["wavelength_nm"] = actual
        return actual

    @command(dtype_in=int, dtype_out=int)
    def SetGrating(self, value):
        self._require_idle()
        if value not in GRATING_BLAZE_NM:
            raise ValueError("Choose an installed Kymera grating (1, 2, or 3)")
        ky = self._proxy(self.kymera_device, 65000)
        if ky.shutter != "Closed":
            raise RuntimeError("Close the Kymera shutter before changing grating")
        ky.grating = value
        if int(ky.grating) != value or not math.isclose(
            float(ky.blaze_wavelength_nm), GRATING_BLAZE_NM[value], abs_tol=.01
        ):
            raise RuntimeError("Kymera's grating and blaze did not verify")
        self._optics.update(grating_index=value, blaze=GRATING_BLAZE_NM[value],
                            wavelength_nm=float(ky.wavelength_nm))
        return value

    @command
    def StartLive(self):
        self._start_live()

    @command
    def StartAlignment(self):
        self._set_time_range("1 us")
        self._start_live()

    def _start_live(self):
        self._require_idle()
        dg = self._proxy(self.dg645_device)
        if dg.state() != DevState.ON:
            raise RuntimeError("DG645 is not ON")
        source = self._query(dg, "TSRC?")
        if source not in {0, 1, 2, 5} or self._query(dg, "BURM?") != 0:
            raise RuntimeError("Select internal or external triggering with Burst off")
        if source in {0, 5} and self._query(dg, "TRAT?") != 5:
            raise RuntimeError("Set the DG645 internal rate to 5 Hz")
        verify_timing(dg, timing_for_range(self._time_range))
        camera = self._proxy(self.ccd_device, 30000)
        ky = self._proxy(self.kymera_device)
        if ky.shutter != "Closed":
            raise RuntimeError("Start VD2 with the Kymera shutter closed")
        self._optics = {"grating_index": int(ky.grating), "blaze": float(ky.blaze_wavelength_nm),
                        "wavelength_nm": float(ky.wavelength_nm)}
        self._camera = camera
        self._kymera = ky
        try:
            camera.command_inout("OpenReadout")
            roi = tuple(camera.command_inout("SetROI", SENSOR_ROI))
            if roi != (*SENSOR_ROI, SENSOR_ROI[-1]):
                raise RuntimeError("CCD ROI did not verify")
            camera.ExposureMs = 10.0
            camera.command_inout("StartSynchronizedLiveAt", self._time_range)
            if camera.state() != DevState.RUNNING or not camera.AcquisitionActive:
                raise RuntimeError("CCD did not confirm synchronized Live")
            ky.shutter = "Open"
            if ky.shutter != "Open":
                raise RuntimeError("Kymera shutter did not verify open")
            if source == 5:
                self._clock = dg
                self._set_clock(dg, 0)
        except Exception as exc:
            self._fail_live(exc)
        self._fault = ""
        self.set_state(DevState.RUNNING)
        self.set_status("VD2 synchronized Live")

    def _fail_live(self, error):
        try:
            self._release()
        except RuntimeError as cleanup:
            error = RuntimeError(f"{error}. {cleanup}")
        self._fault = str(error)
        self.set_state(DevState.FAULT)
        self.set_status(self._fault)
        raise error

    @command
    def PrepareMeasurement(self):
        """Warm the powered flash lamp at the selected clock before measuring."""
        lamp = self._proxy(self.lamp_pdu_device)
        outlets = tuple(map(int, lamp.ids))
        states = tuple(map(int, lamp.states))
        if len(states) != len(outlets) or outlets.count(1) != 1 or states[outlets.index(1)] != 1:
            raise RuntimeError("Verify the VD2 flashlamp supply is ON")
        if self._camera is None:
            self._start_live()
        elif self.get_state() != DevState.RUNNING or not self._camera.AcquisitionActive:
            raise RuntimeError("Stop the current VD2 operation first")
        if self._warmup_until is not None:
            return
        self._warmup_frame = int(self._camera.SweepFrameCount)
        self._warmup_until = monotonic() + LAMP_WARMUP_S
        self.set_status("VD2 warming the flash lamp")

    @command
    def StopLive(self):
        try:
            self._release()
        except RuntimeError as exc:
            self._fault = str(exc)
            self.set_state(DevState.FAULT)
            self.set_status(self._fault)
            raise
        self._fault = ""
        self.set_state(DevState.ON)
        self.set_status("VD2 idle")

    def _release(self):
        errors = []
        if self._clock is not None:
            try:
                if self._query(self._clock, "TSRC?") != 5:
                    self._set_clock(self._clock, 5)
                self._clock = None
            except Exception as exc:
                errors.append(f"DG645: {exc}")
        if self._kymera is not None:
            try:
                if self._kymera.shutter != "Closed":
                    self._kymera.shutter = "Closed"
                if self._kymera.shutter != "Closed":
                    raise RuntimeError("shutter did not verify closed")
                self._kymera = None
            except Exception as exc:
                errors.append(f"Kymera: {exc}")
        if self._camera is not None:
            try:
                self._camera.command_inout("CloseReadout")
                if self._camera.state() != DevState.OFF:
                    raise RuntimeError("CCD did not verify OFF")
                self._camera = None
            except Exception as exc:
                errors.append(f"DCAM: {exc}")
        self._warmup_until = None
        self._warmup_frame = None
        if errors:
            raise RuntimeError("Could not stop VD2. " + " | ".join(errors))

    @command(dtype_out=str)
    def GetState(self):
        state = str(self.get_state()).split(".")[-1]
        if state == "RUNNING" and (self._camera.state() != DevState.RUNNING or not self._camera.AcquisitionActive):
            return json.dumps({"state": "FAULT", "phase": "fault", "time_range": self._time_range,
                               "frames": 0, "remaining_warmup_s": None, "error": str(self._camera.status())})
        acquired_frames = int(self._camera.SweepFrameCount) if state == "RUNNING" else 0
        phase = {"ON": "idle", "RUNNING": "live", "FAULT": "fault"}.get(state, state.lower())
        remaining = None
        if self._warmup_until is not None:
            remaining = max(0.0, self._warmup_until - monotonic())
            sufficient_frames = acquired_frames - self._warmup_frame >= WARMUP_FRAME_COUNT
            phase = "warming" if remaining else ("measurement_ready" if sufficient_frames else "waiting_for_trigger")
        elif phase == "live" and not acquired_frames:
            phase = "waiting_for_trigger"
        return json.dumps({"state": state, "phase": phase, "time_range": self._time_range,
                           "frames": acquired_frames, "remaining_warmup_s": remaining,
                           "optics": self._optics, "error": self._fault})


if __name__ == "__main__":
    DS_VD2.run_server()
