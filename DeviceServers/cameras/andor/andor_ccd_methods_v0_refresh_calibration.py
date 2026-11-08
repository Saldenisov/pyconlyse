"""Implementation for _v0_refresh_calibration and related operations."""


def _bind_andor_ccd_methods_v0_refresh_calibration(api):
    """Bind implementation to the owning module and its runtime state."""

    def _v0_refresh_calibration(self, width):
        """V0 admits only a fresh explicit DBL calibration; no pixel fallback."""
        linked = self._coerce_str(self.linked_spectrograph_ds, "").strip()
        calibration_file = self._coerce_str(self.wavelengths_file, "").strip()
        if linked:
            axis = api.np.asarray(api.DeviceProxy(linked).read_attribute("calibration").value, dtype=api.np.float64).reshape(-1)
            source = "linked_spectrograph"
        elif calibration_file:
            # A missing/invalid configured file must not silently become a
            # property calibration or the legacy pixel-index display fallback.
            axis = api.np.loadtxt(calibration_file, dtype=api.np.float64).reshape(-1)
            source = "configured_calibration"
        else:
            axis = self._parse_array_property(self.wavelengths, dtype=api.np.float64)
            source = "configured_calibration"
        if axis.shape != (int(width),) or not api.np.all(api.np.isfinite(axis)):
            raise RuntimeError("V0 requires a finite explicit calibration matching fresh SDK width")
        self._v0_wavelengths = axis.copy()
        self._v0_axis_source = source

    def _v0_configuration(self):
        """Fresh SDK-wrapper readback under lifecycle guard, never guessed defaults."""
        camera = self.camera
        if camera is None:
            raise RuntimeError("Camera is not opened")
        for method in ("get_frames_status", "get_new_images_range", "read_multiple_images"):
            if not callable(getattr(camera, method, None)):
                raise RuntimeError(f"SDK wrapper lacks indexed read API {method}")
        buffer_size = int(camera.get_frames_status().buffer_size)
        height, width = map(int, camera.get_data_dimensions())
        axis = api.np.asarray(self._v0_wavelengths, dtype=api.np.float64)
        if axis.shape != (width,):
            raise RuntimeError("V0 calibrated axis does not match fresh SDK width")
        def optional_read(method_name):
            method = getattr(camera, method_name, None)
            if not callable(method):
                return {"method_present": False, "value": None}
            try:
                return {"method_present": True, "value": method()}
            except getattr(self, "_andor_not_supported_errors", ()) as exc:
                # Non-EM models expose the SDK2 gain getter but reject this
                # capability. Preserve that distinction in the fingerprint.
                # Communication/SDK failures must still invalidate freshness.
                return {"method_present": True, "value": None,
                        "unsupported": True, "reason": str(exc)}
        configuration = {
            "trigger_mode": str(camera.get_trigger_mode()),
            "read_mode": str(camera.get_read_mode()),
            "acquisition_mode": str(camera.get_acquisition_mode()),
            "track_count": height, "width": width,
            "exposure_seconds": float(camera.get_exposure()),
            "multi_track": list(camera.get_multi_track_mode_parameters()),
            "amplifier": list(camera.get_amp_mode()),
            "indexed_buffer_size": buffer_size,
            "wavelengths": axis.tolist(), "axis_source": self._v0_axis_source,
            # SDK2 get_roi exposes the stored image-mode ROI. Active multi-track
            # sampling is described by multi_track and data dimensions above.
            "image_mode_roi": optional_read("get_roi"),
            "emccd_gain": optional_read("get_EMCCD_gain"),
            "vertical_shift_speed": optional_read("get_vsspeed"),
            "horizontal_shift_speed": optional_read("get_hsspeed"),
            "image_indexing": optional_read("get_image_indexing"),
        }
        return configuration, bool(camera.acquisition_in_progress()) and not self.abort

    def _v0_worker_tick(self):
        # No blocking SDK wait while holding the lifecycle lock. A warm-up/stop
        # can retain this lock while joining: timed acquisition lets the worker
        # observe abort instead of deadlocking behind that join.
        lock = self._get_lifecycle_lock()
        if not lock.acquire(timeout=0.05):
            return
        try:
            if self.abort or self.camera is None:
                self._v0_orders.unavailable("Camera acquisition stopped")
                return
            if self._v0_orders.needs_arm():
                self._v0_refresh_calibration(int(self.camera.get_data_dimensions()[1]))
            configuration, active = self._v0_configuration()
            self._v0_orders.observe(configuration, active)
            frames = self._v0_orders.pump(self.camera)
            # Preserve legacy latest-frame display/order delivery; the V0 book
            # retains every indexed sample independently.
            if frames:
                self.last_image = api.np.asarray(frames[-1], dtype=api.np.float32).copy()
                self._consume_frame_for_orders(self.last_image)
        except Exception as exc:
            self._v0_orders.unavailable(str(exc))
        finally:
            lock.release()

    def wait(self, timeout=0):
        while self.abort is not True and self.camera is not None:
            try:
                if self._v0_orders.has_active():
                    self._v0_worker_tick()
                    api.sleep(0.005)
                    continue
                self.camera.wait_for_frame(timeout=1.0, error_on_stopped=False)
                frame = self.camera.read_newest_image()
                if frame is None:
                    continue
                normalized = self._normalize_frame(frame)
                self.last_image = normalized
                self._consume_frame_for_orders(normalized)
            except Exception as exc:
                self.warn(f"Andor grabbing loop warning: {exc}")
                api.sleep(0.1)

    def get_controller_status_local(self) -> api.Union[int, str]:
        if self.camera is None:
            self.set_state(api.DevState.OFF)
            return 0
        if self.grabbing:
            self.set_state(api.DevState.RUNNING)
        else:
            self.set_state(api.DevState.ON)
        return 0

    def start_grabbing_local(self):
        if not self.camera:
            return "Camera is not opened"

        if self.grabbing_thread and self.grabbing_thread.is_alive():
            return 0

        self.abort = False
        self._apply_acquisition_mode_settings()
        self.camera.setup_acquisition(mode="sequence")
        self.camera.start_acquisition()
        self._v0_orders.new_epoch()
        self.grabbing_thread = api.Thread(target=self.wait, args=[self.timeoutt], daemon=True)
        self.grabbing_thread.start()
        self.set_state(api.DevState.RUNNING)
        return 0

    def stop_grabbing_local(self):
        self.abort = True
        book = getattr(self, "_v0_orders", None)
        if book is not None:
            book.unavailable("Camera acquisition stopped")
        if self.camera:
            try:
                self.camera.stop_acquisition()
            except Exception:
                pass
        if self.grabbing_thread and self.grabbing_thread.is_alive():
            self.grabbing_thread.join(timeout=1.0)
        self.set_state(api.DevState.ON if self.camera else api.DevState.OFF)
        return 0

    def grabbing_local(self):
        return bool(self.grabbing_thread and self.grabbing_thread.is_alive() and not self.abort)

    def get_trigger_mode(self) -> int:
        return int(self.trigger_mode_value)

    def get_trigger_source(self) -> int:
        return int(self.trigger_source_value)

    def get_trigger_type(self) -> int:
        return int(self.trigger_type_value)

    def register_order_local(self, name, value):
        requested_frames = max(1, int(value[0]))
        self._refresh_wavelengths_axis(expected_width=self.current_width)
        self.orders[name] = api.FrameOrderState(
            order_length=requested_frames,
            order_done=False,
            order_timestamp=api.time(),
            ready_to_delete=False,
            order_array=api.np.array([self.wavelengths_axis_value], dtype=api.np.float32),
            frames_done=0,
        )
        return 0

    def give_order_local(self, name):
        if name in self.orders:
            order = self.orders[name]
            order.ready_to_delete = True
            return api.np.asarray(order.order_array, dtype=api.np.float32)

        if self.last_image is None:
            self.get_image()
        if self.last_image is None:
            return api.np.array([self.wavelengths_axis_value], dtype=api.np.float32)
        return api.np.vstack([self.wavelengths_axis_value, self.last_image]).astype(
            api.np.float32
        )

    return {
        "_v0_refresh_calibration": _v0_refresh_calibration,
        "_v0_configuration": _v0_configuration,
        "_v0_worker_tick": _v0_worker_tick,
        "wait": wait,
        "get_controller_status_local": get_controller_status_local,
        "start_grabbing_local": start_grabbing_local,
        "stop_grabbing_local": stop_grabbing_local,
        "grabbing_local": grabbing_local,
        "get_trigger_mode": get_trigger_mode,
        "get_trigger_source": get_trigger_source,
        "get_trigger_type": get_trigger_type,
        "register_order_local": register_order_local,
        "give_order_local": give_order_local,
    }
