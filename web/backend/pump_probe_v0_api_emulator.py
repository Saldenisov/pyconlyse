"""V0 emulator controller operations."""


def bind(api):
    class V0Emulator:
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
                kinetics = api.preview_kinetics(delay)
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
                if self._tango_stop_event is not None:
                    # Full acquisition is owned by the authorized worker.
                    return
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
            if payload_rows.shape[0] % track_count:
                raise ValueError("Andor order contains an incomplete signal/reference pair")
            frame_count = payload_rows.shape[0] // track_count
            if frame_count < 1:
                raise ValueError("Andor order contains no spectra")
            tracks = payload_rows.reshape(frame_count, track_count, width)
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
            # Validate the entire positional schedule before replacing any displayed
            # data or opening a writer. A clamp would merge distinct delay points.
            plan = self._current_scan_plan_locked()
            continuing = payload.get("run_action", "new") == "continue"
            if continuing and not self._resume_available_locked():
                raise ValueError("No stopped run matches the current scan plan; restore its settings or start a new run")
            output_dir = str(payload.get("save_path") or "").strip()
            if continuing and not output_dir:
                output_dir = self._run_output_dir
            if not output_dir:
                raise ValueError("Choose a data folder before starting an emulator run")
            output_dir = api._normalize_data_path(output_dir)
            if not api._is_data_path_allowed(output_dir):
                raise ValueError("Run output path is outside pump-probe data root")

            sample_name = str(payload.get("sample_name", self._run_sample_name if continuing else "") or "").strip()
            run_config = {
                "experiment": "V0 DirectLine pump-probe",
                "mode": "emulator",
                "sample_name": sample_name,
                "settings": dict(self._settings),
                "hardware_config": dict(self._hardware_config),
                "raw_groups": list(api.RAW_GROUPS),
                "spectrometer": {"rate_hz": api.SPECTROMETER_HZ, "burst": api.SPECTROMETER_BURST},
                "accelerator_hz": api.ACCELERATOR_HZ,
            }
            if continuing:
                writer = api.V0EmulatorRunWriter.resume_from(
                    self._resume_source["h5_path"], run_config, expected_plan=plan,
                    expected_wavelengths=self._wavelengths,
                )
            else:
                writer = api.V0EmulatorRunWriter(
                    self._wavelengths, plan.delays, plan.positions,
                    plan.shots_per_point, run_config, plan=plan,
                )
            previous_position = self._position_mm
            previous_faraday = self._faraday_closed
            self._reset_locked()
            self._position_mm = previous_position
            self._faraday_closed = previous_faraday
            self._run_writer = writer
            self._scan_plan = plan
            self._tango_run_plan = None
            self._run_raw_groups = tuple(api.RAW_GROUPS)
            self._resume_source = None
            self._run_output_dir = output_dir
            self._run_sample_name = sample_name
            checkpoint = writer.artifacts()
            counts = checkpoint["frame_counts"]
            next_index = checkpoint.get("next_point_index")
            self._current_index = int(next_index if next_index is not None else 0)
            self._pulses_at_point = int(counts[self._current_index])
            self._total_pulses = sum(counts)
            self._spectrometer_frames = self._total_pulses * len(api.RAW_GROUPS)
            self._set_position_mm = plan.positions[self._current_index]
            if continuing:
                for index, count in enumerate(counts):
                    if count:
                        values = writer.od_for_delay(index)
                        self._heatmap[index] = [float(value) if api.np.isfinite(value) else None for value in values]
                if counts[self._current_index]:
                    self._live_od = self._heatmap[self._current_index]
            self._run_status = "running"
            self._run_error = ""
            self._run_artifacts = {}
            self._running = True
            self._real_time = False
            self._last_pulse_update = api.time.monotonic()
            self._run_thread = api.threading.Thread(
                target=self._run_emulator_loop,
                args=(writer.run_id,),
                name=f"pump-probe-v0-{self._run_writer.run_id}",
                daemon=True,
            )
            self._run_thread.start()

        def _run_emulator_loop(self, run_id):
            """Advance a scan independently from HTTP state polling."""
            while True:
                with self._lock:
                    if (not self._running or self._run_writer is None
                            or self._run_writer.run_id != run_id):
                        return
                    self._sync_locked()
                api.time.sleep(0.02)

        def _apply_pulse_locked(self):
            if not self._running and not self._real_time:
                return

            if self._running and self._run_writer is not None:
                if (self._scan_plan is None
                        or self._set_position_mm != self._scan_plan.positions[self._current_index]):
                    self._finalize_run_locked("fault", "Delay target no longer matches the immutable scan plan")
                    return
                if abs(self._set_position_mm - self._position_mm) > 0.0005:
                    return
                try:
                    frames = self._emulator_raw_cycle_locked(self._current_index)
                    self._live_od = self._run_writer.record_cycle(
                        self._current_index,
                        frames,
                        self._set_position_mm,
                        self._position_mm,
                    )
                    self._total_pulses += 1
                    self._spectrometer_frames += len(frames)
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
                self._set_position_mm = self._scan_plan.positions[self._current_index]
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

    return V0Emulator
