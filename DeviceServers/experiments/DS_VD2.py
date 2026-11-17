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
TRIGGER_RATES_HZ = (5, 10)
RECORDING_PHASES = {"BRUIT", "BASE", "ABSORPTION"}


class DS_VD2(Device):
    """Own a VD2 Live session and the devices that it starts."""

    head_device = device_property(dtype=str, default_value="vd2/head/c13410")
    ccd_device = device_property(dtype=str, default_value="vd2/camera/dcam")
    dg645_device = device_property(dtype=str, default_value="manip/sync/DG645")
    kymera_device = device_property(dtype=str, default_value="manip/CR/ANDOR_KYMERA1")
    camera_pdu_device = device_property(dtype=str, default_value="manip/SD2/PDU_SD2")
    lamp_pdu_device = device_property(dtype=str, default_value="manip/VD2/PDU_VD2")

    def init_device(self):
        super().init_device()
        self._camera = None
        self._clock = None
        self._kymera = None
        self._time_range = "1 us"
        self._rate_hz = 5
        self._prepared = False
        self._optics = {}
        self._warmup_until = None
        self._warmup_frame = None
        self._recording_phase = None
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

    @classmethod
    def _verify_standby(cls, generator):
        if generator.state() != DevState.ON or cls._query(generator, "BURM?") != 0:
            raise RuntimeError("DG645 must be ON with Burst off")
        if cls._query(generator, "TSRC?") != 5:
            raise RuntimeError("DG645 must be in standby")

    @classmethod
    def _write_rate(cls, generator, rate):
        cls._verify_standby(generator)
        if cls._query(generator, "TRAT?") != rate:
            generator.command_inout("scpi_write", f"TRAT {rate}")
            if cls._query(generator, "TRAT?") != rate:
                raise RuntimeError("DG645 did not verify its trigger rate")

    @command(dtype_in=int, dtype_out=int)
    def SetRate(self, value):
        if value not in TRIGGER_RATES_HZ:
            raise ValueError("Choose 5 or 10 Hz")
        self._require_idle()
        if self._prepared:
            self._write_rate(self._proxy(self.dg645_device), value)
        self._rate_hz = value
        return value

    @command
    def Prepare(self):
        self._require_idle()
        dg = self._proxy(self.dg645_device)
        ky = self._proxy(self.kymera_device)
        if ky.state() != DevState.ON or ky.shutter != "Closed":
            raise RuntimeError("Verify Kymera is ON and the shutter is closed")
        if dg.state() != DevState.ON or self._query(dg, "BURM?") != 0:
            raise RuntimeError("DG645 must be ON with Burst off")
        if not self._prepared and self._query(dg, "TSRC?") != 5:
            self._set_clock(dg, 5)
        self._write_rate(dg, self._rate_hz)
        if self._prepared:
            verify_timing(dg, timing_for_range(self._time_range), live=True)
        else:
            self._set_time_range(self._time_range)
        self._read_optics(ky)
        self._prepared = True
        self._fault = ""
        self.set_state(DevState.ON)
        self.set_status("VD2 prepared; trigger in standby")

    @command
    def Unprepare(self):
        self.StopLive()
        self._require_idle()
        dg = self._proxy(self.dg645_device)
        if self._query(dg, "TSRC?") != 5:
            raise RuntimeError("Cannot verify DG645 standby; power retained")
        if self._outlet_power(self.camera_pdu_device):
            self._proxy(self.head_device).command_inout("Park")
        self._prepared = False
        self.set_status("VD2 unprepared")

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
        if not self._prepared:
            raise RuntimeError("Prepare VD2 before starting Live")
        self._set_time_range("1 us")
        self._start_live()

    def _read_optics(self, ky):
        self._optics = {"grating_index": int(ky.grating), "blaze": float(ky.blaze_wavelength_nm),
                        "wavelength_nm": float(ky.wavelength_nm)}

    def _start_live(self, *, dark=False):
        self._require_idle()
        if not self._prepared:
            raise RuntimeError("Prepare VD2 before starting Live")
        dg = self._proxy(self.dg645_device)
        self._verify_standby(dg)
        if self._query(dg, "TRAT?") != self._rate_hz:
            raise RuntimeError(f"DG645 rate did not verify at {self._rate_hz} Hz")
        verify_timing(dg, timing_for_range(self._time_range), live=True)
        camera = self._proxy(self.ccd_device, 30000)
        ky = self._proxy(self.kymera_device)
        if ky.shutter != "Closed":
            raise RuntimeError("Start VD2 with the Kymera shutter closed")
        self._read_optics(ky)
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
            if not dark:
                ky.shutter = "Open"
            if ky.shutter != ("Closed" if dark else "Open"):
                raise RuntimeError("Kymera shutter did not verify for acquisition")
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
        if not self._outlet_power(self.lamp_pdu_device):
            raise RuntimeError("Verify the VD2 flashlamp supply is ON")
        if self._camera is None:
            self._start_live()
        elif self.get_state() != DevState.RUNNING or not self._camera.AcquisitionActive:
            raise RuntimeError("Stop the current VD2 operation first")
        self._start_warmup()

    def _start_warmup(self):
        if self._warmup_until is not None:
            return
        self._warmup_frame = int(self._camera.SweepFrameCount)
        self._warmup_until = monotonic() + LAMP_WARMUP_S
        self.set_status("VD2 warming the flash lamp")

    @command(dtype_in=str, dtype_out=str)
    def StartPhase(self, phase):
        if phase not in RECORDING_PHASES:
            raise ValueError("Unknown VD2 recording phase")
        if self._recording_phase is not None:
            raise RuntimeError("A VD2 sequence is already running")
        if self._time_range != "1 us":
            raise RuntimeError("Direct recording currently requires the calibrated 1 us time axis")
        if phase != "BRUIT" and not self._outlet_power(self.lamp_pdu_device):
            raise RuntimeError("Verify the VD2 flashlamp supply is ON")
        if self._camera is not None:
            self.StopLive()
        self._start_live(dark=phase == "BRUIT")
        self._recording_phase = phase
        try:
            if phase != "BRUIT":
                self._start_warmup()
            return self.PhaseConfiguration()
        except Exception as exc:
            self._fail_live(exc)

    @command(dtype_out=str)
    def PhaseConfiguration(self):
        if self._recording_phase is None or self.get_state() != DevState.RUNNING:
            raise RuntimeError("VD2 has no active sequence")
        if not self._camera.AcquisitionActive or self._query(self._clock, "TSRC?") != 0:
            raise RuntimeError("VD2 synchronized sequence is no longer active")
        if self._query(self._clock, "TRAT?") != self._rate_hz or self._query(self._clock, "BURM?") != 0:
            raise RuntimeError("DG645 rate or burst changed during recording")
        optics = self._kymera.read_attributes(["grating", "wavelength_nm", "lines_per_mm", "blaze_wavelength_nm",
                                               "exit_mirror", "focus_mirror", "turret", "side_entry_iris", "shutter"])
        values = {item.name.lower(): item.value for item in optics}
        if values["shutter"] != ("Closed" if self._recording_phase == "BRUIT" else "Open"):
            raise RuntimeError("Kymera shutter changed during recording")
        delays = {name: self._clock.command_inout("scpi_query", f"DLAY? {channel}").strip()
                  for channel, name in enumerate("abcdefgh", 2)}
        return json.dumps({"phase": self._recording_phase, "time_range": self._time_range,
                           "rate_hz": self._rate_hz, "camera": json.loads(self._camera.ReadoutConfiguration()),
                           "kymera_device": self.kymera_device, "optics": values, "delays": delays})

    def _outlet_power(self, device):
        pdu = self._proxy(device)
        outlets = tuple(map(int, pdu.ids))
        states = tuple(map(int, pdu.states))
        if len(states) != len(outlets) or outlets.count(1) != 1 or states[outlets.index(1)] not in {0, 1}:
            raise RuntimeError(f"Invalid power readback from {device} outlet 1")
        return states[outlets.index(1)] == 1

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
        if not errors:
            self._recording_phase = None
        if errors:
            raise RuntimeError("Could not stop VD2. " + " | ".join(errors))

    @command(dtype_out=str)
    def GetState(self):
        state = str(self.get_state()).split(".")[-1]
        if state == "RUNNING" and (self._camera.state() != DevState.RUNNING or not self._camera.AcquisitionActive):
            return json.dumps({"state": "FAULT", "phase": "fault", "time_range": self._time_range,
                               "prepared": self._prepared, "trigger_rate_hz": self._rate_hz,
                               "frames": 0, "remaining_warmup_s": None, "error": str(self._camera.status())})
        acquired_frames = int(self._camera.SweepFrameCount) if state == "RUNNING" else 0
        phase = {"ON": "idle", "RUNNING": "live", "FAULT": "fault"}.get(state, state.lower())
        remaining = None
        if self._warmup_until is not None:
            remaining = max(0.0, self._warmup_until - monotonic())
            sufficient_frames = acquired_frames - self._warmup_frame >= LAMP_WARMUP_S * self._rate_hz
            phase = "warming" if remaining else ("measurement_ready" if sufficient_frames else "waiting_for_trigger")
        elif phase == "live" and not acquired_frames:
            phase = "waiting_for_trigger"
        return json.dumps({"state": state, "phase": phase, "time_range": self._time_range,
                           "frames": acquired_frames, "remaining_warmup_s": remaining,
                           "prepared": self._prepared, "trigger_rate_hz": self._rate_hz,
                           "optics": self._optics, "error": self._fault})


if __name__ == "__main__":
    DS_VD2.run_server()
