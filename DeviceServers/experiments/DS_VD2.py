"""Coordinate the direct VD2 optical instruments without HPD-TA."""

import json
import math
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from time import monotonic

from tango import DevState, DeviceProxy
from tango.server import Device, command, device_property

from DeviceServers.instruments.dg645.vd2_timing import apply_timing, timing_for_range, verify_timing


SENSOR_ROI = (352, 1632, 516, 1532, 2)
GRATING_BLAZE_NM = {1: 300, 2: 800, 3: 500}
LAMP_WARMUP_S = 10
TRIGGER_RATES_HZ = (5, 10)
LIVE_TRIGGER_SOURCES = {"Internal": 0, "Ext. rising": 1, "Ext. falling": 2, "Standby": 5}
DG_CHANNELS = dict(zip("abcdefgh", range(2, 10)))
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
        self._manual_clock = None
        self._kymera = None
        self._time_range = "1 us"
        self._rate_hz = 5
        self._live_trigger_source = 0
        self._live_exposure_ms = 10.0
        self._prepared = False
        self._dark_checkout = False
        self._focus_preview = False
        self._optics = {}
        self._warmup_until = None
        self._warmup_frame = None
        self._recording_phase = None
        self._paired_source = None
        self._paired_dg_readbacks = None
        self._preview_configuration = None
        self._preview_first_frame = 0
        self._timing_values = {}
        self._camera_values = {}
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
        if cls._query(generator, "TRAT?") != rate:
            generator.command_inout("scpi_write", f"TRAT {rate}")
            if cls._query(generator, "TRAT?") != rate:
                raise RuntimeError("DG645 did not verify its trigger rate")

    def _output_state(self, generator):
        if generator.state() != DevState.ON:
            raise RuntimeError("DG645 is not ON")
        source = self._query(generator, "TSRC?")
        rate = self._query(generator, "TRAT?")
        if not math.isfinite(rate) or rate <= 0:
            raise RuntimeError("DG645 did not return a valid internal trigger rate")
        return {"enabled": source == 0 if source in {0, 5} else None, "rate_hz": rate}

    @command(dtype_out=str)
    def GetDg645Output(self):
        return json.dumps(self._output_state(self._proxy(self.dg645_device)))

    @command(dtype_in=bool, dtype_out=str)
    def SetDg645Output(self, enabled):
        if (self._camera is not None or self._clock is not None or self._kymera is not None
                or self._recording_phase is not None or self._warmup_until is not None
                or self.get_state() == DevState.RUNNING):
            raise RuntimeError("Stop VD2 Live or finish the measurement before changing manual DG645 Output")
        if enabled and (not self._prepared or self._dark_checkout or self.get_state() != DevState.ON):
            raise RuntimeError("Manual DG645 Output requires standard VD2 preparation")
        generator = self._proxy(self.dg645_device)
        previous = self._output_state(generator)
        if previous["enabled"] is None:
            raise RuntimeError("DG645 is using another trigger source")
        if enabled:
            if self._query(generator, "BURM?") != 0:
                raise RuntimeError("Turn off DG645 Burst before enabling manual Output")
            if previous["rate_hz"] != self._rate_hz:
                raise RuntimeError("DG645 rate does not match the configured VD2 rate")
            # Retain ownership even if the write succeeds but its readback fails.
            self._manual_clock = generator
        if previous["enabled"] != enabled:
            self._set_clock(generator, 0 if enabled else 5)
        if not enabled:
            self._manual_clock = None
        self._timing_values.update(delay_trigger_mode="Internal" if enabled else "Standby",
                                   dg_output="On" if enabled else "Standby")
        return json.dumps({"enabled": enabled, "rate_hz": previous["rate_hz"]})

    def _stop_manual_output(self):
        if self._manual_clock is not None:
            self._set_clock(self._manual_clock, 5)
            self._manual_clock = None
            self._timing_values.update(delay_trigger_mode="Standby", dg_output="Standby")

    @command(dtype_in=int, dtype_out=int)
    def SetRate(self, value):
        if value not in TRIGGER_RATES_HZ:
            raise ValueError("Choose 5 or 10 Hz")
        live = self._adjusting_live()
        if live or self._prepared:
            generator = self._clock if live else self._proxy(self.dg645_device)
            if not live:
                self._verify_standby(generator)
            self._write_rate(generator, value)
        self._rate_hz = value
        self._timing_values["delay_repetition_rate"] = value
        return value

    def _adjusting_live(self):
        if self._recording_phase is not None or self._warmup_until is not None:
            raise RuntimeError("Finish the VD2 measurement before changing Live settings")
        if self.get_state() == DevState.RUNNING:
            if self._focus_preview:
                raise RuntimeError("Stop Focus preview before changing synchronized Live settings")
            if self._camera is None or self._clock is None or not self._camera.AcquisitionActive:
                raise RuntimeError("VD2 Live is no longer active. Stop Live and retry.")
            return True
        self._require_idle()
        return False

    @command(dtype_in=(str,), dtype_out=float)
    def SetDelay(self, selection):
        if len(selection) != 2:
            raise ValueError("Supply a DG645 channel and a delay in seconds")
        name, requested = selection
        if name not in DG_CHANNELS:
            raise ValueError("Select DG645 channel A–H")
        try:
            seconds = Decimal(requested)
        except InvalidOperation:
            raise ValueError("Enter a numerical DG645 delay in seconds") from None
        if not seconds.is_finite() or seconds < 0 or seconds > 2000:
            raise ValueError("DG645 delay must be between 0 and 2000 seconds")
        live = self._adjusting_live()
        dg = self._clock if live else self._proxy(self.dg645_device)
        channel = DG_CHANNELS[name]
        reference, before = dg.command_inout("scpi_query", f"DLAY? {channel}").split(",")
        ref = int(reference)
        if Decimal(before) != seconds:
            dg.command_inout("scpi_write", f"DLAY {channel},{ref},{seconds:f}")
        actual_reference, actual = dg.command_inout("scpi_query", f"DLAY? {channel}").split(",")
        if int(actual_reference) != ref or abs(Decimal(actual) - seconds) > Decimal("5e-12"):
            raise RuntimeError(f"DG645 delay {name.upper()} did not verify. Check the delay readback.")
        self._timing_values[f"delay_{name}"] = float(actual)
        if live:
            if self._preview_configuration is not None:
                self._preview_configuration["dg_delay_seconds"] = {
                    key: self._timing_values[f"delay_{key}"] for key in DG_CHANNELS
                }
            self._mark_preview_changed()
        return float(actual)

    @command(dtype_in=str, dtype_out=str)
    def SetLiveTriggerSource(self, value):
        if value not in LIVE_TRIGGER_SOURCES:
            raise ValueError("Choose Internal, Ext. rising, Ext. falling or Standby")
        source = LIVE_TRIGGER_SOURCES[value]
        if self._adjusting_live():
            self._set_clock(self._clock, source)
            self._timing_values.update(delay_trigger_mode=value, dg_output="Standby" if source == 5 else "On")
            self._mark_preview_changed()
        self._live_trigger_source = source
        self._timing_values["live_trigger_selection"] = value
        return value

    def _mark_preview_changed(self):
        self._preview_first_frame = int(self._camera.SweepFrameCount) + 3

    @contextmanager
    def _reconfigure_preview(self):
        live = self._adjusting_live()
        if live:
            streak_open = self._optics["streak_shutter"] == "Open"
            kymera_open = self._optics["spectrograph_shutter"] == "Open"
            gain = self._camera_values.get("mcp_gain", 0)
            self.StopLive()
        yield
        if live:
            self._start_live(streak_open=streak_open, kymera_open=kymera_open)
            if streak_open and gain:
                self.SetMcpGain(gain)

    @command
    def Prepare(self):
        self._require_idle()
        self._stop_manual_output()
        dg = self._proxy(self.dg645_device)
        ky = self._proxy(self.kymera_device)
        if ky.state() != DevState.ON or ky.shutter not in {"Closed", "Open"}:
            raise RuntimeError("Verify Kymera is ON and its shutter state is known")
        if dg.state() != DevState.ON or self._query(dg, "BURM?") != 0:
            raise RuntimeError("DG645 must be ON with Burst off")
        if not self._prepared and self._query(dg, "TSRC?") != 5:
            self._set_clock(dg, 5)
        self._verify_standby(dg)
        self._write_rate(dg, self._rate_hz)
        if self._prepared:
            verify_timing(dg, timing_for_range(self._time_range), live=True)
        else:
            self._set_time_range(self._time_range)
        self._read_optics(ky)
        self._read_timing_values(dg)
        self._timing_values["live_trigger_selection"] = next(
            name for name, source in LIVE_TRIGGER_SOURCES.items() if source == self._live_trigger_source
        )
        self._camera_values.setdefault("live_exposure_time", f"{self._live_exposure_ms:.9g} ms")
        actual_mode = self._proxy(self.head_device).command_inout("ReadMode")
        self._camera_values.update(streak_mode=actual_mode, gate_mode="Normal", mcp_gain=0, streak_trigger_mode="Single")
        self._prepared = True
        self._fault = ""
        self.set_state(DevState.ON)
        self.set_status("VD2 prepared; trigger in standby")

    @command
    def PrepareDarkCheckout(self):
        self._verify_dark_lamp()
        self._require_idle()
        self._proxy(self.head_device).command_inout("SetShutter", "Closed")
        self.Prepare()
        self.SetStreakMode("Focus")
        self._dark_checkout = True

    @command
    def PrepareStandard(self):
        self.Prepare()
        self._dark_checkout = False

    def _verify_dark_lamp(self):
        if self._outlet_power(self.lamp_pdu_device):
            raise RuntimeError("Switch the VD2 flashlamp supply off before dark checkout")

    @command
    def Unprepare(self):
        self._prepared = False
        self._dark_checkout = False
        self._stop_live(keep_shutters=False)
        camera = self._proxy(self.ccd_device, 30000)
        try:
            if self._outlet_power(self.camera_pdu_device, outlet=2):
                dg = self._proxy(self.dg645_device)
                if self._query(dg, "TSRC?") != 5:
                    self._set_clock(dg, 5)
        finally:
            if camera.state() != DevState.OFF:
                camera.command_inout("CloseReadout")
            if camera.state() != DevState.OFF:
                raise RuntimeError("Cannot verify DCAM handle released. Retry Unprepare before opening HPD-TA.")
        if self._outlet_power(self.camera_pdu_device):
            self._proxy(self.head_device).command_inout("Park")
            self._optics["streak_shutter"] = "Closed"
            self._camera_values.update(streak_mode="Focus", mcp_gain=0, streak_trigger_status="Idle")
        kymera = self._proxy(self.kymera_device)
        state = kymera.state()
        if state == DevState.ON:
            self._set_kymera_shutter(kymera, "Closed")
        elif state != DevState.OFF:
            raise RuntimeError("Kymera shutter state unverified; power retained")
        self.set_status("VD2 unprepared")

    @command(dtype_in=str, dtype_out=str)
    def SetTimeRange(self, value):
        profile = timing_for_range(value)
        if profile.time_range == self._time_range:
            return self._time_range
        with self._reconfigure_preview():
            self._proxy(self.head_device).command_inout("SetShutter", "Closed")
            self._optics["streak_shutter"] = "Closed"
            actual = self._set_time_range(value)
        return actual

    @command(dtype_in=str, dtype_out=str)
    def SetStreakMode(self, value):
        if self._adjusting_live():
            raise RuntimeError("Stop Live before changing the streak camera mode")
        if value == "Focus":
            self._proxy(self.head_device).command_inout("Park")
            self._optics["streak_shutter"] = "Closed"
            self._camera_values["mcp_gain"] = 0
        elif value == "Operate":
            self._set_time_range(self._time_range)
        else:
            raise ValueError("Choose Focus or Operate")
        self._camera_values["streak_mode"] = value
        return value

    @command(dtype_in=float, dtype_out=str)
    def SetLiveExposure(self, value):
        if not math.isfinite(value) or not 1 <= value <= 25:
            raise ValueError("VD2 Live exposure must be between 1 and 25 ms")
        with self._reconfigure_preview():
            self._live_exposure_ms = value
            self._camera_values["live_exposure_time"] = f"{value:.9g} ms"
        return self._camera_values["live_exposure_time"]

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
        self._timing_values["delay_e"] = float(profile.delay_e_ms) / 1000
        self._time_range = actual
        return actual

    @command(dtype_in=float, dtype_out=float)
    def SetWavelength(self, value):
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Choose a positive, finite wavelength")
        with self._move_kymera(30000) as ky:
            ky.wavelength_nm = value
            actual = float(ky.wavelength_nm)
            if not math.isclose(value, actual, rel_tol=0, abs_tol=.1):
                raise RuntimeError("Kymera wavelength did not verify")
        return actual

    @command(dtype_in=int, dtype_out=int)
    def SetGrating(self, value):
        if value not in GRATING_BLAZE_NM:
            raise ValueError("Choose an installed Kymera grating (1, 2, or 3)")
        with self._move_kymera(65000) as ky:
            ky.grating = value
            if int(ky.grating) != value or not math.isclose(
                float(ky.blaze_wavelength_nm), GRATING_BLAZE_NM[value], rel_tol=0, abs_tol=.01
            ):
                raise RuntimeError("Kymera's grating and blaze did not verify")
        return value

    @contextmanager
    def _move_kymera(self, timeout):
        ky = self._kymera_for_adjustment(timeout)
        try:
            initial_shutter = ky.shutter
        except Exception as exc:
            self._optics.pop("spectrograph_shutter", None)
            raise RuntimeError("Cannot read the Kymera shutter. Refresh the instrument status and retry.") from exc
        if initial_shutter not in {"Open", "Closed"}:
            raise RuntimeError("Select Open or Closed on the Kymera shutter before changing the optics")
        self._preview_configuration = None
        try:
            self._set_kymera_shutter(ky, "Closed")
        except Exception as exc:
            self._optics.pop("spectrograph_shutter", None)
            raise RuntimeError("Could not confirm the Kymera shutter closed. Check the shutter and retry.") from exc
        try:
            yield ky
            optics = self._read_optics(ky)
        except Exception as exc:
            for name in ("wavelength_nm", "grating_index", "blaze"):
                self._optics.pop(name, None)
            raise RuntimeError("Kymera did not confirm the new setting. Its shutter was left closed.") from exc
        if initial_shutter == "Open":
            try:
                optics["shutter"] = self._set_kymera_shutter(ky, "Open")
            except Exception as exc:
                self._optics.pop("spectrograph_shutter", None)
                raise RuntimeError("Kymera moved, but shutter reopening is unverified. Check the shutter.") from exc
        try:
            self._refresh_preview_configuration(optics)
        except Exception as exc:
            raise RuntimeError("Kymera settings changed. Live calibration is unavailable. Restart Live to retry.") from exc

    def _kymera_for_adjustment(self, timeout=6000):
        if self._recording_phase is not None or self._warmup_until is not None:
            raise RuntimeError("Finish the VD2 measurement before adjusting Kymera")
        if self.get_state() != DevState.RUNNING:
            self._require_idle()
        ky = self._proxy(self.kymera_device, timeout)
        if ky.state() != DevState.ON:
            raise RuntimeError("Kymera must be ON before adjusting its controls")
        return ky

    def _refresh_preview_configuration(self, optics):
        if self._camera is not None and not self._focus_preview:
            configuration = self._read_calibration_configuration(optics)
            # Skip an in-flight exposure and allow for frame publication after the counter advances.
            self._mark_preview_changed()
            self._preview_configuration = configuration

    @command
    def StartLive(self):
        if self._read_head_mode() == "Focus":
            self._start_focus_preview()
            return
        self._start_live(streak_open=False, kymera_open=False)

    @command
    def StartLiveWithShutters(self):
        if self._read_head_mode() != "Operate":
            raise RuntimeError("Select Operate before opening the shutters for Live")
        self._start_live()

    @command
    def StartAlignment(self):
        if not self._prepared:
            raise RuntimeError("Prepare VD2 before starting Live")
        if self._read_head_mode() == "Focus":
            self._start_focus_preview()
            return
        if self._time_range != "1 us":
            self.SetTimeRange("1 us")
        self._start_live(streak_open=False, kymera_open=False)

    @command
    def StartAlignmentWithShutters(self):
        if self._read_head_mode() != "Operate":
            raise RuntimeError("Select Operate before opening the shutters for Live")
        if self._time_range != "1 us":
            self.SetTimeRange("1 us")
        self._start_live()

    def _read_head_mode(self):
        self._require_idle()
        if not self._prepared:
            raise RuntimeError("Prepare VD2 before starting Live")
        return self._proxy(self.head_device).command_inout("ReadMode")

    def _start_focus_preview(self):
        if self._dark_checkout:
            self._verify_dark_lamp()
        self._stop_manual_output()
        dg = self._proxy(self.dg645_device)
        self._verify_standby(dg)
        ky = self._proxy(self.kymera_device)
        self._proxy(self.head_device).command_inout("SetShutter", "Closed")
        self._optics["streak_shutter"] = "Closed"
        self._set_kymera_shutter(ky, "Closed")
        self._camera = camera = self._proxy(self.ccd_device, 30000)
        self._kymera = ky
        self._clock = dg
        try:
            camera.command_inout("OpenReadout")
            if tuple(camera.command_inout("SetROI", SENSOR_ROI)) != (*SENSOR_ROI, SENSOR_ROI[-1]):
                raise RuntimeError("CCD ROI did not verify")
            camera.ExposureMs = self._live_exposure_ms
            camera.command_inout("StartLive")
            if camera.state() != DevState.RUNNING or not camera.AcquisitionActive:
                raise RuntimeError("CCD did not confirm Focus preview")
            self._camera_values.update(streak_mode="Focus", streak_trigger_status="Internal",
                                       mcp_gain=0, live_mcp_gain_max=0,
                                       live_exposure_time=f"{camera.ExposureMs:.9g} ms")
        except Exception as exc:
            self._fail_live(exc)
        self._focus_preview = True
        self._fault = ""
        self.set_state(DevState.RUNNING)
        self.set_status("VD2 Focus preview; shutters closed")

    def _read_optics(self, ky):
        values = self._read_kymera(ky)
        self._optics.update(grating_index=int(values["grating"]), blaze=float(values["blaze_wavelength_nm"]),
                            wavelength_nm=float(values["wavelength_nm"]), exit_mirror=values["exit_mirror"],
                            focus_mirror=values["focus_mirror"], slit_width_um=values["active_input_slit_um"],
                            spectrograph_shutter=values["shutter"], ruling=values["lines_per_mm"])
        return values

    @staticmethod
    def _read_kymera(ky):
        names = ["grating", "wavelength_nm", "lines_per_mm", "blaze_wavelength_nm", "exit_mirror",
                 "focus_mirror", "turret", "side_entry_iris", "shutter", "active_input_slit_um"]
        return {item.name.lower(): item.value for item in ky.read_attributes(names)}

    def _read_timing_values(self, dg):
        delays = {f"delay_{name}": float(dg.command_inout("scpi_query", f"DLAY? {channel}").split(",")[1])
                  for channel, name in enumerate("abcdefgh", 2)}
        source = int(self._query(dg, "TSRC?"))
        mode = {0: "Internal", 1: "Ext. rising", 2: "Ext. falling", 5: "Standby"}.get(source, f"Source {source}")
        self._timing_values.update(delays, delay_repetition_rate=self._query(dg, "TRAT?"),
                                   delay_trigger_mode=mode, dg_output="Standby" if source == 5 else "On",
                                   delay_burst_mode="On" if self._query(dg, "BURM?") else "Off")

    @command(dtype_out=str)
    def RefreshInstrumentValues(self):
        ky = self._proxy(self.kymera_device)
        dg = self._proxy(self.dg645_device)
        if ky.state() == DevState.ON:
            self._read_optics(ky)
        if dg.state() == DevState.ON:
            self._read_timing_values(dg)
        return self.GetState()

    def _set_kymera_shutter(self, kymera, value):
        if value not in {"Open", "Closed"}:
            raise ValueError("Choose Open or Closed")
        if kymera.shutter != value:
            kymera.shutter = value
        if kymera.shutter != value:
            raise RuntimeError("Kymera shutter did not verify")
        self._optics["spectrograph_shutter"] = value
        return value

    @command(dtype_in=str, dtype_out=str)
    def SetSpectrographShutter(self, value):
        if value not in {"Open", "Closed"}:
            raise ValueError("Choose Open or Closed")
        ky = self._kymera_for_adjustment()
        if self._preview_configuration is None:
            return self._set_kymera_shutter(ky, value)
        self._preview_configuration = None
        actual = self._set_kymera_shutter(ky, value)
        self._refresh_preview_configuration(self._read_optics(ky))
        return actual

    @command(dtype_in=int, dtype_out=int)
    def SetMcpGain(self, value):
        if self._recording_phase is not None or self._warmup_until is not None:
            raise RuntimeError("Finish the VD2 measurement before adjusting II-Gain")
        if self.get_state() != DevState.RUNNING or self._camera is None:
            raise RuntimeError("Start VD2 Live before adjusting II-Gain")
        if self._preview_configuration is None:
            raise RuntimeError("Wait for verified Live settings before adjusting II-Gain")
        limit = int(self._camera.LiveMcpGainMax)
        if value < 0 or value > limit:
            raise ValueError("II-Gain is outside the configured VD2 Live range")
        optics = self._preview_configuration["optics"]
        self._preview_configuration = None
        try:
            actual = int(self._camera.command_inout("SetLiveMcpGain", value))
            if actual != value:
                raise RuntimeError("DCAM returned a different II-Gain")
            self._refresh_preview_configuration(optics)
        except Exception as exc:
            self._fail_live(RuntimeError(f"Could not confirm II-Gain. VD2 Live stopped. {exc}"))
        self._camera_values["mcp_gain"] = actual
        return actual

    @command(dtype_in=str, dtype_out=str)
    def SetStreakShutter(self, value):
        if value not in {"Open", "Closed"}:
            raise ValueError("Choose Open or Closed")
        if self._adjusting_live():
            if value == "Open" and self._camera_values.get("mcp_gain") != 0:
                raise RuntimeError("Set II-Gain to zero before opening the streak shutter")
            try:
                result = self._camera.command_inout("SetLiveStreakShutter", value)
                self._mark_preview_changed()
            except Exception as exc:
                self._fail_live(exc)
        else:
            result = self._proxy(self.head_device).command_inout("SetShutter", value)
        self._optics["streak_shutter"] = result
        return result

    def _start_live(self, *, dark=False, recording=False, streak_open=True, kymera_open=True,
                    hold_clock=False):
        self._require_idle()
        if not self._prepared:
            raise RuntimeError("Prepare VD2 before starting Live")
        if self._dark_checkout:
            self._verify_dark_lamp()
        self._stop_manual_output()
        dg = self._proxy(self.dg645_device)
        self._verify_standby(dg)
        if self._query(dg, "TRAT?") != self._rate_hz:
            raise RuntimeError(f"DG645 rate did not verify at {self._rate_hz} Hz")
        verify_timing(dg, timing_for_range(self._time_range), live=True)
        camera = self._proxy(self.ccd_device, 30000)
        ky = self._proxy(self.kymera_device)
        self._read_optics(ky)
        if not streak_open:
            self._proxy(self.head_device).command_inout("SetShutter", "Closed")
        self._camera = camera
        self._kymera = ky
        try:
            camera.command_inout("OpenReadout")
            roi = tuple(camera.command_inout("SetROI", SENSOR_ROI))
            if roi != (*SENSOR_ROI, SENSOR_ROI[-1]):
                raise RuntimeError("CCD ROI did not verify")
            camera.ExposureMs = 10.0 if recording else self._live_exposure_ms
            if dark:
                camera.command_inout("StartSynchronizedDark" if streak_open else "StartSynchronizedDarkClosed",
                                     self._rate_hz)
            else:
                command_name = ("StartSynchronizedLiveWithOpenShutterAt" if streak_open
                                else "StartSynchronizedLiveWithClosedShutterAt")
                camera.command_inout(command_name, self._time_range)
            if camera.state() != DevState.RUNNING or not camera.AcquisitionActive:
                raise RuntimeError("CCD did not confirm synchronized Live")
            self._optics["streak_shutter"] = "Open" if streak_open else "Closed"
            self._set_kymera_shutter(ky, "Open" if kymera_open else "Closed")
            self._read_timing_values(dg)
            self._preview_configuration = self._read_calibration_configuration()
            self._camera_values.update(
                streak_mode="Operate", gate_mode="Normal", streak_trigger_mode="Single",
                mcp_gain=self._preview_configuration["camera"].get("mcp_gain", 0),
                live_mcp_gain_max=int(camera.LiveMcpGainMax),
                acquire_exposure_time=f'{self._preview_configuration["camera"]["exposure_ms"]:.9g} ms',
                streak_trigger_status="Software" if dark else "External")
            if not recording:
                self._camera_values["live_exposure_time"] = f'{self._preview_configuration["camera"]["exposure_ms"]:.9g} ms'
            self._clock = dg
            source = 5 if dark or hold_clock else (0 if recording else self._live_trigger_source)
            if source != 5:
                self._set_clock(dg, source)
            mode = next(name for name, code in LIVE_TRIGGER_SOURCES.items() if code == source)
            self._timing_values.update(delay_trigger_mode=mode, dg_output="Standby" if source == 5 else "On")
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
        if self._dark_checkout:
            raise RuntimeError("Dark checkout does not warm the flashlamp")
        if not self._outlet_power(self.lamp_pdu_device):
            raise RuntimeError("Verify the VD2 flashlamp supply is ON")
        if self._camera is None and self._read_head_mode() != "Operate":
            raise RuntimeError("Select Operate before starting a VD2 measurement")
        if self._camera is None:
            self._start_live(recording=True)
        elif self.get_state() != DevState.RUNNING or not self._camera.AcquisitionActive:
            raise RuntimeError("Stop the current VD2 operation first")
        elif self._query(self._clock, "TSRC?") != 0:
            raise RuntimeError("Select Internal on the DG645 before warming the flash lamp")
        self._start_warmup()

    def _start_warmup(self):
        if self._warmup_until is not None:
            return
        self._warmup_frame = int(self._camera.SweepFrameCount)
        self._warmup_until = monotonic() + LAMP_WARMUP_S
        self.set_status("VD2 warming the flash lamp")

    @command(dtype_in=str, dtype_out=str)
    def StartPhase(self, phase):
        if phase != "BRUIT" and self._rate_hz == 10 and not self._dark_checkout:
            raise RuntimeError("At 10 Hz record ABS and BASE together via Paired acquisition")
        if phase not in RECORDING_PHASES:
            raise ValueError("Unknown VD2 recording phase")
        if self._recording_phase is not None:
            raise RuntimeError("A VD2 sequence is already running")
        if self._time_range != "1 us":
            raise RuntimeError("Direct recording currently requires the calibrated 1 us time axis")
        if self._camera is not None:
            self.StopLive()
        self._require_idle()
        if not self._prepared:
            raise RuntimeError("Prepare VD2 before recording")
        if self._read_head_mode() != "Operate":
            raise RuntimeError("Select Operate before starting a VD2 measurement")
        if not self._dark_checkout and phase != "BRUIT" and not self._outlet_power(self.lamp_pdu_device):
            raise RuntimeError("Verify the VD2 flashlamp supply is ON")
        self._start_live(dark=self._dark_checkout or phase == "BRUIT", recording=True,
                         streak_open=not self._dark_checkout, kymera_open=not self._dark_checkout)
        self._recording_phase = phase
        try:
            if not self._dark_checkout and phase != "BRUIT":
                self._start_warmup()
            return self.PhaseConfiguration()
        except Exception as exc:
            self._fail_live(exc)

    @command(dtype_in=int, dtype_out=str)
    def ArmPaired(self, source):
        if source not in {1, 2}:
            raise ValueError("Select the external 5 Hz electron trigger for paired acquisition")
        self._require_idle()
        if not self._prepared or self._dark_checkout or self._time_range != "1 us":
            raise RuntimeError("Pairing requires standard VD2 preparation and the calibrated 1 us range")
        if self._read_head_mode() != "Operate" or not self._outlet_power(self.lamp_pdu_device):
            raise RuntimeError("Confirm Operate mode and flashlamp power before paired acquisition")
        self.SetRate(5)
        self._start_live(recording=True, hold_clock=True)
        self._recording_phase = "PAIRED"
        self._paired_source = source
        try:
            # The reader is armed before the first pulse so it begins at the start of a burst.
            self._camera.command_inout("BufferContinuousSequence")
            dg = self._clock
            queries = ["*IDN?", "TLVL?", "ADVT?", "HOLD?", "INHB?", "TIMB?", "BURD?", "BURT?"]
            queries += [f"{key}? {output}" for key in ("PRES", "LAMP", "LOFF", "LPOL")
                        for output in range(5)]
            queries += [f"PHAS? {output}" for output in range(1, 5)]
            self._paired_dg_readbacks = {
                query: dg.command_inout("scpi_query", query).strip() for query in queries
            }
            return self._paired_configuration(5)
        except Exception as exc:
            self._fail_live(exc)

    def _paired_configuration(self, source):
        if self._recording_phase != "PAIRED" or not self._camera.AcquisitionActive:
            raise RuntimeError("Paired camera acquisition is no longer active")
        if self._query(self._clock, "TRAT?") != 5 or self._query(self._clock, "TSRC?") != source:
            raise RuntimeError("Paired DG645 clock changed")
        configuration = self._read_calibration_configuration()
        if configuration["optics"]["shutter"] != "Open":
            raise RuntimeError("Kymera shutter is closed")
        delays = {name: self._clock.command_inout("scpi_query", f"DLAY? {channel}").strip()
                  for name, channel in DG_CHANNELS.items()}
        return json.dumps({**configuration, "phase": "PAIRED", "rate_hz": 10,
                           "dg_trigger_source": self._paired_source, "ccd_trigger": "external",
                           "delays": delays, "dark_checkout": False,
                           "dg645_arm_readbacks": self._paired_dg_readbacks,
                           "dg645_capture_settings": {"burst_enabled": True, "burst_count": 2,
                                                       "burst_period_s": .1, "base_rate_hz": 5}})

    @command
    def FirePaired(self):
        self._paired_configuration(5)
        dg = self._clock
        try:
            for query in ("BURD?", "BURT?"):
                if self._query(dg, query) != 0:
                    raise RuntimeError("Pairing requires zero burst delay and T0 on both pulses")
            for output in range(5):
                if self._query(dg, f"PRES? {output}") != 1:
                    raise RuntimeError("Pairing requires DG645 output prescales of one")
            for keyword, value in (("BURC", 2), ("BURP", .1), ("BURM", 1)):
                dg.command_inout("scpi_write", f"{keyword} {value}")
                if self._query(dg, f"{keyword}?") != value:
                    raise RuntimeError(f"DG645 did not verify {keyword}")
            self._set_clock(dg, self._paired_source)
            self._timing_values.update(delay_repetition_rate=10, delay_burst_mode="On",
                                       delay_trigger_mode=next(name for name, source in LIVE_TRIGGER_SOURCES.items()
                                                               if source == self._paired_source),
                                       dg_output="On")
            self.set_status("VD2 paired capture · two pulses per external trigger")
        except Exception as exc:
            self._fail_live(exc)

    @command(dtype_out=str)
    def PairedConfiguration(self):
        configuration = self._paired_configuration(self._paired_source)
        for keyword, value in (("BURM", 1), ("BURC", 2), ("BURP", .1)):
            if self._query(self._clock, f"{keyword}?") != value:
                raise RuntimeError("DG645 burst changed during paired recording")
        return configuration

    @command
    def StopPaired(self):
        if self._recording_phase == "PAIRED" or self._paired_source is not None:
            self.StopLive()

    @command(dtype_out=str)
    def PhaseConfiguration(self):
        if self._recording_phase is None or self.get_state() != DevState.RUNNING:
            raise RuntimeError("VD2 has no active sequence")
        dark = self._dark_checkout or self._recording_phase == "BRUIT"
        if self._dark_checkout:
            self._verify_dark_lamp()
        trigger_source = 5 if dark else 0
        if not self._camera.AcquisitionActive or self._query(self._clock, "TSRC?") != trigger_source:
            raise RuntimeError("VD2 synchronized sequence is no longer active")
        if self._query(self._clock, "TRAT?") != self._rate_hz or self._query(self._clock, "BURM?") != 0:
            raise RuntimeError("DG645 rate or burst changed during recording")
        configuration = self._read_calibration_configuration()
        if configuration["optics"]["shutter"] != ("Closed" if self._dark_checkout else "Open"):
            raise RuntimeError("Kymera shutter changed during recording")
        delays = {name: self._clock.command_inout("scpi_query", f"DLAY? {channel}").strip()
                  for channel, name in enumerate("abcdefgh", 2)}
        return json.dumps({**configuration, "phase": self._recording_phase,
                           "rate_hz": self._rate_hz, "dg_trigger_source": trigger_source,
                           "ccd_trigger": "software" if dark else "external", "delays": delays,
                           "dark_checkout": self._dark_checkout})

    def _read_calibration_configuration(self, optics=None):
        return {"time_range": self._time_range, "camera": json.loads(self._camera.ReadoutConfiguration()),
                "kymera_device": self.kymera_device,
                "optics": self._read_kymera(self._kymera) if optics is None else optics,
                "dg_delay_seconds": {name: self._timing_values[f"delay_{name}"] for name in DG_CHANNELS}}

    def _outlet_power(self, device, *, outlet=1):
        pdu = self._proxy(device)
        outlets = tuple(map(int, pdu.ids))
        states = tuple(map(int, pdu.states))
        if len(states) != len(outlets) or outlets.count(outlet) != 1 or states[outlets.index(outlet)] not in {0, 1}:
            raise RuntimeError(f"Invalid power readback from {device} outlet {outlet}")
        return states[outlets.index(outlet)] == 1

    @command
    def StopLive(self):
        self._stop_live(keep_shutters=True)

    def _stop_live(self, *, keep_shutters):
        try:
            self._release(keep_shutters=keep_shutters)
        except RuntimeError as exc:
            self._fault = str(exc)
            self.set_state(DevState.FAULT)
            self.set_status(self._fault)
            raise
        self._fault = ""
        self.set_state(DevState.ON)
        self.set_status("VD2 idle")

    def _release(self, *, keep_shutters=False):
        errors = []
        try:
            self._stop_manual_output()
        except Exception as exc:
            errors.append(f"DG645 manual output: {exc}")
        if self._clock is not None:
            try:
                if self._query(self._clock, "TSRC?") != 5:
                    self._set_clock(self._clock, 5)
                if self._paired_source is not None:
                    if self._query(self._clock, "BURM?") != 0:
                        self._clock.command_inout("scpi_write", "BURM 0")
                    self._verify_standby(self._clock)
                    self._write_rate(self._clock, 5)
                    self._timing_values.update(delay_repetition_rate=5, delay_burst_mode="Off")
                    self._paired_source = None
                    self._paired_dg_readbacks = None
                self._timing_values.update(delay_trigger_mode="Standby", dg_output="Standby")
                self._clock = None
            except Exception as exc:
                errors.append(f"DG645: {exc}")
        if self._kymera is not None:
            try:
                if not keep_shutters:
                    self._set_kymera_shutter(self._kymera, "Closed")
                self._kymera = None
            except Exception as exc:
                errors.append(f"Kymera: {exc}")
        if self._camera is not None:
            try:
                self._camera.command_inout("CloseReadoutKeepShutter" if keep_shutters else "CloseReadout")
                if self._camera.state() != DevState.OFF:
                    raise RuntimeError("CCD did not verify OFF")
                self._camera = None
                self._camera_values.update(mcp_gain=0, live_mcp_gain_max=0)
            except Exception as exc:
                errors.append(f"DCAM: {exc}")
        self._warmup_until = None
        self._warmup_frame = None
        self._preview_configuration = None
        self._focus_preview = False
        self._preview_first_frame = 0
        self._camera_values["streak_trigger_status"] = "Idle"
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
        elif phase == "live" and not acquired_frames and not self._focus_preview:
            phase = "waiting_for_trigger"
        preview_pending = state == "RUNNING" and not self._focus_preview and (
            self._preview_configuration is None or acquired_frames < self._preview_first_frame
        )
        return json.dumps({"state": state, "phase": phase, "time_range": self._time_range,
                           "frames": acquired_frames, "remaining_warmup_s": remaining,
                           "prepared": self._prepared, "trigger_rate_hz": self._rate_hz,
                           "dark_checkout": self._dark_checkout,
                           "optics": self._optics, "values": {**self._camera_values, **self._timing_values},
                           "preview_configuration": None if preview_pending else self._preview_configuration,
                           "preview_configuration_pending": preview_pending, "error": self._fault})


if __name__ == "__main__":
    DS_VD2.run_server()
