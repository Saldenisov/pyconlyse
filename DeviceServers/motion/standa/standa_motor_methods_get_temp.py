"""Implementation for get_temp and related operations."""


def _bind_standa_motor_methods_get_temp(api):
    """Bind implementation to the owning module and its runtime state."""

    def get_temp(self):
        return self._temperature

    def get_current(self):
        return self._power_current

    def get_voltage(self):
        return self._power_voltage

    def _initialize_on_startup_if_requested(self) -> bool:
        """Leave a discovered controller open and ready for immediate use."""

        try:
            enabled = bool(int(self.initialize_on_startup or 0))
        except (TypeError, ValueError):
            enabled = True

        if not enabled:
            if self._device_id_internal != -1:
                self.set_state(api.DevState.STANDBY)
                self.info(
                    f"{self.device_name} controller discovered; startup initialisation is disabled.",
                    True,
                )
            return False

        if self._device_id_internal == -1:
            message = (
                f"{self.device_name} startup initialisation failed: "
                "controller was not discovered"
            )
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.DISCONNECTED,
                api.InitializationState.FAILED,
                message,
            )
            self.set_state(api.DevState.FAULT)
            self.error(message)
            return False

        # A configured power dependency schedules its own delayed probe during
        # base initialisation.  This Standa-specific startup path performs the
        # stronger open/serial/status/position verification itself, so leaving
        # that probe pending would make it run against an already-open ON axis.
        # In that state find_device() is intentionally disallowed and the base
        # probe would incorrectly report the powered controller as missing.
        probe_was_pending = bool(getattr(self, "_power_probe_pending", False))
        if probe_was_pending:
            self._power_probe_pending = False
            self._power_probe_due_at = 0.0

        self.info(
            f"Initialising {self.device_name} automatically at device-server startup.",
            True,
        )
        result = self.turn_on_local()
        if result in (None, 0) and self.get_state() == api.DevState.ON:
            power_state = getattr(self, "_power_dependency_state", None)
            if getattr(power_state, "configured", False) and getattr(
                power_state, "powered", None
            ) is True:
                self._last_power_probe_error = ""
                self._power_dependency_status = (
                    f"{power_state.detail}; startup initialisation verified "
                    "the hardware; axis is ready"
                )
            self.info(
                f"{self.device_name} startup initialisation succeeded; axis is ready.",
                True,
            )
            return True

        self.set_state(api.DevState.FAULT)
        if probe_was_pending:
            self._schedule_power_probe(
                float(self.power_dependency_reconnect_seconds or 5.0)
            )
        message = f"{self.device_name} startup initialisation failed: {result}"
        self.error(message)
        return False

    def _transport_lock(self, timeout_s=None):
        timeout = (
            self.usb_transport_lock_timeout_s
            if timeout_s is None
            else timeout_s
        )
        if self.usb_transport_lock_path:
            return api.exclusive_standa_transport(
                self.usb_transport_lock_path,
                timeout_seconds=max(0.1, float(timeout or 1.0)),
            )
        return api.exclusive_standa_device_transport(
            str(self.device_id),
            timeout_seconds=max(0.1, float(timeout or 1.0)),
        )

    def _discovery_transport_lock(self, timeout_s=None):
        """Serialize enumeration because probing touches the complete COM bus."""

        timeout = (
            self.usb_transport_lock_timeout_s
            if timeout_s is None
            else timeout_s
        )
        return api.exclusive_standa_transport(
            self.usb_transport_lock_path or None,
            timeout_seconds=max(0.1, float(timeout or 1.0)),
        )

    def _utc_now_iso():
        return api.datetime.now(api.timezone.utc).isoformat()

    def _record_transport_error(self, operation, result):
        self._transport_error_count = int(
            getattr(self, "_transport_error_count", 0)
        ) + 1
        self._last_transport_error = f"{operation}: {result}"
        self._last_transport_error_at_utc = self._utc_now_iso()

    def _read_transport_call(self, operation, function, *args):
        """Retry only idempotent reads after resetting transmission locks."""

        retries = max(0, int(getattr(self, "usb_read_retry_count", 1) or 0))
        with self._transport_lock():
            result = function(*args)
            if result == api.Result.Ok:
                return result
            self._record_transport_error(operation, result)
            if result != api.Result.Error:
                return result
            reset_locks = getattr(api.lib, "reset_locks", None)
            if not callable(reset_locks):
                return result
            for _attempt in range(retries):
                reset_locks()
                api.time.sleep(
                    max(0.0, float(getattr(self, "usb_read_retry_delay_s", 0.05)))
                )
                result = function(*args)
                if result == api.Result.Ok:
                    self._transport_retry_success_count = int(
                        getattr(self, "_transport_retry_success_count", 0)
                    ) + 1
                    return result
                self._record_transport_error(operation, result)
                if result != api.Result.Error:
                    return result
            return result

    def _endpoint_state_from_gpio_flags(gpio_flags) -> str:
        """Decode the two physical end switches without using motor position."""

        flags = int(gpio_flags or 0)
        right_active = bool(flags & api.GPIOFlags.STATE_RIGHT_EDGE)
        left_active = bool(flags & api.GPIOFlags.STATE_LEFT_EDGE)
        if right_active and left_active:
            return "CONFLICT"
        if right_active:
            return "RIGHT"
        if left_active:
            return "LEFT"
        return "BETWEEN"

    def _update_endpoint_state(self, controller_status) -> str:
        self._endpoint_state = self._endpoint_state_from_gpio_flags(
            getattr(controller_status, "GPIOFlags", 0)
        )
        return self._endpoint_state

    def _refresh_endpoint_state_passively(self) -> str:
        """Read end switches through a temporary handle, without any motion."""

        uri = getattr(self, "_uri", b"") or getattr(self, "_last_known_uri", b"")
        if not uri:
            self._endpoint_state = "UNKNOWN"
            return self._endpoint_state

        handle = -1
        try:
            with self._transport_lock():
                handle = api.lib.open_device(uri)
                if handle < 0:
                    self._endpoint_state = "UNKNOWN"
                    return self._endpoint_state
                try:
                    serial = api.ctypes.c_uint()
                    serial_result = api.lib.get_serial_number(
                        handle, api.ctypes.byref(serial)
                    )
                    if (
                        serial_result != api.Result.Ok
                        or int(serial.value) != int(self.device_id)
                    ):
                        self._endpoint_state = "UNKNOWN"
                        return self._endpoint_state

                    controller_status = api.status_t()
                    status_result = api.lib.get_status(
                        handle, api.ctypes.byref(controller_status)
                    )
                    if status_result != api.Result.Ok:
                        self._endpoint_state = "UNKNOWN"
                        return self._endpoint_state
                    return self._update_endpoint_state(controller_status)
                finally:
                    self._close_handle_locked(handle)
                    handle = -1
        except Exception:
            self._endpoint_state = "UNKNOWN"
            return self._endpoint_state

    def _has_open_transport(self) -> bool:
        return bool(
            getattr(
                self,
                "_standa_handle_open",
                getattr(self, "_device_id_internal", -1) not in (-1, None),
            )
        )

    def _close_handle_locked(device_handle) -> int:
        if device_handle in (-1, None):
            return 0
        handle = api.ctypes.cast(device_handle, api.ctypes.POINTER(api.ctypes.c_int))
        return api.lib.close_device(api.ctypes.byref(handle))

    def _invalidate_transport(self) -> None:
        self._commanded_flipper_state = "UNKNOWN"
        device_handle = getattr(self, "_device_id_internal", -1)
        was_open = self._has_open_transport()
        current_uri = getattr(self, "_uri", b"")
        if current_uri:
            self._last_known_uri = current_uri
        self._device_id_internal = -1
        self._uri = b""
        self._standa_handle_open = False
        if not was_open:
            return
        try:
            with self._transport_lock(timeout_s=0.2):
                self._close_handle_locked(device_handle)
        except Exception:
            # A disconnected USB device commonly cannot be closed.  The local
            # handle is already invalidated, so no further command will use it.
            pass

    def _schedule_transport_recovery(self) -> None:
        delay = max(0.1, float(getattr(self, "_standa_recovery_delay_s", 3.0)))
        max_delay = max(delay, float(self.usb_recovery_max_delay_s or 60.0))
        self._next_fault_recovery_at = api.time.monotonic() + delay
        self._standa_recovery_delay_s = min(max_delay, delay * 2.0)

    def _reset_transport_recovery(self) -> None:
        self._status_check_fault = 0
        self._standa_auto_recovery_blocked = False
        self._standa_recovery_delay_s = max(
            0.1, float(self.usb_recovery_initial_delay_s or 3.0)
        )

    def _enumerated_serial(devenum, index):
        get_serial = getattr(api.lib, "get_enumerate_device_serial", None)
        if not callable(get_serial):
            return None
        serial = api.ctypes.c_uint()
        result = get_serial(devenum, index, api.ctypes.byref(serial))
        if result == api.Result.Ok:
            return int(serial.value)
        return None

    def _serial_by_temporary_open(self, uri):
        """Compatibility fallback for legacy enumeration without serial data."""

        device_handle = api.lib.open_device(uri)
        if device_handle < 0:
            return None
        try:
            serial = api.ctypes.c_uint()
            result = api.lib.get_serial_number(device_handle, api.ctypes.byref(serial))
            if result == api.Result.Ok:
                return int(serial.value)
            return None
        finally:
            self._close_handle_locked(device_handle)

    def _set_passive_discovery_result(self, discovered_uri):
        """Store a closed discovery marker without initialising the axis."""

        discovered_uri = discovered_uri or b""
        self._standa_handle_open = False
        self._uri = discovered_uri
        self._device_id_internal = 0 if discovered_uri else -1
        if discovered_uri:
            self._last_known_uri = discovered_uri

    def find_device(self):
        api._startup_trace("find_device_enter")
        state_ok = self.check_func_allowance(self.find_device)
        discovered_uri = b""
        if not state_ok:
            return

        self.info(f"Searching for STANDA device {self.device_id}", True)
        cache_ttl = max(0.0, float(self.usb_discovery_cache_ttl_s or 0.0))
        cached_devices = api.load_discovery_snapshot(cache_ttl)
        if cached_devices is not None:
            cached_uri = cached_devices.get(str(self.device_id))
            discovered_uri = cached_uri.encode("utf-8") if cached_uri else b""
            self._set_passive_discovery_result(discovered_uri)
            if discovered_uri:
                self._last_known_uri = discovered_uri
                self.info(
                    f"Reused recent host discovery for {self.device_name}: "
                    f"{discovered_uri!r}",
                    True,
                )
            return

        discovered_devices = {}
        devenum = None
        try:
            # Enumeration itself opens every connected controller.  A single
            # host-wide lock prevents simultaneous recoveries from disrupting
            # one another when USB is noisy during accelerator operation.
            api._startup_trace("transport_lock_wait")
            # A complete probe can take longer than an ordinary controller
            # command. Once inside the host-wide lock, recheck the cache: a
            # preceding Tango process may already have completed the scan.
            with self._discovery_transport_lock(
                timeout_s=max(
                    0.1, float(self.usb_discovery_lock_timeout_s or 15.0)
                )
            ):
                api._startup_trace("transport_lock_acquired")
                cached_devices = api.load_discovery_snapshot(cache_ttl)
                if cached_devices is not None:
                    cached_uri = cached_devices.get(str(self.device_id))
                    discovered_uri = (
                        cached_uri.encode("utf-8") if cached_uri else b""
                    )
                    if discovered_uri:
                        self.info(
                            f"Reused host discovery completed by another process "
                            f"for {self.device_name}: {discovered_uri!r}",
                            True,
                        )
                    self._set_passive_discovery_result(discovered_uri)
                    return
                set_bindy_key = getattr(api.lib, "set_bindy_key", None)
                keyfile = api.Path(api.ximc_dir / api.arch_type / "keyfile.sqlite")
                if callable(set_bindy_key) and keyfile.exists():
                    set_bindy_key(str(keyfile).encode("utf-8"))
                probe_flags = api.EnumerateFlags.ENUMERATE_PROBE
                enum_hints = b""
                if bool(int(self.enumerate_network_devices or 0)):
                    probe_flags |= api.EnumerateFlags.ENUMERATE_NETWORK
                    enum_hints = f"addr={self.ip_address}".encode()
                api._startup_trace("enumerate_devices_enter")
                devenum = api.lib.enumerate_devices(probe_flags, enum_hints)
                api._startup_trace("enumerate_devices_exit")
                device_counts = api.lib.get_device_count(devenum)
                for index in range(max(0, device_counts)):
                    uri = api.lib.get_device_name(devenum, index)
                    serial = self._enumerated_serial(devenum, index)
                    if serial is None:
                        serial = self._serial_by_temporary_open(uri)
                    if serial is not None:
                        discovered_devices[int(serial)] = uri
                    if int(self.device_id) == serial:
                        discovered_uri = uri
                api.store_discovery_map(discovered_devices)
        except api.StandaTransportBusyError as error:
            self.warn(f"STANDA discovery deferred: {error}", True)
        except Exception as error:
            self.warn(f"STANDA discovery failed: {error}", True)
        finally:
            if devenum is not None:
                free_enumeration = getattr(api.lib, "free_enumerate_devices", None)
                if callable(free_enumeration):
                    try:
                        free_enumeration(devenum)
                    except Exception as error:
                        self.warn(f"STANDA enumeration cleanup failed: {error}")

        # A closed probe handle remains only as a discovery marker. Commands
        # use it only after turn_on_local reopens and verifies the selected URI.
        self._set_passive_discovery_result(discovered_uri)
        if discovered_uri:
            self.set_state(api.DevState.STANDBY)
        api._startup_trace("find_device_exit")

    def read_position_local(self) -> api.Union[int, str]:
        if not self._has_open_transport():
            return (
                f"Could not read position of {self.device_name}: "
                "STANDA transport is not open."
            )
        pos = api.get_position_t()
        try:
            result = self._read_transport_call(
                "get_position",
                api.lib.get_position,
                self._device_id_internal,
                api.ctypes.byref(pos),
            )
        except api.StandaTransportBusyError:
            return (
                f"Could not read position of {self.device_name}: "
                "STANDA USB transport is busy."
            )
        except Exception as error:
            return f"Could not read position of {self.device_name}: {error}."
        if result == api.Result.Ok:
            pos_microsteps = pos.Position * 256 + pos.uPosition
            pos_basic_units = pos_microsteps / 256
            self._position = round(pos_basic_units / self.conversion, 3)
            return 0
        return f"Could not read position of {self.device_name}: {result}."

    def write_position_local(self, pos) -> api.Union[int, str]:
        self.move_axis(pos)
        return 0

    def _standa_error(self, error: int) -> api.Tuple[bool, str]:
        # TODO: finish filling different errors values
        if error == 0:
            res, comments = True, ""
        elif error == -1:
            res, comments = False, "Standa: generic error."
        else:
            res, comments = False, "Standa: unknown error."

        return res, comments

    def define_position_local(self, position) -> api.Union[str, int]:
        if not self._has_open_transport():
            return (
                f"Could not define position of {self.device_name}: "
                "STANDA transport is not open."
            )
        position = position * self.conversion
        pos_steps = int(position // 1)
        pos_microsteps = int(position % 1 * 256)
        pos_standa = api.set_position_t()
        pos_standa.Position = api.ctypes.c_int(pos_steps)
        pos_standa.uPosition = api.ctypes.c_int(pos_microsteps)
        pos_standa.EncPosition = api.ctypes.c_longlong(0)
        pos_standa.PosFlags = api.ctypes.c_uint(api.PositionFlags.SETPOS_IGNORE_ENCODER)
        try:
            with self._transport_lock():
                result = api.lib.set_position(
                    self._device_id_internal, api.ctypes.byref(pos_standa)
                )
        except api.StandaTransportBusyError as error:
            return f"Could not define position of {self.device_name}: {error}."
        except Exception as error:
            return f"Could not define position of {self.device_name}: {error}."
        if result == api.Result.Ok:
            return 0
        return f"Could not define position of {self.device_name}: {result}."

    def _open_verified_transport(self, uri):
        """Open one URI and verify that it is the configured controller."""

        if not uri:
            return -1, "empty URI"
        try:
            with self._transport_lock():
                handle = api.lib.open_device(uri)
                if handle < 0:
                    return handle, f"open_device returned {handle}"
                serial = api.ctypes.c_uint()
                result = api.lib.get_serial_number(handle, api.ctypes.byref(serial))
                if result != api.Result.Ok or int(serial.value) != int(self.device_id):
                    self._close_handle_locked(handle)
                    return -1, (
                        f"serial verification failed: result={result}, "
                        f"serial={serial.value}"
                    )
                return handle, ""
        except api.StandaTransportBusyError as error:
            return -1, str(error)
        except Exception as error:
            return -1, str(error)

    def _resume_open_transport(self, uri) -> bool:
        """Reopen and verify a previously initialized axis without moving it."""

        handle, error = self._open_verified_transport(uri)
        if handle < 0:
            if error:
                self._record_transport_error("reopen", error)
            return False
        self._device_id_internal = handle
        self._uri = uri
        self._last_known_uri = uri
        self._standa_handle_open = True

        status = api.status_t()
        try:
            result = self._read_transport_call(
                "reopen_get_status",
                api.lib.get_status,
                handle,
                api.ctypes.byref(status),
            )
            if result != api.Result.Ok or self.read_position_local() != 0:
                self._invalidate_transport()
                return False
        except Exception as error:
            self._record_transport_error("reopen_validation", error)
            self._invalidate_transport()
            return False

        self._reset_transport_recovery()
        self.set_state(api.DevState.ON)
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.READY,
            api.InitializationState.SUCCEEDED,
            "STANDA transport automatically reopened and verified; no movement or stop command was issued",
        )
        self.info(
            f"STANDA transport safely resumed for {self.device_name} without movement.",
            True,
        )
        return True

    return {
        "get_temp": get_temp,
        "get_current": get_current,
        "get_voltage": get_voltage,
        "_initialize_on_startup_if_requested": _initialize_on_startup_if_requested,
        "_transport_lock": _transport_lock,
        "_discovery_transport_lock": _discovery_transport_lock,
        "_utc_now_iso": _utc_now_iso,
        "_record_transport_error": _record_transport_error,
        "_read_transport_call": _read_transport_call,
        "_endpoint_state_from_gpio_flags": _endpoint_state_from_gpio_flags,
        "_update_endpoint_state": _update_endpoint_state,
        "_refresh_endpoint_state_passively": _refresh_endpoint_state_passively,
        "_has_open_transport": _has_open_transport,
        "_close_handle_locked": _close_handle_locked,
        "_invalidate_transport": _invalidate_transport,
        "_schedule_transport_recovery": _schedule_transport_recovery,
        "_reset_transport_recovery": _reset_transport_recovery,
        "_enumerated_serial": _enumerated_serial,
        "_serial_by_temporary_open": _serial_by_temporary_open,
        "_set_passive_discovery_result": _set_passive_discovery_result,
        "find_device": find_device,
        "read_position_local": read_position_local,
        "write_position_local": write_position_local,
        "_standa_error": _standa_error,
        "define_position_local": define_position_local,
        "_open_verified_transport": _open_verified_transport,
        "_resume_open_transport": _resume_open_transport,
    }
