"""Implementation for _coerce_int and related operations."""


def _bind_andor_ccd_methods_coerce_int(api):
    """Bind implementation to the owning module and its runtime state."""

    def _coerce_int(value, default: int) -> int:
        try:
            if value is None or value == "":
                return int(default)
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _coerce_float(value, default: float) -> float:
        try:
            if value is None or value == "":
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _coerce_str(value, default: str) -> str:
        if value is None:
            return str(default)
        text = str(value).strip()
        return text if text else str(default)

    def _parse_array_property(self, raw_value, dtype=api.np.float32) -> api.np.ndarray:
        if isinstance(raw_value, api.np.ndarray):
            return raw_value.astype(dtype)

        text = str(raw_value or "").strip()
        if not text:
            return api.np.array([], dtype=dtype)

        try:
            parsed = api.ast.literal_eval(text)
        except Exception:
            return api.np.array([], dtype=dtype)

        try:
            return api.np.asarray(parsed, dtype=dtype).reshape(-1)
        except Exception:
            return api.np.array([], dtype=dtype)

    def _parse_wavelengths(self, dtype=api.np.float32) -> api.np.ndarray:
        calibration_path = self._coerce_str(self.wavelengths_file, "").strip()
        if calibration_path:
            try:
                return api.np.loadtxt(calibration_path, dtype=dtype).reshape(-1)
            except Exception as exc:
                self.warn(
                    f"Could not read wavelength calibration from {calibration_path}: {exc}"
                )
        return self._parse_array_property(self.wavelengths, dtype=dtype)

    def _create_camera(self):
        Andor = api.get_andor_module(sdk_path=self.dll_path)
        self._andor_not_supported_errors = (Andor.AndorNotSupportedError,)
        ini_path = self._coerce_str(self.ini_path, "")
        return Andor.AndorSDK2Camera(
            idx=self._coerce_int(self.camera_index, 0),
            ini_path=ini_path,
            temperature=self._coerce_int(self.default_temperature, -50),
            fan_mode=self._coerce_str(self.fan_mode, "full"),
        )

    def _with_temp_camera(self):
        camera = self._create_camera()
        try:
            yield camera
        finally:
            try:
                camera.close()
            except Exception:
                pass

    def _sync_from_camera(self, camera) -> None:
        info = camera.get_device_info()
        if hasattr(info, "serial_number") or hasattr(info, "head_model"):
            self.serial_number_real = getattr(info, "serial_number", -1)
            self.head_name = getattr(info, "head_model", "Andor")
        elif isinstance(info, tuple):
            if len(info) >= 3:
                self.serial_number_real = info[2]
            if len(info) >= 2:
                self.head_name = str(info[1])
            elif len(info) >= 1:
                self.head_name = str(info[0])
        detector_width, detector_height = camera.get_detector_size()
        self.current_width = int(detector_width)
        self.current_height = int(camera.get_data_dimensions()[0])
        self.height_value = int(detector_height)
        self.track_count_value = max(1, int(camera.get_data_dimensions()[0]))
        self.exposure_time_local = float(camera.get_exposure())
        timings = camera.get_cycle_timings()
        self.accumulate_time_local = float(getattr(timings, "accum_cycle_time", 0.0))
        self.kinetic_time_local = float(getattr(timings, "kinetic_cycle_time", 0.0))
        self.current_read_mode = str(camera.get_read_mode())
        self.current_acquisition_mode = str(camera.get_acquisition_mode())
        self._update_amp_mode_state(camera)
        self._update_temperature_status(camera)
        self._update_image_geometry_from_mode(camera)

    def _update_image_geometry_from_mode(self, camera) -> None:
        try:
            dims = camera.get_data_dimensions()
            if len(dims) == 2:
                self.current_height = int(dims[0])
                self.current_width = int(dims[1])
                self.track_count_value = max(1, int(dims[0]))
        except Exception:
            pass

        if self.current_read_mode == "image":
            try:
                _, _, _, _, hbin, vbin = camera.get_image_mode_parameters()
                self.binning_horizontal_value = int(hbin)
                self.binning_vertical_value = int(vbin)
            except Exception:
                self.binning_horizontal_value = 1
                self.binning_vertical_value = 1
        else:
            self.binning_horizontal_value = 1
            self.binning_vertical_value = 1

    def _update_temperature_status(self, camera=None) -> None:
        cam = camera or self.camera
        if cam is None:
            return

        try:
            self.temperature_value = float(cam.get_temperature())
        except Exception:
            pass
        try:
            self.temperature_target_value = float(cam.get_temperature_setpoint())
        except Exception:
            pass
        try:
            self.temperature_status_value = str(cam.get_temperature_status())
        except Exception:
            pass
        try:
            self.cooler_on_value = bool(cam.is_cooler_on())
        except Exception:
            pass

    def _update_amp_mode_state(self, camera) -> None:
        try:
            amp_mode = camera.get_amp_mode(full=False)
            if len(amp_mode) >= 4:
                self.ad_channel_value = int(amp_mode[0])
                self.oamp_value = int(amp_mode[1])
                self.hsspeed_value = int(amp_mode[2])
                self.gain_value = int(amp_mode[3])
        except Exception:
            pass

        try:
            amp_modes = camera.get_all_amp_modes()
            if amp_modes:
                self.n_gains_max = max(int(mode[6]) for mode in amp_modes)
        except Exception:
            self.n_gains_max = max(self.n_gains_max, self.gain_value)

        try:
            self.vsspeed_value = int(camera.get_vsspeed())
        except Exception:
            pass

    def _refresh_wavelengths_axis(self, expected_width: api.Optional[int] = None) -> None:
        width = self._coerce_int(expected_width or self.current_width or self.width, 1064)
        axis = api.np.array([], dtype=api.np.float32)
        axis64 = api.np.array([], dtype=api.np.float64)
        axis_source = "pixel_index"

        linked_device_name = self._coerce_str(self.linked_spectrograph_ds, "").strip()
        if linked_device_name:
            try:
                linked_ds = api.DeviceProxy(linked_device_name)
                linked_axis = linked_ds.read_attribute("calibration").value
                axis = api.np.asarray(linked_axis, dtype=api.np.float32).reshape(-1)
                axis64 = api.np.asarray(linked_axis, dtype=api.np.float64).reshape(-1)
                axis_source = "linked_spectrograph"
            except Exception as exc:
                self.warn(f"Could not read calibration from {linked_device_name}: {exc}")

        if axis.size == 0:
            axis = api.np.asarray(self._default_wavelengths, dtype=api.np.float32).reshape(-1)
            axis64 = api.np.asarray(self._v0_default_wavelengths, dtype=api.np.float64).reshape(-1)
            axis_source = "configured_calibration"
            if axis.size != width and self._coerce_str(self.wavelengths_file, "").strip():
                axis = self._parse_wavelengths()
                if axis.size:
                    self._default_wavelengths = axis
                    axis64 = self._parse_wavelengths(dtype=api.np.float64)
                    self._v0_default_wavelengths = axis64

        if axis.size != width:
            axis = api.np.arange(width, dtype=api.np.float32)
            axis64 = api.np.arange(width, dtype=api.np.float64)
            axis_source = "pixel_index"

        self.wavelengths_axis_value = axis
        self._v0_wavelengths = axis64
        self._v0_axis_source = axis_source
        self.current_width = int(axis.size)

    def _normalize_frame(self, frame) -> api.np.ndarray:
        frame_array = api.np.asarray(frame, dtype=api.np.float32)
        if frame_array.ndim == 1:
            frame_array = frame_array[api.np.newaxis, :]
        elif frame_array.ndim > 2:
            frame_array = frame_array.reshape(frame_array.shape[0], -1)

        self.current_height = int(frame_array.shape[0])
        self.current_width = int(frame_array.shape[1])
        self.track_count_value = max(1, int(frame_array.shape[0]))
        self._refresh_wavelengths_axis(expected_width=self.current_width)
        return frame_array

    def _consume_frame_for_orders(self, frame: api.np.ndarray) -> None:
        time_stamp = api.time_ns()
        self.time_stamp_deque.append(time_stamp)
        self.data_deque.append(frame.copy())

        if not self.orders:
            return

        orders_to_delete = []
        for order_name, order_info in list(self.orders.items()):
            if (api.time() - order_info.order_timestamp) >= 100:
                orders_to_delete.append(order_name)
                continue

            if order_info.order_done:
                continue

            order_info.order_array = api.np.vstack([order_info.order_array, frame])
            order_info.frames_done += 1
            if order_info.frames_done >= order_info.order_length:
                order_info.order_done = True

        for order_name in orders_to_delete:
            self.orders.pop(order_name, None)

    def find_device(self) -> api.Tuple[int, str]:
        # Do not open and immediately close the USB camera just to probe it.
        # ``turn_on_local`` performs the single SDK initialization and then
        # reads the camera identity, which avoids an extra USB re-enumeration.
        camera_index = self._coerce_int(self.camera_index, 0)
        self.info(f"Deferring Andor camera initialization for {self.device_name}", True)
        self._device_id_internal = camera_index
        self._uri = f"andor-sdk2://index/{camera_index}".encode("utf-8")
        return self._device_id_internal, self._uri

    def get_camera_friendly_name(self):
        return self.friendly_name

    def set_camera_friendly_name(self, value):
        self.friendly_name = str(value)

    def get_camera_serial_number(self) -> api.Union[str, int]:
        return self.serial_number_real

    def get_camera_model_name(self) -> str:
        return self.head_name

    def get_exposure_time(self) -> float:
        if self.camera:
            try:
                self.exposure_time_local = float(self.camera.get_exposure())
            except Exception:
                pass
        return self.exposure_time_local

    def get_trigger_delay(self) -> str:
        return float(self.trigger_source_value)

    def get_exposure_min(self):
        return 0.0

    def get_exposure_max(self):
        return 3600.0

    def get_gain(self) -> int:
        return int(self.gain_value)

    def get_gain_min(self) -> int:
        return 0

    def get_gain_max(self) -> int:
        return int(max(self.n_gains_max, self.gain_value, 0))

    def get_width(self) -> int:
        return int(self.current_width)

    def get_width_min(self):
        return 1

    def get_width_max(self):
        return int(self.current_width)

    def get_height(self) -> int:
        return int(self.current_height)

    def get_height_min(self):
        return 1

    def get_height_max(self):
        return int(max(self.current_height, self.height_value))

    def get_offsetX(self) -> int:
        return int(self.offsetX_value)

    def get_offsetY(self) -> int:
        return int(self.offsetY_value)

    def set_format_pixel(self, value: str):
        return None

    def get_format_pixel(self) -> str:
        return "float32"

    def get_framerate(self):
        if not self.camera:
            return 0.0
        try:
            timings = self.camera.get_frame_timings()
            frame_period = float(getattr(timings, "frame_period", timings[1]))
            return 0.0 if frame_period <= 0 else 1.0 / frame_period
        except Exception:
            return 0.0

    def get_binning_horizontal(self) -> int:
        return int(self.binning_horizontal_value)

    def get_binning_vertical(self) -> int:
        return int(self.binning_vertical_value)

    def get_sensor_readout_mode(self) -> str:
        return str(self.current_read_mode)

    def turn_on_local(self) -> api.Union[int, str]:
        if self.camera is not None:
            self.set_state(api.DevState.ON)
            return 0

        try:
            self.camera = self._create_camera()
            self.camera.setup_shutter("open")
            self._sync_from_camera(self.camera)
            self._apply_parameters(self.parameters.get("Acquisition_Controls", {}))
            self._refresh_wavelengths_axis(expected_width=self.current_width)
            self.set_state(api.DevState.ON)
            return 0
        except Exception as exc:
            self.camera = None
            self.set_state(api.DevState.FAULT)
            return f"Could not turn on camera via pylablib: {exc}"

    def turn_off_local(self) -> api.Union[int, str]:
        book = getattr(self, "_v0_orders", None)
        if book is not None:
            book.unavailable("Camera turned off")
        if self.grabbing:
            self.stop_grabbing_local()

        if self.camera is not None:
            try:
                self.camera.close()
            except Exception as exc:
                self.warn(f"Camera close reported: {exc}", True)
            finally:
                self.camera = None

        self.set_state(api.DevState.OFF)
        return 0

    def release_power_dependency_local(self) -> None:
        """Release a stale SDK handle without issuing camera configuration commands."""
        book = getattr(self, "_v0_orders", None)
        if book is not None:
            book.unavailable("Camera power dependency released")
        if self.grabbing:
            self.abort = True
        camera = self.camera
        self.camera = None
        if camera is not None:
            try:
                camera.close()
            except Exception:
                pass

    def probe_powered_hardware(self) -> api.Union[int, str]:
        """Verify an externally powered camera without opening its shutter or grabbing."""
        if self.camera is not None:
            return 0
        camera = None
        try:
            camera = self._create_camera()
            camera.get_device_info()
            camera_index = self._coerce_int(self.camera_index, 0)
            self._device_id_internal = camera_index
            self._uri = f"andor-sdk2://index/{camera_index}".encode("utf-8")
            return 0
        except Exception as exc:
            self._device_id_internal = -1
            self._uri = b""
            return f"Andor camera probe failed: {exc}"
        finally:
            if camera is not None:
                try:
                    camera.close()
                except Exception:
                    pass

    def set_param_after_init_local(self) -> api.Union[int, str]:
        if not self.camera:
            return "Camera is not opened"
        return self._apply_parameters(self.parameters.get("Acquisition_Controls", {}))

    def get_image(self):
        if self.last_image is not None:
            return
        book = getattr(self, "_v0_orders", None)
        if book is not None and book.has_active():
            # A snap can restart/reconfigure acquisition and cannot share an
            # indexed order. The worker owns all reads until that order ends.
            return
        if not self.camera:
            return

        try:
            frame = self.camera.snap()
            self.last_image = self._normalize_frame(frame)
        except Exception as exc:
            self.warn(f"Single-frame snap failed: {exc}")

    return {
        "_coerce_int": _coerce_int,
        "_coerce_float": _coerce_float,
        "_coerce_str": _coerce_str,
        "_parse_array_property": _parse_array_property,
        "_parse_wavelengths": _parse_wavelengths,
        "_create_camera": _create_camera,
        "_with_temp_camera": _with_temp_camera,
        "_sync_from_camera": _sync_from_camera,
        "_update_image_geometry_from_mode": _update_image_geometry_from_mode,
        "_update_temperature_status": _update_temperature_status,
        "_update_amp_mode_state": _update_amp_mode_state,
        "_refresh_wavelengths_axis": _refresh_wavelengths_axis,
        "_normalize_frame": _normalize_frame,
        "_consume_frame_for_orders": _consume_frame_for_orders,
        "find_device": find_device,
        "get_camera_friendly_name": get_camera_friendly_name,
        "set_camera_friendly_name": set_camera_friendly_name,
        "get_camera_serial_number": get_camera_serial_number,
        "get_camera_model_name": get_camera_model_name,
        "get_exposure_time": get_exposure_time,
        "get_trigger_delay": get_trigger_delay,
        "get_exposure_min": get_exposure_min,
        "get_exposure_max": get_exposure_max,
        "get_gain": get_gain,
        "get_gain_min": get_gain_min,
        "get_gain_max": get_gain_max,
        "get_width": get_width,
        "get_width_min": get_width_min,
        "get_width_max": get_width_max,
        "get_height": get_height,
        "get_height_min": get_height_min,
        "get_height_max": get_height_max,
        "get_offsetX": get_offsetX,
        "get_offsetY": get_offsetY,
        "set_format_pixel": set_format_pixel,
        "get_format_pixel": get_format_pixel,
        "get_framerate": get_framerate,
        "get_binning_horizontal": get_binning_horizontal,
        "get_binning_vertical": get_binning_vertical,
        "get_sensor_readout_mode": get_sensor_readout_mode,
        "turn_on_local": turn_on_local,
        "turn_off_local": turn_off_local,
        "release_power_dependency_local": release_power_dependency_local,
        "probe_powered_hardware": probe_powered_hardware,
        "set_param_after_init_local": set_param_after_init_local,
        "get_image": get_image,
    }
