"""V0 experiment controller and emulator runtime."""


def bind(api):
    """Use the owning API module for shared state and dependencies."""
    class PumpProbeV0Controller:
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
            self._live_od = self._make_od_row_locked(0, include_signal=False)
            self._last_spectra = self._make_spectra_locked(0, False)

        def _make_delays_locked(self):
            custom_delays = self._settings.get("delay_points_ps")
            if custom_delays:
                return [float(value) for value in custom_delays]
            start = float(self._settings["scan_start_ps"])
            step = float(self._settings["delay_step_ps"])
            count = int(self._settings["point_count"])
            return [float(start + index * step) for index in range(count)]

        def _delay_to_mm(self, delay_ps):
            real_zero_ps = float(self._settings["real_zero_ps"])
            return api._clamp(-(delay_ps + real_zero_ps) * api.MM_PER_PS, api.STAGE_MIN_MM, api.STAGE_MAX_MM)

        def _make_od_row_locked(self, index, include_signal=True, signal_progress=1.0):
            delay = self._delays[index]
            shot_phase = self._total_pulses * 1.37
            phase = index * 0.31 + shot_phase
            drift = (
                0.00045 * api.math.sin(self._total_pulses / 17.0 + index / 11.0)
                + api.OD_COMMON_OSCILLATION * api.math.sin(shot_phase)
                + 0.00035 * api.math.sin(shot_phase * 0.43 + index * 0.17)
            )
            signal_progress = api._clamp(signal_progress, 0.0, 1.0)
            row = []
            for pixel, wavelength in enumerate(self._wavelengths):
                band_a = api._gaussian(wavelength, 445, 42)
                band_b = api._gaussian(wavelength, 650, 68)
                kinetics = 0.18 * (1 - api.math.exp(-(delay + 30) / 42))
                ripple = 0.012 * api.math.sin(pixel / 13 + index / 7)
                signal = kinetics * band_a - 0.07 * band_b + ripple
                signal_factor = signal_progress if include_signal and not self._faraday_closed else 0.0
                random_od = self._rng.uniform(-0.00045, 0.00045)
                od_noise = api.OD_NOISE_SCALE * (
                    0.55 * api.math.sin(pixel * 0.37 + phase * 1.7)
                    + 0.30 * api.math.sin(pixel * 1.91 + phase * 0.91)
                    + 0.15 * api.math.cos(pixel * 0.11 + shot_phase * 2.3)
                )
                row.append(round(signal_factor * signal + drift + od_noise + random_od, 5))
            return row

        def _make_spectra_locked(self, index, electron_on):
            phase = index * 0.31 + self._total_pulses * 0.73
            electron_scale = 0.92 if electron_on else 1.0
            lamp_drift = 1.0 + api.LAMP_DRIFT_FRACTION * (
                0.6 * api.math.sin(self._total_pulses / 19.0)
                + 0.4 * api.math.sin(self._total_pulses * 1.11)
            )
            dark_drift = (
                api.DARK_DRIFT_COUNTS * api.math.sin(self._total_pulses / 23.0)
                + 0.7 * api.math.sin(self._total_pulses * 1.43)
                + 0.3 * api.math.sin(self._total_pulses * 2.17)
            )
            signal = []
            reference = []
            background = []
            for pixel, wavelength in enumerate(self._wavelengths):
                pixel_dark = 1.4 * api.math.sin(pixel / 41.0 + phase * 0.19)
                read_signal = api.READ_NOISE_COUNTS * api.math.sin(pixel * 0.73 + phase * 2.1)
                read_reference = api.READ_NOISE_COUNTS * api.math.cos(pixel * 0.67 + phase * 1.8)
                read_background = 1.8 * api.math.sin(pixel * 0.91 + phase * 2.7)
                signal_random = self._rng.randint(-api.SIGNAL_RANDOM_COUNTS, api.SIGNAL_RANDOM_COUNTS)
                reference_random = self._rng.randint(-api.REFERENCE_RANDOM_COUNTS, api.REFERENCE_RANDOM_COUNTS)
                background_random = self._rng.randint(-api.BACKGROUND_RANDOM_COUNTS, api.BACKGROUND_RANDOM_COUNTS)

                lamp_signal = (22000 * api._gaussian(wavelength, 525, 230) + 4200) * lamp_drift
                absorbance_depth = 0.11 if electron_on else 0.0
                absorbance = 1 - absorbance_depth * api._gaussian(wavelength, 458 + 6 * api.math.sin(phase), 38)
                signal.append(round(lamp_signal * absorbance * electron_scale + read_signal + signal_random))

                lamp_reference = (21000 * api._gaussian(wavelength, 535, 250) + 4600) * lamp_drift
                reference.append(round(lamp_reference + read_reference + reference_random))

                bg = 520 + dark_drift + pixel_dark + 2.5 * api.math.sin(pixel / 17 + phase) + read_background + background_random
                background.append(round(bg))
            return {
                "signal": signal,
                "reference": reference,
                "background": background,
            }

        def _sync_locked(self):
            if self._control_mode_locked() == "tango":
                # Passive idle reads must not begin an order.  Only an already
                # authorized run/realtime operation may advance Tango acquisition.
                if self._running or self._real_time:
                    self._sync_andor_spectra_locked()
                return

            now = api.time.monotonic()
            motion_elapsed = max(0.0, now - self._last_motion_update)
            self._last_motion_update = now
            distance = self._set_position_mm - self._position_mm
            max_step = api.STAGE_SPEED_MM_PER_SEC * motion_elapsed
            if abs(distance) <= max_step:
                self._position_mm = self._set_position_mm
            elif distance > 0:
                self._position_mm += max_step
            else:
                self._position_mm -= max_step

            elapsed = now - self._last_pulse_update
            pulse_count = int(elapsed * api.ACCELERATOR_HZ)
            if pulse_count <= 0:
                return
            self._last_pulse_update += pulse_count / api.ACCELERATOR_HZ
            for _ in range(pulse_count):
                self._apply_pulse_locked()

        def _decode_andor_order_locked(self, payload, width):
            raw = api.zlib.decompress(api.ast.literal_eval(str(payload)))
            data = api.np.frombuffer(raw, dtype=api.np.float32)
            if width <= 0 or data.size < width * 3 or data.size % width:
                raise ValueError(f"Invalid Andor order shape: {data.size} values, width={width}")

            rows = data.reshape(-1, width)
            wavelengths = rows[0]
            payload_rows = rows[1:]
            track_count = 2
            frame_count = payload_rows.shape[0] // track_count
            if frame_count < 1:
                raise ValueError("Andor order contains no spectra")
            tracks = payload_rows[: frame_count * track_count].reshape(frame_count, track_count, width)
            return wavelengths, tracks

        def _sync_andor_spectra_locked(self):
            """Pull completed three-shot Andor orders without fabricating spectra."""
            try:
                camera = api._tango_proxy(self._hardware_config["andor_device"], timeout_ms=5000)
                if "FAULT" in str(camera.state()).upper() or "OFF" in str(camera.state()).upper():
                    raise RuntimeError(f"Andor state is {camera.state()}")

                if self._andor_order is None:
                    camera.command_inout("start_grabbing")
                    self._andor_order = camera.command_inout("register_order", [api.SPECTROMETER_BURST])
                    self._andor_error = ""
                    return

                if not camera.command_inout("is_order_ready", self._andor_order):
                    return

                axis = api.np.asarray(camera.read_attribute("wavelengths_axis").value, dtype=api.np.float32)
                wavelengths, frames = self._decode_andor_order_locked(
                    camera.command_inout("give_order", self._andor_order), axis.size
                )
                self._andor_order = None
                if self._wavelengths != wavelengths.tolist():
                    self._wavelengths = [float(value) for value in wavelengths]
                    self._heatmap = [[None for _ in self._wavelengths] for _ in self._delays]
                    self._live_od = [None for _ in self._wavelengths]

                averaged = api.np.mean(frames, axis=0)
                self._last_spectra = {
                    "reference": [float(value) for value in averaged[0]],
                    "signal": [float(value) for value in averaged[1]],
                    # Dark/background has to be acquired separately; do not emulate it in Tango mode.
                    "background": [0.0 for _ in self._wavelengths],
                    "background_available": False,
                }
                self._spectrometer_frames += int(frames.shape[0])
                self._andor_error = ""
            except Exception as exc:
                self._andor_error = str(exc)

        def _sync_sample_stage_locked(self):
            now = api.time.monotonic()
            elapsed = max(0.0, now - self._sample_last_motion_update)
            self._sample_last_motion_update = now
            distance = self._sample_set_position_mm - self._sample_position_mm
            max_step = api.STAGE_SPEED_MM_PER_SEC * elapsed
            if abs(distance) <= max_step:
                self._sample_position_mm = self._sample_set_position_mm
            elif distance > 0:
                self._sample_position_mm += max_step
            else:
                self._sample_position_mm -= max_step

        def _emulator_raw_cycle_locked(self, delay_index):
            """Generate one unaveraged frame for each legacy V0 raw group."""
            off = self._make_spectra_locked(delay_index, electron_on=False)
            on = self._make_spectra_locked(delay_index, electron_on=True)
            return [
                off["background"],
                off["reference"],
                off["signal"],
                on["background"],
                on["reference"],
                on["signal"],
            ]

        def _start_emulator_run_locked(self, payload):
            output_dir = str(payload.get("save_path") or "").strip()
            if not output_dir:
                raise ValueError("Choose a data folder before starting an emulator run")
            output_dir = api._normalize_data_path(output_dir)
            if not api._is_data_path_allowed(output_dir):
                raise ValueError("Run output path is outside pump-probe data root")

            self._reset_locked()
            self._run_output_dir = output_dir
            self._run_sample_name = str(payload.get("sample_name") or "").strip()
            positions = [self._delay_to_mm(delay) for delay in self._delays]
            run_config = {
                "experiment": "V0 DirectLine pump-probe",
                "mode": "emulator",
                "sample_name": self._run_sample_name,
                "settings": dict(self._settings),
                "hardware_config": dict(self._hardware_config),
                "raw_groups": list(api.RAW_GROUPS),
                "spectrometer": {"rate_hz": api.SPECTROMETER_HZ, "burst": api.SPECTROMETER_BURST},
                "accelerator_hz": api.ACCELERATOR_HZ,
            }
            self._run_writer = api.V0EmulatorRunWriter(
                self._wavelengths,
                self._delays,
                positions,
                self._settings["pulses_per_point"],
                run_config,
            )
            self._run_status = "running"
            self._run_error = ""
            self._run_artifacts = {}
            self._running = True
            self._real_time = False
            self._last_pulse_update = api.time.monotonic()
            self._run_thread = api.threading.Thread(
                target=self._run_emulator_loop,
                name=f"pump-probe-v0-{self._run_writer.run_id}",
                daemon=True,
            )
            self._run_thread.start()

        def _run_emulator_loop(self):
            """Advance a scan independently from HTTP state polling."""
            while True:
                with self._lock:
                    if not self._running or self._run_writer is None:
                        return
                    self._sync_locked()
                api.time.sleep(0.02)

        def _finalize_run_locked(self, status, error=""):
            writer = self._run_writer
            self._running = False
            if writer is None:
                self._run_status = status
                self._run_error = str(error)
                return
            try:
                staged = writer.finalize(status=status, error=error)
                self._run_artifacts = {
                    "run_id": staged["run_id"],
                    "h5": api._publish_data_file(self._run_output_dir, staged["h5_path"]),
                    "dat": api._publish_data_file(self._run_output_dir, staged["dat_path"]),
                    "manifest": api._publish_data_file(self._run_output_dir, staged["manifest_path"]),
                    "frame_counts": staged["frame_counts"],
                }
                self._run_status = status
                self._run_error = str(error)
            except Exception as exc:
                self._run_status = "fault"
                self._run_error = f"Run storage failed: {exc}"
            finally:
                self._run_writer = None

        def _apply_pulse_locked(self):
            if not self._running and not self._real_time:
                return

            if self._running and self._run_writer is not None:
                if abs(self._set_position_mm - self._position_mm) > 0.0005:
                    return
                try:
                    frames = self._emulator_raw_cycle_locked(self._current_index)
                    self._total_pulses += 1
                    self._spectrometer_frames += len(frames)
                    self._live_od = self._run_writer.record_cycle(
                        self._current_index,
                        frames,
                        self._set_position_mm,
                        self._position_mm,
                    )
                    self._last_spectra = {
                        "background": frames[0],
                        "reference": frames[1],
                        "signal": frames[2],
                        "background_available": True,
                    }
                    self._heatmap[self._current_index] = self._live_od
                    self._pulses_at_point += 1
                except Exception as exc:
                    self._finalize_run_locked("fault", str(exc))
                    return

                if self._pulses_at_point < int(self._settings["pulses_per_point"]):
                    return
                self._pulses_at_point = 0
                if self._current_index + 1 >= len(self._delays):
                    self._finalize_run_locked("completed")
                    return
                self._current_index += 1
                self._set_position_mm = self._delay_to_mm(self._delays[self._current_index])
                return

            self._total_pulses += 1
            self._spectrometer_frames += api.SPECTROMETER_BURST
            electron_on = not self._faraday_closed
            self._last_spectra = self._make_spectra_locked(self._current_index, electron_on)
            pulses_per_point = int(self._settings["pulses_per_point"])
            signal_progress = min(1.0, (self._pulses_at_point + 1) / pulses_per_point)
            self._live_od = self._make_od_row_locked(
                self._current_index,
                include_signal=self._running,
                signal_progress=signal_progress,
            )

            if not self._running:
                return

            self._heatmap[self._current_index] = self._live_od
            self._pulses_at_point += 1
            if self._pulses_at_point < pulses_per_point:
                return

            self._live_od = self._make_od_row_locked(self._current_index, signal_progress=1.0)
            self._heatmap[self._current_index] = self._live_od
            self._pulses_at_point = 0
            if self._current_index + 1 >= len(self._delays):
                self._running = False
                return
            self._current_index += 1
            self._set_position_mm = self._delay_to_mm(self._delays[self._current_index])

        def configure(self, payload):
            with self._lock:
                if self._control_mode_locked() != "tango":
                    self._sync_locked()
                    self._sync_sample_stage_locked()
                if self._running and self._run_writer is not None:
                    raise RuntimeError("Stop the active run before changing scan settings")
                self._configure_hardware_locked(payload)
                if "delay_points_ps" in payload:
                    raw_delays = payload["delay_points_ps"]
                    if raw_delays:
                        delays = [float(value) for value in raw_delays]
                        delays = delays[:400]
                        self._settings["delay_points_ps"] = delays
                        self._settings["point_count"] = len(delays)
                        self._settings["scan_start_ps"] = delays[0]
                        if len(delays) > 1:
                            self._settings["delay_step_ps"] = delays[1] - delays[0]
                            self._settings["scan_span_ps"] = delays[-1] - delays[0]
                    else:
                        self._settings["delay_points_ps"] = None
                for key in ("point_count", "scan_start_ps", "delay_step_ps", "scan_span_ps", "pulses_per_point", "real_zero_ps"):
                    if key not in payload:
                        continue
                    if key in ("point_count", "pulses_per_point"):
                        self._settings[key] = max(1, int(payload[key]))
                    else:
                        self._settings[key] = float(payload[key])
                    if key in ("point_count", "scan_start_ps", "delay_step_ps"):
                        self._settings["delay_points_ps"] = None
                self._settings["point_count"] = api._clamp(self._settings["point_count"], 2, 400)
                self._settings["pulses_per_point"] = api._clamp(self._settings["pulses_per_point"], 1, 200)
                if not self._settings.get("delay_points_ps"):
                    self._settings["scan_span_ps"] = (int(self._settings["point_count"]) - 1) * float(self._settings["delay_step_ps"])
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

        def set_running(self, running, payload=None):
            with self._lock:
                next_running = bool(running)
                payload = payload or {}
                if not next_running and self._control_mode_locked() == "tango":
                    # Clearing the authorized active flag must precede any state
                    # refresh: stopping an active sequence never polls or advances
                    # another camera order.
                    self._running = False
                    self._real_time = False
                    self._last_pulse_update = api.time.monotonic()
                    return self.state()
                self._sync_locked()
                if not next_running and self._run_writer is not None:
                    self._finalize_run_locked("stopped")
                    return self.state()
                if next_running and self._control_mode_locked() == "emulator":
                    if self._run_writer is None:
                        self._start_emulator_run_locked(payload)
                    return self.state()
                if next_running and self._control_mode_locked() == "tango":
                    self._preflight_dg645_locked()
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
                if not enabled and self._control_mode_locked() == "tango":
                    self._real_time = False
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
                self._sync_locked()
                if self._control_mode_locked() == "tango":
                    self._stop_owis_axis_locked(self._hardware_config["delay_line_axis"])
                self._set_position_mm = self._position_mm
                return self.state()

        def move_sample_stage(self, payload):
            with self._lock:
                self._sync_sample_stage_locked()
                position = api._clamp(float(payload.get("position_mm", self._sample_set_position_mm)), 0.0, 150.0)
                if self._control_mode_locked() == "tango":
                    self._move_owis_axis_locked(self._hardware_config["sample_stage_axis"], position)
                self._sample_set_position_mm = position
                return self.state()

        def stop_sample_stage(self):
            with self._lock:
                self._sync_sample_stage_locked()
                if self._control_mode_locked() == "tango":
                    self._stop_owis_axis_locked(self._hardware_config["sample_stage_axis"])
                self._sample_set_position_mm = self._sample_position_mm
                return self.state()

        def _owis_aggregator_locked(self):
            return api._tango_proxy(self._hardware_config["owis_aggregator_device"])

        def _move_owis_axis_locked(self, axis, position):
            proxy = self._owis_aggregator_locked()
            proxy.command_inout("move_axis", [float(axis), float(position)])

        def _stop_owis_axis_locked(self, axis):
            proxy = self._owis_aggregator_locked()
            proxy.command_inout("stop_axis", int(axis))

        def _preflight_dg645_locked(self):
            policy = str(self._hardware_config.get("dg645_preflight_policy") or "apply_recall_then_verify").strip().lower()
            if policy in {"off", "skip", "disabled"}:
                return

            config = api._load_dg645_recall_config(self._hardware_config.get("dg645_recall_config"))
            dg645 = api._tango_proxy(self._hardware_config.get("dg645_device") or config.get("device"), timeout_ms=8000)
            recall_slot = int(config.get("recall_slot", 8))

            if policy in {"apply_recall_then_verify", "recall_then_verify", "apply"}:
                dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
                api.time.sleep(1.0)
                try:
                    dg645.command_inout("scpi_query", "*OPC?")
                except Exception:
                    pass
            elif policy not in {"verify", "verify_only"}:
                raise ValueError(f"Unsupported DG645 preflight policy: {policy}")

            expected_queries = dict(config.get("snapshot", {}).get("raw_queries") or {})
            expected_queries.pop("*IDN?", None)
            mismatches = []
            for command, expected in expected_queries.items():
                actual = str(dg645.command_inout("scpi_query", command)).strip()
                if not api._values_match(expected, actual):
                    mismatches.append(f"{command} expected {expected!r} got {actual!r}")

            if mismatches:
                preview = "; ".join(mismatches[:5])
                suffix = f"; +{len(mismatches) - 5} more" if len(mismatches) > 5 else ""
                raise ValueError(f"DG645 recall {recall_slot} preflight failed: {preview}{suffix}")

        def _check_device(self, label, device_name, fix=False):
            try:
                server_name = api._server_name_for_device(device_name)
                proxy = api._tango_proxy(device_name, timeout_ms=5000)
                state = str(proxy.state())
                ok = state.upper() not in {"FAULT", "UNKNOWN", "OFF"}
                if not ok and fix:
                    repair = api._restart_server_for_device(device_name)
                    proxy = api._tango_proxy(device_name, timeout_ms=5000)
                    state = str(proxy.state())
                    ok = state.upper() not in {"FAULT", "UNKNOWN", "OFF"}
                    return (api._json_ok if ok else api._json_fail)(
                        label,
                        f"state={state}",
                        device=device_name,
                        server=server_name,
                        repair=repair,
                    )
                return (api._json_ok if ok else api._json_fail)(label, f"state={state}", device=device_name, server=server_name)
            except Exception as exc:
                repair = None
                if fix:
                    try:
                        repair = api._restart_server_for_device(device_name)
                        proxy = api._tango_proxy(device_name, timeout_ms=5000)
                        state = str(proxy.state())
                        ok = state.upper() not in {"FAULT", "UNKNOWN", "OFF"}
                        return (api._json_ok if ok else api._json_fail)(
                            label,
                            f"state={state}",
                            device=device_name,
                            repair=repair,
                        )
                    except Exception as repair_exc:
                        return api._json_fail(label, repair_exc, device=device_name, repair=repair)
                return api._json_fail(label, exc, device=device_name)

        def _netio_outputs_for_device(self, device_name):
            proxy = api._tango_proxy(device_name, timeout_ms=5000)
            ids = [int(value) for value in list(proxy.read_attribute("ids").value)]
            names = [str(value) for value in list(proxy.read_attribute("names").value)]
            states = [int(value) for value in list(proxy.read_attribute("states").value)]
            return proxy, ids, names, states

        def _check_netio_output(self, item, fix=False):
            try:
                proxy, ids, names, states = self._netio_outputs_for_device(item["device"])
                output_id = int(item["output_id"])
                index = ids.index(output_id) if output_id in ids else output_id - 1
                state = int(states[index]) if 0 <= index < len(states) else 0
                name = names[index] if 0 <= index < len(names) else f"Output {output_id}"
                if state != 1 and fix:
                    next_states = list(states)
                    while len(next_states) <= index:
                        next_states.append(0)
                    next_states[index] = 1
                    proxy.command_inout("set_channels_states", next_states)
                    api.time.sleep(0.5)
                    _proxy, _ids, _names, states = self._netio_outputs_for_device(item["device"])
                    state = int(states[index]) if 0 <= index < len(states) else 0
                ok = state == 1
                return (api._json_ok if ok else api._json_fail)(
                    item["label"],
                    f"{name} output {output_id} is {'ON' if ok else 'OFF'}",
                    device=item["device"],
                    output_id=output_id,
                    state=state,
                )
            except Exception as exc:
                return api._json_fail(item["label"], exc, device=item["device"], output_id=item["output_id"])

        def _check_owis_axes(self, fix=False):
            checks = []
            aggregator = self._hardware_config["owis_aggregator_device"]
            backend = self._hardware_config["owis_backend_device"]
            axes = [
                ("Sample holder V0 axis", int(self._hardware_config["sample_stage_axis"])),
                ("Delay line long axis", int(self._hardware_config["delay_line_axis"])),
            ]
            checks.append(self._check_device("OWIS aggregator", aggregator, fix=fix))
            checks.append(self._check_device("OWIS backend", backend, fix=fix))
            for label, axis in axes:
                try:
                    proxy = api._tango_proxy(backend, timeout_ms=5000)
                    state = str(proxy.command_inout("get_status_axis", axis))
                    position = float(proxy.command_inout("read_position_axis", axis))
                    ok = "FAULT" not in state.upper() and "ERROR" not in state.upper()
                    if not ok and fix:
                        try:
                            proxy.command_inout("turn_on_axis", axis)
                            api.time.sleep(0.5)
                            state = str(proxy.command_inout("get_status_axis", axis))
                            ok = "FAULT" not in state.upper() and "ERROR" not in state.upper()
                        except Exception:
                            pass
                    checks.append((api._json_ok if ok else api._json_fail)(label, f"axis {axis}: {state}, {position:.4f} mm", axis=axis))
                except Exception as exc:
                    checks.append(api._json_fail(label, exc, axis=axis))
            return checks

        def _read_daq_counter(self, timeout_ms=5000):
            proxy = api._tango_proxy(self._hardware_config["daqmx_device"], timeout_ms=timeout_ms)
            return int(float(proxy.command_inout("read_counter", self._hardware_config["daqmx_counter_channel"])))

        def _counter_status_locked(self):
            try:
                value = self._read_daq_counter(timeout_ms=700)
                now = api.time.monotonic()
                rate = self._counter_rate_hz
                active = False
                if self._counter_last_value is not None and self._counter_last_time is not None:
                    dt = max(1e-6, now - self._counter_last_time)
                    delta = value - self._counter_last_value
                    rate = max(0.0, delta / dt)
                    self._counter_rate_hz = 0.65 * self._counter_rate_hz + 0.35 * rate
                    active = delta > 0
                self._counter_last_value = value
                self._counter_last_time = now
                return {
                    "value": value,
                    "rate_hz": round(self._counter_rate_hz if rate is not None else 0.0, 3),
                    "active": active or self._counter_rate_hz > 1.0,
                    "error": "",
                }
            except Exception as exc:
                return {"value": None, "rate_hz": 0.0, "active": False, "error": str(exc)}

        def _check_counter_activity(self, seconds=1.25):
            try:
                first = self._read_daq_counter(timeout_ms=5000)
                api.time.sleep(max(0.5, float(seconds)))
                second = self._read_daq_counter(timeout_ms=5000)
                rate = (second - first) / max(0.5, float(seconds))
                ok = second > first and rate >= 1.0
                return (api._json_ok if ok else api._json_fail)(
                    "ELYSE pulse counter",
                    f"{first} -> {second}, {rate:.2f} Hz",
                    value=second,
                    rate_hz=round(rate, 3),
                )
            except Exception as exc:
                return api._json_fail("ELYSE pulse counter", exc)

        def _check_dg645_recall(self, apply_recall=False):
            try:
                config = api._load_dg645_recall_config(self._hardware_config.get("dg645_recall_config"))
                dg645 = api._tango_proxy(self._hardware_config.get("dg645_device") or config.get("device"), timeout_ms=8000)
                recall_slot = int(config.get("recall_slot", 8))
                if apply_recall:
                    dg645.command_inout("scpi_write", f"*RCL {recall_slot}")
                    api.time.sleep(1.0)
                    try:
                        dg645.command_inout("scpi_query", "*OPC?")
                    except Exception:
                        pass
                expected_queries = dict(config.get("snapshot", {}).get("raw_queries") or {})
                expected_queries.pop("*IDN?", None)
                mismatches = []
                for command, expected in expected_queries.items():
                    actual = str(dg645.command_inout("scpi_query", command)).strip()
                    if not api._values_match(expected, actual):
                        mismatches.append(f"{command}: expected {expected!r}, got {actual!r}")
                if mismatches:
                    preview = "; ".join(mismatches[:5])
                    return api._json_fail("DG645 recall 8", preview, mismatch_count=len(mismatches))
                return api._json_ok("DG645 recall 8", "Recall 8 matches V0 DirectLine preset", recall_slot=recall_slot)
            except Exception as exc:
                return api._json_fail("DG645 recall 8", exc)

        def hardware_preflight(self, fix=False):
            with self._lock:
                if not fix:
                    # Passive diagnostics may read state/attributes and approved
                    # query commands, but never repair, move, power, recall, or
                    # start/register a camera order.
                    checks = []
                    checks.extend(self._check_owis_axes(fix=False))
                    checks.append(self._check_device("Andor UV-visible detector", self._hardware_config["andor_device"], fix=False))
                    checks.append(self._check_device("DAQmx card", self._hardware_config["daqmx_device"], fix=False))
                    checks.append(self._check_device("DG645 Tango server", self._hardware_config["dg645_device"], fix=False))
                    for item in api.REQUIRED_NETIO_OUTPUTS:
                        checks.append(self._check_netio_output(item, fix=False))
                    checks.append(self._check_dg645_recall(apply_recall=False))
                    checks.append(self._check_counter_activity())
                    ok = all(check.get("ok") for check in checks)
                    return {
                        "success": ok,
                        "fixed": False,
                        "message": "Passive hardware preflight" if ok else "Passive hardware preflight found unavailable hardware",
                        "recommendation": "Use initialize only after a human approval if repair is required.",
                        "checks": checks,
                        "counter": self._counter_status_locked(),
                    }
                self._sync_locked()
                checks = []
                checks.extend(self._check_owis_axes(fix=fix))
                checks.append(self._check_device("Andor UV-visible detector", self._hardware_config["andor_device"], fix=fix))
                checks.append(self._check_device("DAQmx card", self._hardware_config["daqmx_device"], fix=fix))
                checks.append(self._check_device("DG645 Tango server", self._hardware_config["dg645_device"], fix=fix))
                for item in api.REQUIRED_NETIO_OUTPUTS:
                    checks.append(self._check_netio_output(item, fix=fix))
                checks.append(self._check_dg645_recall(apply_recall=fix))
                checks.append(self._check_counter_activity())
                ok = all(check.get("ok") for check in checks)
                return {
                    "success": ok,
                    "fixed": bool(fix),
                    "message": "Hardware initialized" if ok else "Hardware initialization failed",
                    "recommendation": "" if ok else "Use auto-fix once. If this still fails, restart the Windows/Tango computer.",
                    "checks": checks,
                    "counter": self._counter_status_locked(),
                }

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
                if self._run_writer is not None:
                    self._finalize_run_locked("aborted", "Reset requested")
                self._reset_locked()
                self._run_status = "idle"
                self._run_error = ""
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
                        "raw_groups": list(api.RAW_GROUPS),
                    },
                    "wavelengths": self._wavelengths,
                    "delays": self._delays,
                    "heatmap": self._heatmap,
                    "live_od": self._live_od,
                    "spectra": self._last_spectra,
                }
                return self._read_tango_motion_state_locked(state)

    api.PumpProbeV0Controller = PumpProbeV0Controller
