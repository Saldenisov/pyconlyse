"""Implementation for _start_emulator_run_locked and related operations."""


def _bind_pump_probe_v0_api_methods_start_emulator_run_locked(api):
    """Bind implementation to the owning module and its runtime state."""

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
                "h5": api._publish_data_file(self._run_output_dir, staged["h5_path"]),
                "dat": api._publish_data_file(self._run_output_dir, staged["dat_path"]),
                "manifest": api._publish_data_file(self._run_output_dir, staged["manifest_path"]),
                "frame_counts": staged["frame_counts"],
                "parent_run_id": staged.get("parent_run_id"),
                "next_point_index": staged.get("next_point_index"),
                "next_shot_index": staged.get("next_shot_index"),
                "scan_plan_fingerprint": staged.get("scan_plan_fingerprint"),
                "raw_layout": staged.get("raw_layout"),
                "tango_profile_fingerprint": staged.get("tango_profile_fingerprint"),
            }
            self._run_status = status
            self._run_error = str(error)
        except Exception as exc:
            self._resume_source = None
            self._run_status = "fault"
            self._run_error = f"Run storage failed: {exc}"
        finally:
            self._run_writer = None

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

    def _check_device(
        self,
        label,
        device_name,
        fix=False,
        starter_name=None,
        starter_running=None,
        on_progress=None,
    ):
        repair = None
        errors = []
        server_name = None

        def ready(proxy):
            state = str(proxy.state()).upper().rsplit(".", 1)[-1]
            if state not in {"ON", "RUNNING", "MOVING"}:
                return False
            if device_name == self._hardware_config["dg645_device"]:
                return bool(str(proxy.command_inout("scpi_query", "*IDN?")).strip())
            if device_name in api.V0_PDU_DEVICES:
                return bool(list(proxy.read_attribute("ids").value))
            return True

        try:
            server_name = api._server_name_for_device(device_name)
            # A composite or a rewired configuration must not indirectly repair
            # a STANDA axis. Only its Elysium2 owner may initialise it.
            if server_name.lower().startswith("ds_standa_motor/"):
                fix = False
                if starter_name != api.V0_STANDA_STARTER_DEVICE:
                    starter_name = api.V0_STANDA_STARTER_DEVICE
                    starter = api._tango_proxy(starter_name, timeout_ms=2500)
                    starter_running = set(starter.command_inout("DevGetRunningServers", True))
            stopped = (
                starter_running is not None and server_name not in starter_running
            )
            if stopped and not fix:
                raise RuntimeError(f"{server_name} is not running on {starter_name}")
            # An initially stopped shared server may already have been started
            # for another device in this preparation pass.
            if stopped and fix:
                starter = api._tango_proxy(starter_name, timeout_ms=5000)
                stopped = server_name not in set(starter.command_inout("DevGetRunningServers", False))
            if stopped:
                if on_progress:
                    on_progress(f"Starting missing server {server_name} on {starter_name}")
                repair = api._restart_server_for_device(device_name, preferred_starter=starter_name)
                starter_running.add(server_name)
            try:
                proxy = api._tango_proxy(device_name, timeout_ms=5000)
                ok = ready(proxy)
                if not ok:
                    errors.append(f"Initial state={proxy.state()}")
            except Exception as exc:
                proxy = None
                ok = False
                errors.append(str(exc))
            if not ok and fix and proxy is not None:
                ok, recovery_errors = api.recover_device(
                    proxy, ready, ("recover", "turn_on", "Init", "turn_on"),
                    on_progress=on_progress,
                )
                errors.extend(recovery_errors)
                if ok:
                    repair = repair or {"action": "reinitialized"}
            # Never stop an existing SDK process or replay a timed-out Init.
            # Report this branch and continue checking independent equipment.
            state = str(proxy.state()) if proxy is not None else "UNREACHABLE"
            detail = f"state={state}; hardware verified" if ok else (
                f"state={state}; {'; '.join(errors)}. Check power and connection, then press Prepare again."
            )
            return (api._json_ok if ok else api._json_fail)(
                label, detail, device=device_name, server=server_name,
                starter=starter_name, repair=repair,
            )
        except Exception as exc:
            return api._json_fail(
                label, f"{exc}; {'; '.join(errors)}", device=device_name,
                server=server_name, starter=starter_name, repair=repair,
            )

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
            if output_id not in ids or len(ids) != len(states):
                raise RuntimeError(f"PDU output {output_id} is missing or its state readback is invalid")
            index = ids.index(output_id)
            state = int(states[index]) if 0 <= index < len(states) else 0
            name = names[index] if 0 <= index < len(names) else f"Output {output_id}"
            if state != 1 and fix:
                # NETIO Action 5 means No Change. Do not rewrite stale states
                # of unrelated outlets (in particular the streak-camera supply).
                next_states = [5] * len(states)
                next_states[index] = 1
                proxy.command_inout("set_channels_states", next_states)
                api.time.sleep(max(0.5, float(item.get("settle_seconds", 0.5))))
                _proxy, _ids, _names, states = self._netio_outputs_for_device(item["device"])
                if output_id not in _ids or len(_ids) != len(states):
                    raise RuntimeError(f"PDU output {output_id} readback is unavailable")
                index = _ids.index(output_id)
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

    return {
        "_start_emulator_run_locked": _start_emulator_run_locked,
        "_run_emulator_loop": _run_emulator_loop,
        "_finalize_run_locked": _finalize_run_locked,
        "_apply_pulse_locked": _apply_pulse_locked,
        "configure": configure,
        "hardware_config": hardware_config,
        "set_running": set_running,
        "set_real_time": set_real_time,
        "set_faraday": set_faraday,
        "move_stage": move_stage,
        "stop_stage": stop_stage,
        "move_sample_stage": move_sample_stage,
        "stop_sample_stage": stop_sample_stage,
        "_owis_aggregator_locked": _owis_aggregator_locked,
        "_move_owis_axis_locked": _move_owis_axis_locked,
        "_stop_owis_axis_locked": _stop_owis_axis_locked,
        "_preflight_dg645_locked": _preflight_dg645_locked,
        "_check_device": _check_device,
        "_netio_outputs_for_device": _netio_outputs_for_device,
        "_check_netio_output": _check_netio_output,
    }
