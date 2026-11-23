"""V0 tango run controller operations."""


def bind(api):
    class V0TangoRun:
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
                    profile = source["tango_profile"] if source.get("diagnostic_dark") else self._load_tango_profile_locked()
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
                api.Path(__file__).resolve().parents[1] / "pump_probe" / "config" / "v0_tango_raw_profile.json")
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
                profile = api.diagnostic_profile(self, payload, self._load_tango_profile_locked())
                if require_commissioned and not profile.get("diagnostic_dark") and profile.get("commissioned") is not True:
                    raise api.TangoProfileNotCommissioned("Tango RAW profile is not commissioned: verify BG_level for the Andor ROI/readout and set commissioned=true in the server profile")
                if profile.get("diagnostic_dark") and self._hardware_config.get("dg645_preflight_policy") != "verify_only":
                    raise ValueError("Dark checkout requires prepared DG645 timing in verify_only mode; generator settings are retained")
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
                h5_directory = api._native_run_directory(plan.to_dict()["output_context"]["output_dir"])
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
                             expected_plan=plan.scan_plan, expected_wavelengths=wavelengths,
                             h5_directory=h5_directory)
                else:
                    writer = api.V0TangoRunWriter(wavelengths, plan.scan_plan.delays, plan.scan_plan.positions,
                                             plan.scan_plan.shots_per_point, config, plan=plan.scan_plan,
                                             h5_directory=h5_directory)
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

    return V0TangoRun
