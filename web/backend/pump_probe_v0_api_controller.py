"""pump probe v0 api controller operations."""


from pump_probe_v0_api_emulator import bind as _bind_emulator
from pump_probe_v0_api_tango_run import bind as _bind_tango_run
from pump_probe_v0_api_preflight import bind as _bind_preflight


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    class PumpProbeV0Controller(_bind_emulator(api), _bind_tango_run(api), _bind_preflight(api)):
        def __init__(self):
            self._lock = api.threading.RLock()
            self._hardware_config = dict(api.DEFAULT_HARDWARE_CONFIG)
            self._sample_position_mm = 0.0
            self._sample_set_position_mm = 0.0
            self._sample_last_motion_update = api.time.monotonic()
            self._counter_last_value = None
            self._counter_last_time = None
            self._counter_rate_hz = 0.0
            self._andor_order = None
            self._andor_error = ""
            self._run_writer = None
            self._run_status = "idle"
            self._run_error = ""
            self._run_artifacts = {}
            self._run_output_dir = ""
            self._run_sample_name = ""
            self._run_thread = None
            self._scan_plan = None
            self._resume_source = None
            self._tango_run_plan = None
            self._tango_stop_event = None
            self._tango_done_event = api.threading.Event()
            self._tango_done_event.set()
            self._tango_stop_status = "stopped"
            self._tango_order_id = None
            self._tango_rejected_cycles = 0
            self._tango_cleanup_errors = []
            self._tango_camera_fingerprint = None
            self._tango_reset_requested = False
            self._run_raw_groups = tuple(api.RAW_GROUPS)
            self._settings = {
                "point_count": 100,
                "scan_start_ps": -25.0,
                "delay_step_ps": 1.0,
                "scan_span_ps": 99.0,
                "pulses_per_point": 10,
                "real_zero_ps": 465.0,
                "delay_points_ps": None,
            }
            self._wavelengths = api._linspace(253.2375, 826.3287, api.PIXELS)
            self._rng = api.random.Random()
            self._reset_locked()

        def _control_mode_locked(self):
            return api._clean_control_mode(self._hardware_config.get("control_mode"))

        def _configure_hardware_locked(self, payload):
            raw_config = payload.get("hardware_config") or {}
            if "control_mode" in payload:
                raw_config = {**raw_config, "control_mode": payload.get("control_mode")}
            if raw_config:
                next_config = {**self._hardware_config}
                for key, value in raw_config.items():
                    if key not in api.DEFAULT_HARDWARE_CONFIG:
                        continue
                    if key in ("delay_line_axis", "sample_stage_axis"):
                        next_config[key] = int(value)
                    elif key == "control_mode":
                        next_config[key] = api._clean_control_mode(value)
                    else:
                        next_config[key] = str(value)
                self._hardware_config = next_config

        def _reset_locked(self):
            self._running = False
            self._real_time = False
            self._andor_order = None
            self._faraday_closed = True
            self._crystal_position = 0
            self._current_index = 0
            self._pulses_at_point = 0
            self._total_pulses = 0
            self._spectrometer_frames = 0
            now = api.time.monotonic()
            self._last_pulse_update = now
            self._last_motion_update = now
            self._delays = self._make_delays_locked()
            self._position_mm = self._delay_to_mm(self._delays[0])
            self._set_position_mm = self._position_mm
            self._heatmap = [[None for _ in self._wavelengths] for _ in self._delays]
            if self._control_mode_locked() == "tango":
                self._live_od = [None for _ in self._wavelengths]
                self._last_spectra = {
                    key: [None for _ in self._wavelengths]
                    for key in ("reference", "signal", "background")
                }
                self._last_spectra["background_available"] = False
            else:
                self._live_od = self._make_od_row_locked(0, include_signal=False)
                self._last_spectra = self._make_spectra_locked(0, False)


        def _finalize_run_locked(self, status, error=""):
            writer = self._run_writer
            self._running = False
            if writer is None:
                self._run_status = status
                self._run_error = str(error)
                return
            try:
                staged = writer.finalize(status=status, error=error)
                # Continue creates a new acquisition file from acquired RAW slots;
                # the stopped run remains an immutable parent artifact.
                self._resume_source = ({
                    "h5_path": staged["h5_path"], "plan": self._scan_plan,
                    "wavelengths": tuple(self._wavelengths),
                    "hardware_config": dict(self._hardware_config),
                    "mode": self._control_mode_locked(), "run_id": staged["run_id"],
                    "frame_counts": list(staged["frame_counts"]),
                    "next_point_index": staged.get("next_point_index"),
                    "next_shot_index": staged.get("next_shot_index"),
                    "profile_fingerprint": staged.get("tango_profile_fingerprint"),
                    "camera_config_fingerprint": self._tango_camera_fingerprint,
                    "dg645_sha256": self._tango_run_plan.to_dict()["dg645"]["source_sha256"] if self._tango_run_plan is not None and self._control_mode_locked() == "tango" else None,
                } if status == "stopped" and staged.get("next_point_index") is not None else None)
                self._run_artifacts = {
                    "run_id": staged["run_id"],
                    "frame_counts": staged["frame_counts"],
                    "parent_run_id": staged.get("parent_run_id"),
                    "next_point_index": staged.get("next_point_index"),
                    "next_shot_index": staged.get("next_shot_index"),
                    "scan_plan_fingerprint": staged.get("scan_plan_fingerprint"),
                    "raw_layout": staged.get("raw_layout"),
                    "tango_profile_fingerprint": staged.get("tango_profile_fingerprint"),
                }
                for kind in ("h5", "dat", "manifest"):
                    self._run_artifacts[kind] = api._publish_data_file(self._run_output_dir, staged[f"{kind}_path"])
                self._run_status = status
                self._run_error = str(error)
            except Exception as exc:
                self._resume_source = None
                self._run_status = "fault"
                self._run_error = f"Run storage failed: {exc}"
                self._run_artifacts.setdefault("run_id", writer.run_id)
                self._run_artifacts["retained_h5_path"] = str(writer.h5_path)
                try:
                    writer.close()
                except Exception as close_error:
                    self._run_error += f"; HDF5 close failed: {close_error}"
            finally:
                self._run_writer = None


        def configure(self, payload):
            with self._lock:
                if self._run_writer is not None or self._tango_stop_event is not None:
                    raise RuntimeError("Stop the active run before changing scan settings")
                next_settings = api.resolve_scan_settings(self._settings, payload)
                if self._control_mode_locked() != "tango":
                    self._sync_locked()
                    self._sync_sample_stage_locked()
                self._configure_hardware_locked(payload)
                self._settings = next_settings
                old_running = self._running
                old_real_time = self._real_time
                old_faraday = self._faraday_closed
                self._reset_locked()
                self._running = old_running
                self._real_time = old_real_time
                self._faraday_closed = old_faraday
                return self.state()

        def hardware_config(self):
            with self._lock:
                return dict(self._hardware_config)

        def set_running(self, running, payload=None, *, tango_plan=None):
            with self._lock:
                next_running = bool(running)
                payload = payload or {}
                action = payload.get("run_action", "new")
                if action not in {"new", "continue", "overwrite", "cancel"}:
                    raise ValueError("run_action must be new, continue, overwrite, or cancel")
                if self._tango_stop_event is not None:
                    if action == "cancel" or not next_running:
                        self._request_tango_stop_locked("aborted" if action == "cancel" else "stopped")
                        return self.state()
                    raise RuntimeError("Stop the active Tango run and wait for cleanup before starting another")
                if action == "cancel":
                    if self._run_writer is not None:
                        self._finalize_run_locked("aborted", "Cancelled by operator")
                    self._running = False
                    self._real_time = False
                    self._andor_order = None
                    self._resume_source = None
                    if self._run_status == "stopped":
                        self._run_status = "aborted"
                    return self.state()
                if next_running and action in {"continue", "overwrite"} and self._running:
                    raise ValueError("Stop the active run before continuing or replacing it")
                if not next_running:
                    # Clearing the authorized active flag must precede any state
                    # refresh: stopping an active sequence never polls or advances
                    # another camera order.
                    if self._run_writer is not None:
                        self._finalize_run_locked("stopped")
                    self._running = False
                    self._real_time = False
                    self._andor_order = None
                    self._last_pulse_update = api.time.monotonic()
                    return self.state()
                if next_running and self._control_mode_locked() == "emulator":
                    if self._run_writer is None:
                        self._start_emulator_run_locked(payload)
                    return self.state()
                if next_running and self._control_mode_locked() == "tango":
                    if tango_plan is None:
                        raise ValueError("A precomputed authorized Tango RAW plan is required")
                    self._start_tango_run_locked(payload, tango_plan)
                    return self.state()
                self._running = next_running
                if next_running:
                    self._real_time = False
                    if self._control_mode_locked() == "tango":
                        self._sync_locked()
                else:
                    self._real_time = False
                self._last_pulse_update = api.time.monotonic()
                return self.state()

        def set_real_time(self, enabled):
            with self._lock:
                if self._tango_stop_event is not None:
                    if enabled:
                        raise RuntimeError("Stop the Tango RAW run before enabling realtime spectra")
                    self._real_time = False
                    return self.state()
                if not enabled and self._control_mode_locked() == "tango":
                    self._real_time = False
                    self._andor_order = None
                    self._last_pulse_update = api.time.monotonic()
                    return self.state()
                self._sync_locked()
                self._real_time = bool(enabled)
                if self._real_time and self._control_mode_locked() == "tango":
                    self._sync_locked()
                self._last_pulse_update = api.time.monotonic()
                return self.state()

        def set_faraday(self, closed):
            with self._lock:
                self._sync_locked()
                self._faraday_closed = bool(closed)
                return self.state()

        def move_stage(self, payload):
            with self._lock:
                if self._running or self._tango_stop_event is not None:
                    raise RuntimeError("Stop the active run before moving the delay stage")
                self._sync_locked()
                if self._control_mode_locked() == "tango":
                    position = float(payload.get("position_mm", self._set_position_mm))
                    self._move_owis_axis_locked(self._hardware_config["delay_line_axis"], position)
                    self._set_position_mm = api._clamp(position, api.STAGE_MIN_MM, api.STAGE_MAX_MM)
                elif "position_mm" in payload:
                    self._set_position_mm = api._clamp(float(payload["position_mm"]), api.STAGE_MIN_MM, api.STAGE_MAX_MM)
                elif "delta_ps" in payload:
                    self._set_position_mm = api._clamp(
                        self._set_position_mm - float(payload["delta_ps"]) * api.MM_PER_PS,
                        api.STAGE_MIN_MM,
                        api.STAGE_MAX_MM,
                    )
                elif "delta_mm" in payload:
                    self._set_position_mm = api._clamp(
                        self._set_position_mm + float(payload["delta_mm"]),
                        api.STAGE_MIN_MM,
                        api.STAGE_MAX_MM,
                    )
                return self.state()

        def stop_stage(self):
            with self._lock:
                if self._tango_stop_event is not None:
                    self._request_tango_stop_locked()
                    return self.state()
                if self._run_writer is not None:
                    self._finalize_run_locked("stopped")
                self._running = False
                self._real_time = False
                self._andor_order = None
                self._sync_locked()
                if self._control_mode_locked() == "tango":
                    self._stop_owis_axis_locked(self._hardware_config["delay_line_axis"])
                self._set_position_mm = self._position_mm
                return self.state()

        def move_sample_stage(self, payload):
            with self._lock:
                if self._tango_stop_event is not None:
                    raise RuntimeError("Wait for the Tango RAW run and device cleanup before manual sample motion")
                self._sync_sample_stage_locked()
                position = api._clamp(float(payload.get("position_mm", self._sample_set_position_mm)), 0.0, 150.0)
                if self._control_mode_locked() == "tango":
                    self._move_owis_axis_locked(self._hardware_config["sample_stage_axis"], position)
                self._sample_set_position_mm = position
                return self.state()

        def stop_sample_stage(self):
            with self._lock:
                if (self._tango_stop_event is not None
                        and self._hardware_config["sample_stage_axis"] == self._hardware_config["delay_line_axis"]):
                    self._request_tango_stop_locked()
                    return self.state()
                self._sync_sample_stage_locked()
                if self._control_mode_locked() == "tango":
                    self._stop_owis_axis_locked(self._hardware_config["sample_stage_axis"])
                self._sample_set_position_mm = self._sample_position_mm
                return self.state()


        def _read_tango_motion_state_locked(self, state):
            if self._control_mode_locked() != "tango":
                return state
            try:
                proxy = self._owis_aggregator_locked()
                positions = api._parse_tango_dict(proxy.read_attribute("positions").value)
                states = api._parse_tango_dict(proxy.read_attribute("states").value)
                delay_axis = int(self._hardware_config["delay_line_axis"])
                sample_axis = int(self._hardware_config["sample_stage_axis"])
                delay_pos = positions.get(delay_axis, positions.get(str(delay_axis)))
                sample_pos = positions.get(sample_axis, positions.get(str(sample_axis)))
                delay_state = states.get(delay_axis, states.get(str(delay_axis)))
                sample_state = states.get(sample_axis, states.get(str(sample_axis)))
                if delay_pos is not None:
                    self._position_mm = float(delay_pos)
                    state["position_mm"] = round(self._position_mm, 5)
                if sample_pos is not None:
                    self._sample_position_mm = float(sample_pos)
                state["sample_position_mm"] = round(self._sample_position_mm, 5)
                state["sample_set_position_mm"] = round(self._sample_set_position_mm, 5)
                state["stage_moving"] = abs(self._set_position_mm - self._position_mm) > 0.0005
                state["sample_stage_moving"] = abs(self._sample_set_position_mm - self._sample_position_mm) > 0.0005
                state["tango_motion"] = {
                    "delay_line_axis": delay_axis,
                    "delay_line_state": str(delay_state),
                    "sample_stage_axis": sample_axis,
                    "sample_stage_state": str(sample_state),
                }
                state["hardware_error"] = ""
            except Exception as exc:
                state["hardware_error"] = str(exc)
            return state

        def move_crystal(self):
            with self._lock:
                self._sync_locked()
                self._crystal_position = (self._crystal_position + 1) % 8
                return self.state()

        def reset(self):
            with self._lock:
                if self._tango_stop_event is not None:
                    self._tango_reset_requested = True
                    self._request_tango_stop_locked("aborted")
                    return self.state()
                if self._run_writer is not None:
                    self._finalize_run_locked("aborted", "Reset requested")
                self._reset_locked()
                self._run_status = "idle"
                self._run_error = ""
                self._resume_source = None
                self._scan_plan = None
                return self.state()

        def state(self, advance_active=False):
            with self._lock:
                tango_mode = self._control_mode_locked() == "tango"
                if not tango_mode:
                    self._sync_locked()
                    self._sync_sample_stage_locked()
                elif advance_active and (self._running or self._real_time):
                    self._sync_locked()
                state = {
                    "accelerator_hz": api.ACCELERATOR_HZ,
                    "spectrometer_hz": api.SPECTROMETER_HZ,
                    "spectrometer_burst": api.SPECTROMETER_BURST,
                    "stage_speed_mm_per_sec": api.STAGE_SPEED_MM_PER_SEC,
                    "running": self._running,
                    "real_time": self._real_time,
                    "faraday_closed": self._faraday_closed,
                    "electron_state": "OFF" if self._faraday_closed else "ON",
                    "current_index": self._current_index,
                    "pulses_at_point": self._pulses_at_point,
                    "total_pulses": self._total_pulses,
                    "spectrometer_frames": self._spectrometer_frames,
                    "andor_error": self._andor_error,
                    # Dashboard state is deliberately cached/no-probe in both
                    # modes: GET state must never create a Tango proxy or command.
                    "daq_counter": {
                        "value": None,
                        "rate_hz": 0.0,
                        "active": False,
                        "error": "not probed",
                    },
                    "position_mm": round(self._position_mm, 5),
                    "set_position_mm": round(self._set_position_mm, 5),
                    "stage_moving": abs(self._set_position_mm - self._position_mm) > 0.0005,
                    "crystal_position": self._crystal_position,
                    "control_mode": self._control_mode_locked(),
                    "hardware_config": dict(self._hardware_config),
                    "sample_position_mm": round(self._sample_position_mm, 5),
                    "sample_set_position_mm": round(self._sample_set_position_mm, 5),
                    "sample_stage_moving": abs(self._sample_set_position_mm - self._sample_position_mm) > 0.0005,
                    "settings": dict(self._settings),
                    "run": {
                        "id": self._run_writer.run_id if self._run_writer is not None else self._run_artifacts.get("run_id"),
                        "status": self._run_status,
                        "error": self._run_error,
                        "sample_name": self._run_sample_name,
                        "output_dir": self._run_output_dir,
                        "artifacts": dict(self._run_artifacts),
                        "raw_groups": list(self._run_raw_groups),
                        "acquisition_contract": "andor-v0-raw-order-v1" if self._tango_run_plan is not None and tango_mode else "andor-two-track-spectra-v1" if tango_mode else "v0-raw6-scan-v1",
                        "tango_run_plan_fingerprint": self._tango_run_plan.fingerprint if self._tango_run_plan is not None else None,
                        "tango_pending_order": self._tango_order_id,
                        "rejected_cycles": self._tango_rejected_cycles,
                        "cleanup_errors": list(self._tango_cleanup_errors),
                        "scan_plan": self._scan_plan.to_dict() if self._scan_plan is not None else None,
                        "resume_available": self._resume_available_locked(),
                    },
                    "wavelengths": self._wavelengths,
                    "delays": self._delays,
                    "heatmap": self._heatmap,
                    "live_od": self._live_od,
                    "spectra": self._last_spectra,
                }
                # RAW orders advance only in the worker. Once cleanup has ended,
                # preserve the existing passive OWIS readback for manual controls.
                return (state if self._tango_stop_event is not None or not self._tango_done_event.is_set()
                        else self._read_tango_motion_state_locked(state))

    api.PumpProbeV0Controller = PumpProbeV0Controller
