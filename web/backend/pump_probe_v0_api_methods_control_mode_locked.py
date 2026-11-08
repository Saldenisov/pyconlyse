"""Implementation for _control_mode_locked and related operations."""


def _bind_pump_probe_v0_api_methods_control_mode_locked(api):
    """Bind implementation to the owning module and its runtime state."""

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

    def _current_scan_plan_locked(self):
        return api.build_scan_plan(self._settings, api.MM_PER_PS, api.STAGE_MIN_MM, api.STAGE_MAX_MM)

    def _resume_available_locked(self):
        source = self._resume_source
        if source is None:
            return False
        if self._tango_stop_event is not None:
            return False
        try:
            matches = (source["plan"].fingerprint == self._current_scan_plan_locked().fingerprint
                    and source["wavelengths"] == tuple(self._wavelengths)
                    and source["hardware_config"] == self._hardware_config)
            if not matches:
                return False
            if self._control_mode_locked() == "tango":
                profile = self._load_tango_profile_locked()
                timing = api._load_dg645_recall_config(self._hardware_config["dg645_recall_config"])
                timing_sha = api.hashlib.sha256(api.json.dumps(timing, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
                return (source.get("mode") == "tango"
                        and source.get("dg645_sha256") == timing_sha
                        and source.get("profile_fingerprint") == api.V0TangoRunWriter.profile_fingerprint({"tango_profile": profile}))
            return source.get("mode", "emulator") == "emulator"
        except (ValueError, OSError):
            return False

    def _load_tango_profile_locked(self):
        path = api.os.environ.get("PYCONLYSE_V0_TANGO_PROFILE") or str(
            api.Path(api.__file__).resolve().parents[1] / "pump_probe" / "config" / "v0_tango_raw_profile.json")
        return api.load_profile(path)

    def prepare_tango_run(self, payload, *, require_commissioned=True):
        """Compute exact approval content without constructing any device proxy."""
        with self._lock:
            if self._run_writer is not None or not self._tango_done_event.is_set():
                raise RuntimeError("Wait for the active run and its device cleanup to finish")
            if self._tango_cleanup_errors:
                raise RuntimeError("Previous Tango cleanup is unresolved; recover retained RAW/device state before restarting acquisition")
            if self._control_mode_locked() != "tango":
                raise ValueError("Select Tango mode before preparing a Tango run")
            action = payload.get("run_action", "new")
            if action not in {"new", "continue", "overwrite"}:
                raise ValueError("Tango start action must be new, continue, or overwrite")
            profile = self._load_tango_profile_locked()
            if require_commissioned and profile.get("commissioned") is not True:
                raise api.TangoProfileNotCommissioned("Tango RAW profile is not commissioned: verify BG_level for the Andor ROI/readout and set commissioned=true in the server profile")
            checkpoint = None
            if action == "continue":
                if not self._resume_available_locked():
                    raise ValueError("No stopped Tango run matches the current profile and scan plan")
                source = self._resume_source
                checkpoint = {"run_id": source["run_id"], "source_sha256": api.hashlib.sha256(api.Path(source["h5_path"]).read_bytes()).hexdigest(),
                              "frame_counts": list(source["frame_counts"]),
                              "next_point_index": source["next_point_index"],
                              "next_shot_index": source["next_shot_index"],
                              "camera_config_fingerprint": source["camera_config_fingerprint"]}
            recall = api._load_dg645_recall_config(self._hardware_config["dg645_recall_config"])
            output = str(payload.get("save_path") or (self._run_output_dir if action == "continue" else "")).strip()
            if not output:
                raise ValueError("Choose a data folder before preparing a Tango run")
            output = api._normalize_data_path(output)
            if not api._is_data_path_allowed(output):
                raise ValueError("Run output path is outside pump-probe data root")
            output_context = {"output_dir": output,
                              "sample_name": str(payload.get("sample_name") or self._run_sample_name or "").strip()}
            return api.build_tango_plan(self._current_scan_plan_locked(), dict(self._hardware_config), profile, recall,
                                    run_action=action, checkpoint=checkpoint, output_context=output_context)

    def _start_tango_run_locked(self, payload, plan):
        if self.prepare_tango_run(payload).fingerprint != plan.fingerprint:
            raise ValueError("Tango run configuration changed after plan authorization")
        continuing = payload.get("run_action", "new") == "continue"
        output = str(payload.get("save_path") or (self._run_output_dir if continuing else "")).strip()
        if not output:
            raise ValueError("Choose a data folder before starting a Tango run")
        output = api._normalize_data_path(output)
        if not api._is_data_path_allowed(output):
            raise ValueError("Run output path is outside pump-probe data root")
        self._run_output_dir = output
        self._run_sample_name = str(payload.get("sample_name") or self._run_sample_name or "").strip()
        self._tango_run_plan = plan
        self._scan_plan = plan.scan_plan
        self._tango_stop_event = api.threading.Event()
        self._tango_done_event.clear()
        self._tango_stop_status = "stopped"
        self._tango_order_id = None
        self._tango_rejected_cycles = 0
        self._tango_cleanup_errors = []
        self._tango_camera_fingerprint = None
        self._tango_reset_requested = False
        self._run_raw_groups = api.TRANCON_GROUPS
        self._run_status = "preparing"
        self._run_error = ""
        self._run_artifacts = {}
        self._running = True
        self._real_time = False
        self._andor_order = None
        if not continuing:
            self._resume_source = None
            self._delays = list(plan.scan_plan.delays)
            self._heatmap = [[None for _ in self._wavelengths] for _ in self._delays]
            self._live_od = [None for _ in self._wavelengths]
            self._current_index = self._pulses_at_point = self._total_pulses = self._spectrometer_frames = 0
        context = {
            "id": api.uuid.uuid4().hex, "plan": plan, "stop": self._tango_stop_event,
            "checkpoint": dict(self._resume_source) if continuing else None,
            "settings": api.json.loads(api.json.dumps(self._settings)), "sample_name": self._run_sample_name,
            "done": self._tango_done_event,
        }
        self._tango_context_id = context["id"]
        self._run_thread = api.threading.Thread(target=self._run_tango_loop, args=(context,),
                                            name="v0-tango-" + context["id"], daemon=True)
        self._run_thread.start()

    def _request_tango_stop_locked(self, status="stopped"):
        self._running = False
        self._real_time = False
        self._andor_order = None
        if status == "aborted" or self._tango_stop_status != "aborted":
            self._tango_stop_status = status
        self._run_status = "stopping"
        self._tango_stop_event.set()

    def wait_for_tango_cleanup(self, timeout=15.0):
        if not self._tango_done_event.wait(timeout):
            raise RuntimeError("Tango acquisition has not stopped; device power must remain on")
        if self._tango_cleanup_errors:
            raise RuntimeError("Tango acquisition cleanup failed: " + "; ".join(self._tango_cleanup_errors))

    def _run_tango_loop(self, context):
        plan, stop = context["plan"], context["stop"]
        identity = context["id"]
        writer = None
        status, error = "completed", ""

        def current():
            return self._tango_context_id == identity and self._tango_stop_event is stop

        def on_motion(position, target, moving):
            with self._lock:
                if current():
                    self._position_mm, self._set_position_mm = position, target

        def on_order(order):
            with self._lock:
                if current():
                    self._tango_order_id = order

        adapter = api.TangoRawAdapter(plan, api._tango_proxy, stop, on_motion=on_motion, on_order=on_order)
        try:
            checkpoint = context["checkpoint"]
            if checkpoint:
                expected_hash = plan.to_dict()["checkpoint"]["source_sha256"]
                if api.hashlib.sha256(api.Path(checkpoint["h5_path"]).read_bytes()).hexdigest() != expected_hash:
                    raise ValueError("Stopped RAW checkpoint changed after authorization")
            wavelengths = adapter.open()
            if checkpoint and adapter.capabilities["config_fingerprint"] != plan.to_dict()["checkpoint"]["camera_config_fingerprint"]:
                raise ValueError("Andor readout configuration differs from the stopped RAW checkpoint")
            with self._lock:
                if current():
                    self._tango_camera_fingerprint = adapter.capabilities["config_fingerprint"]
            if stop.is_set():
                raise api.AcquisitionCancelled("Acquisition cancelled during preparation")
            config = {"experiment": "V0 DirectLine pump-probe", "mode": "tango",
                      "settings": context["settings"], "sample_name": context["sample_name"],
                      "hardware_config": plan.hardware_config, "tango_profile": plan.profile,
                      "tango_run_plan": plan.to_dict(), "raw_groups": list(api.TRANCON_GROUPS)}
            if checkpoint:
                writer = api.V0TangoRunWriter.resume_from(checkpoint["h5_path"], config,
                         expected_plan=plan.scan_plan, expected_wavelengths=wavelengths)
            else:
                writer = api.V0TangoRunWriter(wavelengths, plan.scan_plan.delays, plan.scan_plan.positions,
                                         plan.scan_plan.shots_per_point, config, plan=plan.scan_plan)
            with self._lock:
                if not current() or stop.is_set():
                    raise api.AcquisitionCancelled("Acquisition cancelled before the first point")
                self._run_writer = writer
                self._resume_source = None
                self._wavelengths = wavelengths.tolist()
                self._delays = list(plan.scan_plan.delays)
                counts = writer.artifacts()["frame_counts"]
                self._heatmap = [[float(v) if api.np.isfinite(v) else None for v in writer.od_for_delay(i)] for i in range(len(counts))]
                self._total_pulses = sum(counts)
                self._spectrometer_frames = 3 * sum(counts)
                self._run_status = "running"
            for point, target in enumerate(plan.scan_plan.positions):
                acquired = writer.artifacts()["frame_counts"][point]
                if acquired == plan.scan_plan.shots_per_point:
                    continue
                with self._lock:
                    if not current() or stop.is_set():
                        raise api.AcquisitionCancelled("Acquisition cancelled before point motion")
                    self._current_index, self._pulses_at_point = point, acquired
                readback = adapter.move_to(point)
                rejected = 0
                while acquired < plan.scan_plan.shots_per_point:
                    # Similarity uses the minimum over the supplied batch. The
                    # source requests all remaining cycles, not singleton shots.
                    batch = adapter.acquire_batch(writer.run_id, point, plan.scan_plan.shots_per_point - acquired)
                    for exc in batch.rejected:
                        writer.record_rejected_transport(exc.packet, exc.metadata, str(exc))
                        rejected += 1
                    if batch.cycles:
                        admission = api.apply_detector_filters(api.np.stack([c.frames for c in batch.cycles]), plan.profile)
                        selected = set(admission["accepted_indices"])
                        for index, cycle in enumerate(batch.cycles):
                            metadata = {**cycle.metadata, "detector_filters": admission["details"],
                                        "filter_source_index": index, "filter_reasons": admission["reasons"][index]}
                            if index not in selected:
                                writer.record_rejected_transport(cycle.packet, metadata,
                                                                 "; ".join(admission["reasons"][index]))
                                rejected += 1
                                continue
                            with self._lock:
                                cancelled = not current() or stop.is_set()
                                if cancelled:
                                    writer.record_rejected_transport(batch.packet,
                                        {"source_envelope": batch.envelope, "source_order_id": batch.envelope["order_id"],
                                         "first_uncommitted_cycle": cycle.metadata["packet_cycle_index"]},
                                        "Cancelled before remaining RAW commits; entire source packet retained")
                                else:
                                    row = writer.record_tango_cycle(point, cycle.frames, target, readback,
                                                                   cycle.packet, metadata)
                                    acquired += 1
                                    self._pulses_at_point = acquired
                                    self._total_pulses += 1
                                    self._spectrometer_frames += 3
                                    self._live_od, self._heatmap[point] = row, row
                                    self._last_spectra = {"background": cycle.frames[1].tolist(),
                                                          "signal": cycle.frames[3].tolist(), "reference": cycle.frames[5].tolist(),
                                                          "background_available": True}
                            if cancelled:
                                writer.flush_transport()
                                adapter.acknowledge_cycle()
                                raise api.AcquisitionCancelled("Acquisition cancelled before RAW commit")
                    # Camera release follows durable RAW/journal flushes.
                    writer.flush_transport()
                    adapter.acknowledge_cycle()
                    with self._lock:
                        if current():
                            self._tango_rejected_cycles += len(batch.rejected) + (len(admission["rejected_indices"]) if batch.cycles else 0)
                    if rejected > plan.profile["max_rejected_cycles"]:
                        raise RuntimeError("Detector rejection budget exceeded; check background and detector filter profile")
                    if stop.is_set():
                        raise api.AcquisitionCancelled("Acquisition cancelled after RAW commit")
        except api.AcquisitionCancelled:
            status = self._tango_stop_status
        except api.TangoPacketError as exc:
            status, error = "fault", str(exc)
            if writer is not None:
                try:
                    writer.record_rejected_transport(exc.packet, exc.metadata, str(exc))
                    writer.flush_transport()
                    adapter.acknowledge_cycle()
                except Exception as journal_error:
                    error += "; RAW journal: " + str(journal_error)
        except Exception as exc:
            status, error = "fault", str(exc)
        finally:
            try:
                partial = adapter.close()
                if partial is not None:
                    if writer is None:
                        raise RuntimeError("Unjournaled camera packet retained in device server")
                    writer.record_rejected_transport(*partial, "Incomplete order retained during cleanup")
                    writer.flush_transport()
                    adapter.acknowledge_cycle()
            except Exception as cleanup_error:
                adapter.cleanup_errors.append("RAW cleanup/journal: " + str(cleanup_error))
            try:
                if adapter.cleanup_errors:
                    status = "fault"
                    error = "; ".join(filter(None, [error, *adapter.cleanup_errors]))
                with self._lock:
                    if current():
                        self._tango_cleanup_errors = list(adapter.cleanup_errors)
                        if writer is not None:
                            self._run_writer = writer
                            self._finalize_run_locked(status, error)
                        else:
                            self._running = False
                            self._run_status, self._run_error = status, error
                        if self._tango_reset_requested and status != "fault" and self._run_status != "fault":
                            self._reset_locked()
                            self._run_status, self._run_error = "idle", ""
                            self._resume_source = None
                            self._scan_plan = None
                        self._tango_stop_event = None
                        self._tango_order_id = adapter.pending_order
                    elif writer is not None and not writer._closed:
                        writer.finalize("aborted", "Run context was replaced")
            finally:
                context["done"].set()

    return {
        "_control_mode_locked": _control_mode_locked,
        "_configure_hardware_locked": _configure_hardware_locked,
        "_reset_locked": _reset_locked,
        "_make_delays_locked": _make_delays_locked,
        "_delay_to_mm": _delay_to_mm,
        "_make_od_row_locked": _make_od_row_locked,
        "_make_spectra_locked": _make_spectra_locked,
        "_sync_locked": _sync_locked,
        "_decode_andor_order_locked": _decode_andor_order_locked,
        "_sync_andor_spectra_locked": _sync_andor_spectra_locked,
        "_sync_sample_stage_locked": _sync_sample_stage_locked,
        "_emulator_raw_cycle_locked": _emulator_raw_cycle_locked,
        "_current_scan_plan_locked": _current_scan_plan_locked,
        "_resume_available_locked": _resume_available_locked,
        "_load_tango_profile_locked": _load_tango_profile_locked,
        "prepare_tango_run": prepare_tango_run,
        "_start_tango_run_locked": _start_tango_run_locked,
        "_request_tango_stop_locked": _request_tango_stop_locked,
        "wait_for_tango_cleanup": wait_for_tango_cleanup,
        "_run_tango_loop": _run_tango_loop,
    }
