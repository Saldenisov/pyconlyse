"""Implementation for write_always_on_value and related operations."""


def _bind_general_methods_write_always_on_value(api):
    """Bind implementation to the owning module and its runtime state."""

    def write_always_on_value(self, value: int):
        self.always_on = value

    def write_device_friendly_name(self, friendly_name):
        self.friendly_name = friendly_name

    def set_state(self, state):
        """Track real Tango state transitions without creating polling records."""

        previous = getattr(self, "_tracked_tango_state", None)
        api.Device.set_state(self, state)
        if previous != state:
            self._tracked_tango_state = state
            self._last_state_change_at_utc = api._utc_now_iso()
            self._push_tracking_event("State", state)
            self._push_tracking_event(
                "last_state_change_at_utc", self._last_state_change_at_utc
            )

    def set_status(self, status):
        """Push status only when it actually changes."""

        text = str(status)
        previous = getattr(self, "_tracked_tango_status", None)
        api.Device.set_status(self, text)
        if previous != text:
            self._tracked_tango_status = text
            self._push_tracking_event("Status", text)

    def _configure_tracking_events(self):
        """Enable device-pushed, change-only lifecycle archive events."""

        self._tracking_events_ready = False
        for name in self._TRACKING_EVENT_ATTRIBUTES:
            try:
                self.set_change_event(name, True, False)
                self.set_archive_event(name, True, False)
            except Exception as exc:
                self.warn_stream(f"Cannot configure tracking event {name}: {exc}")
        self._tracking_events_ready = True

    def _push_tracking_event(self, name, value):
        if not getattr(self, "_tracking_events_ready", False):
            return
        try:
            self.push_change_event(name, value)
        except Exception as exc:
            self.warn_stream(f"Cannot push change event {name}: {exc}")
        try:
            self.push_archive_event(name, value)
        except Exception as exc:
            self.warn_stream(f"Cannot push archive event {name}: {exc}")

    def set_hardware_lifecycle(
        self,
        connection_state=api.HardwareConnectionState.UNKNOWN,
        initialization_state=api.InitializationState.UNKNOWN,
        detail="",
    ):
        """Record hardware facts without changing Tango ``DevState``.

        A device server must not use these attributes to imply that the Tango
        process itself is unavailable.  That is determined externally by a
        DeviceProxy/Astor reachability check.
        """
        previous_connection_state = getattr(self, "_hardware_connection_state", None)
        previous_initialization_state = getattr(self, "_initialization_state", None)
        previous_detail = getattr(self, "_hardware_lifecycle_status", None)
        self._hardware_connection_state = api.lifecycle_value(
            connection_state,
            api.HardwareConnectionState,
            api.HardwareConnectionState.UNKNOWN,
        )
        self._initialization_state = api.lifecycle_value(
            initialization_state,
            api.InitializationState,
            api.InitializationState.UNKNOWN,
        )
        self._hardware_lifecycle_status = str(detail or "")
        if (
            self._initialization_state != api.InitializationState.UNKNOWN.value
            and self._initialization_state != previous_initialization_state
        ):
            self._initialization_completed_at_utc = api._utc_now_iso()
            started = getattr(self, "_initialization_started_monotonic", None)
            if isinstance(started, (int, float)):
                self._initialization_duration_ms = max(
                    0.0, (api.time.monotonic() - started) * 1000.0
                )
            self._push_tracking_event(
                "initialization_completed_at_utc",
                getattr(self, "_initialization_completed_at_utc", ""),
            )
            self._push_tracking_event(
                "initialization_duration_ms",
                float(getattr(self, "_initialization_duration_ms", 0.0)),
            )
        if previous_connection_state != self._hardware_connection_state:
            self._push_tracking_event(
                "hardware_connection_state", self._hardware_connection_state
            )
        if previous_initialization_state != self._initialization_state:
            self._push_tracking_event("initialization_state", self._initialization_state)
        if previous_detail != self._hardware_lifecycle_status:
            self._push_tracking_event(
                "hardware_lifecycle_status", self._hardware_lifecycle_status
            )

    def error(self, error_in):
        self.error_stream(error_in)
        self._error = str(error_in)
        self._last_error_at_utc = api._utc_now_iso()
        self._error_count = int(getattr(self, "_error_count", 0)) + 1
        self._push_tracking_event("last_error", self._error)
        self._push_tracking_event("last_error_at_utc", self._last_error_at_utc)
        self._push_tracking_event("error_count", self._error_count)
        self._n = 0
        print(error_in)

    def warn(self, warn_in, printing=False):
        # Log a warning and optionally print
        try:
            self.warn_stream(warn_in)
        except Exception:
            # Fallback if warn_stream is unavailable
            self.info_stream(f"WARNING: {warn_in}")
        self._comment = warn_in
        if printing:
            print(warn_in)

    def info(self, info_in, printing=False):
        self.info_stream(info_in)
        self._comment = info_in
        if printing:
            print(info_in)

    def _start_error_timer(self):
        """Start one bounded maintenance timer per device instance."""
        self._stop_error_timer()
        self._error_timer_stop = api.Event()
        self._error_timer_thread = api.Thread(
            target=self.int_time,
            args=(self._error_timer_stop,),
            name=f"{self.__class__.__name__}-error-timer",
            daemon=True,
        )
        self._error_timer_thread.start()

    def _power_dependency_is_configured(self) -> bool:
        try:
            return bool(str(self.power_dependency_device or "").strip()) and int(
                self.power_dependency_output_id or 0
            ) > 0
        except (TypeError, ValueError):
            return False

    def _power_dependency_auto_turn_on_enabled(self) -> bool:
        """Return whether this explicitly opted-in device may re-enable itself."""
        try:
            return bool(int(self.power_dependency_auto_turn_on or 0))
        except (TypeError, ValueError):
            return False

    def _read_power_dependency_state(self) -> api.PowerDependencyState:
        return api.read_power_dependency_state(
            self.power_dependency_device,
            self.power_dependency_output_id,
            self._power_dependency_proxy,
        )

    def _power_dependency_proxy(device_name: str):
        from tango import DeviceProxy

        return DeviceProxy(device_name)

    def _observe_power_dependency(
        self, *, force: bool = False, initial: bool = False
    ) -> api.PowerDependencyState:
        if not self._power_dependency_is_configured():
            state = api.PowerDependencyState(
                False, None, "power dependency is not configured"
            )
            self._power_dependency_state = state
            self._power_dependency_status = state.detail
            return state

        state = self._read_power_dependency_state()
        self._apply_power_dependency_state(state, initial=initial)
        return state

    def _apply_power_dependency_state(
        self, state: api.PowerDependencyState, *, initial: bool = False
    ) -> None:
        previous = getattr(self, "_power_dependency_state", None)
        observed = bool(getattr(self, "_power_dependency_observed", False))
        changed = (
            not observed
            or previous is None
            or previous.powered != state.powered
            or previous.detail != state.detail
        )
        self._power_dependency_observed = True
        self._power_dependency_state = state
        if changed:
            self._power_dependency_status = state.detail

        if state.powered is False:
            self._power_probe_pending = False
            self._power_probe_due_at = 0.0
            if changed:
                self._handle_power_dependency_off(state.detail)
            return

        if state.powered is None:
            self._power_probe_pending = False
            self._power_probe_due_at = 0.0
            if changed:
                self._handle_power_dependency_unavailable(state.detail)
            return

        if initial:
            return

        if previous is not None and previous.powered is not True:
            settle_seconds = max(0.0, float(self.power_on_settle_seconds or 0.0))
            self._schedule_power_probe(settle_seconds)
            self._power_dependency_status = (
                f"{state.detail}; waiting {settle_seconds:.1f}s before safe probe"
            )
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.CONNECTING,
                api.InitializationState.PENDING,
                self._power_dependency_status,
            )
            self.set_state(api.DevState.INIT)
            self.info(self._power_dependency_status, True)

    def _schedule_power_probe(self, delay_seconds: float) -> None:
        """Schedule a passive hardware probe; never issue a PDU command."""
        self._power_probe_pending = bool(int(self.power_dependency_auto_probe or 0))
        self._power_probe_due_at = api.time.monotonic() + max(0.0, float(delay_seconds))

    def _mark_hardware_power_off(
        self, message: str, *, tango_state=api.DevState.OFF
    ) -> str:
        """Record a confirmed external power loss without fault recovery."""
        self._device_id_internal, self._uri = -1, b""
        self._status_check_fault = 0
        self._fault_recovery_attempts = 0
        self._next_fault_recovery_at = 0.0
        self._last_fault_recovery_error = ""
        self._last_power_probe_error = ""
        self._error = ""
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.POWER_OFF,
            api.InitializationState.NOT_REQUESTED,
            message,
        )
        self.set_state(tango_state)
        self.comment = message
        if getattr(self, "_last_power_off_message", "") != message:
            self.info(message, True)
            self._last_power_off_message = message
        return message

    def _handle_power_dependency_off(self, detail: str) -> None:
        self._release_power_dependency_transport()
        message = f"Hardware power is OFF ({detail}); connection is intentionally skipped."
        self._power_dependency_status = message
        self._mark_hardware_power_off(message)

    def _handle_power_dependency_unavailable(self, detail: str) -> None:
        self._release_power_dependency_transport()
        self._device_id_internal, self._uri = -1, b""
        message = f"Power dependency is unavailable: {detail}"
        self._power_dependency_status = message
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.POWER_STATUS_UNAVAILABLE,
            api.InitializationState.UNKNOWN,
            message,
        )
        self.set_state(api.DevState.FAULT)
        self.error(message)

    def release_power_dependency_local(self) -> None:
        """Release local transport resources after external power loss only."""

    def power_dependency_ready_state(self):
        """State after a passive post-power probe; hardware defaults to STANDBY."""
        return api.DevState.STANDBY

    def _release_power_dependency_transport(self) -> None:
        try:
            self.release_power_dependency_local()
        except Exception as error:
            self.warn(f"Power-loss transport cleanup failed: {error}", True)

    def probe_powered_hardware(self) -> api.Union[int, str]:
        """Probe a restored supply without calling turn_on or moving hardware."""
        self._device_id_internal, self._uri = -1, b""
        self.find_device()
        if self._device_id_internal == -1:
            return "hardware did not respond after power was restored"
        return 0

    def _power_dependency_monitor_loop(self, stop_event: api.Event) -> None:
        while not stop_event.wait(
            max(0.2, float(self.power_dependency_poll_interval_s or 1.0))
        ):
            try:
                self._observe_power_dependency()
                self._run_power_dependency_probe_if_due()
            except Exception as error:
                self.warn(f"Power dependency monitor failed: {error}", True)

    def _run_power_dependency_probe_if_due(self) -> None:
        if not bool(getattr(self, "_power_probe_pending", False)):
            return
        if api.time.monotonic() < float(getattr(self, "_power_probe_due_at", 0.0)):
            return
        self._power_probe_pending = False
        with self._get_lifecycle_lock():
            state = self._observe_power_dependency(force=True)
            if state.powered is not True:
                return
            result = self.probe_powered_hardware()
            if api.operation_succeeded(result):
                self.set_state(self.power_dependency_ready_state())
                self._last_power_probe_error = ""
                self._error = ""
                self.set_hardware_lifecycle(
                    api.HardwareConnectionState.CONNECTED,
                    api.InitializationState.NOT_REQUESTED,
                    f"{state.detail}; safe transport probe succeeded; operational initialisation has not been requested",
                )
                if self._power_dependency_auto_turn_on_enabled():
                    self._power_dependency_status = (
                        f"{state.detail}; safe probe succeeded; running automatic turn_on"
                    )
                    self.info(self._power_dependency_status, True)
                    self.turn_on()
                    if self.get_state() == api.DevState.ON:
                        self.set_hardware_lifecycle(
                            api.HardwareConnectionState.READY,
                            api.InitializationState.SUCCEEDED,
                            f"{state.detail}; safe probe and automatic operational initialisation succeeded",
                        )
                        self._power_dependency_status = (
                            f"{state.detail}; safe probe succeeded; device was turned ON automatically"
                        )
                        self.info(self._power_dependency_status, True)
                    else:
                        self._power_dependency_status = (
                            f"{state.detail}; safe probe succeeded but automatic turn_on "
                            f"did not reach ON (state={self.get_state()})"
                        )
                        self.error(self._power_dependency_status)
                    return
                self._power_dependency_status = (
                    f"{state.detail}; safe probe succeeded; awaiting explicit turn_on"
                )
                self.info(self._power_dependency_status, True)
                return
            message = f"Hardware power is ON but safe probe failed: {result}"
            self._power_dependency_status = message
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.DISCONNECTED,
                api.InitializationState.NOT_REQUESTED,
                message,
            )
            self.set_state(api.DevState.FAULT)
            if message != getattr(self, "_last_power_probe_error", ""):
                self.error(message)
                self._last_power_probe_error = message
            self._schedule_power_probe(
                float(self.power_dependency_reconnect_seconds or 5.0)
            )

    def _start_power_dependency_monitor(self) -> None:
        if not self._power_dependency_is_configured():
            return
        self._stop_power_dependency_monitor()
        self._power_dependency_monitor_stop = api.Event()
        self._power_dependency_monitor_thread = api.Thread(
            target=self._power_dependency_monitor_loop,
            args=(self._power_dependency_monitor_stop,),
            name=f"{self.__class__.__name__}-power-monitor",
            daemon=True,
        )
        self._power_dependency_monitor_thread.start()

    def _stop_power_dependency_monitor(self) -> None:
        stop_event = getattr(self, "_power_dependency_monitor_stop", None)
        monitor_thread = getattr(self, "_power_dependency_monitor_thread", None)
        if stop_event is not None:
            stop_event.set()
        if (
            monitor_thread is not None
            and monitor_thread.is_alive()
            and monitor_thread is not api.current_thread()
        ):
            monitor_thread.join(timeout=1.0)
        self._power_dependency_monitor_stop = None
        self._power_dependency_monitor_thread = None

    def _stop_error_timer(self):
        stop_event = getattr(self, "_error_timer_stop", None)
        timer_thread = getattr(self, "_error_timer_thread", None)
        if stop_event is not None:
            stop_event.set()
        if (
            timer_thread is not None
            and timer_thread.is_alive()
            and timer_thread is not api.current_thread()
        ):
            timer_thread.join(timeout=1.0)
        self._error_timer_stop = None
        self._error_timer_thread = None

    def send_state_archive(self):
        res = {}
        for key, prev_value in self.previous_archive_state.items():
            current_value = self.archive_state[key][0]()
            dt = self.archive_state[key][1]
            res[key] = current_value
            if prev_value != current_value:
                data = self.form_archive_data(current_value, key, dt)
                self.write_to_archive(data)
        self.previous_archive_state = res

    def fix_state(self):
        res = {}
        for key, value in self.archive_state.items():
            res[key] = value[0]()
        self.previous_archive_state = res
        self.info("Fixing archiving state", True)

    def check_func_allowance(self, func) -> int:
        state_ok = -1
        if func.__name__ in self.RULES:
            rules_for_func = self.RULES[func.__name__]
            state = self.get_state()
            if state in rules_for_func:
                state_ok = 1
        else:
            self.error(f"Function {func} is not in RULES: {self.RULES}.")
        return state_ok

    def _get_lifecycle_lock(self):
        """Return a per-device reentrant lock for state-changing operations."""
        lock = getattr(self, "_lifecycle_lock", None)
        if lock is None:
            lock = api.RLock()
            self._lifecycle_lock = lock
        return lock

    def _fault_recovery_due(self, state) -> bool:
        if state != api.DevState.FAULT:
            return True
        if not bool(int(getattr(self, "fault_recovery_enabled", 1) or 0)):
            return False
        now = api.time.monotonic()
        if now < getattr(self, "_next_fault_recovery_at", 0.0):
            return False
        cooldown = max(0.1, float(getattr(self, "fault_recovery_cooldown_s", 3.0)))
        self._next_fault_recovery_at = now + cooldown
        self._fault_recovery_attempts = getattr(self, "_fault_recovery_attempts", 0) + 1
        return True

    def _record_controller_status(self, result) -> None:
        if api.operation_succeeded(result):
            # Older adapters sometimes reported success but left their previous
            # FAULT untouched. A successful health check is authoritative.
            if self.get_state() == api.DevState.FAULT:
                self.set_state(api.DevState.ON)
            self._fault_recovery_attempts = 0
            self._next_fault_recovery_at = 0.0
            self._last_fault_recovery_error = ""
            return
        self._last_fault_recovery_error = str(result)
        self.error(str(result))

    def _power_dependency_allows_hardware_operation(self, *, force: bool = False) -> bool:
        if not self._power_dependency_is_configured():
            return True
        state = self._observe_power_dependency(force=force)
        if state.powered is True and not bool(
            getattr(self, "_power_probe_pending", False)
        ):
            return True
        if state.powered is True:
            self.info(self._power_dependency_status, True)
            return False
        return False

    return {
        "write_always_on_value": write_always_on_value,
        "write_device_friendly_name": write_device_friendly_name,
        "set_state": set_state,
        "set_status": set_status,
        "_configure_tracking_events": _configure_tracking_events,
        "_push_tracking_event": _push_tracking_event,
        "set_hardware_lifecycle": set_hardware_lifecycle,
        "error": error,
        "warn": warn,
        "info": info,
        "_start_error_timer": _start_error_timer,
        "_power_dependency_is_configured": _power_dependency_is_configured,
        "_power_dependency_auto_turn_on_enabled": _power_dependency_auto_turn_on_enabled,
        "_read_power_dependency_state": _read_power_dependency_state,
        "_power_dependency_proxy": _power_dependency_proxy,
        "_observe_power_dependency": _observe_power_dependency,
        "_apply_power_dependency_state": _apply_power_dependency_state,
        "_schedule_power_probe": _schedule_power_probe,
        "_mark_hardware_power_off": _mark_hardware_power_off,
        "_handle_power_dependency_off": _handle_power_dependency_off,
        "_handle_power_dependency_unavailable": _handle_power_dependency_unavailable,
        "release_power_dependency_local": release_power_dependency_local,
        "power_dependency_ready_state": power_dependency_ready_state,
        "_release_power_dependency_transport": _release_power_dependency_transport,
        "probe_powered_hardware": probe_powered_hardware,
        "_power_dependency_monitor_loop": _power_dependency_monitor_loop,
        "_run_power_dependency_probe_if_due": _run_power_dependency_probe_if_due,
        "_start_power_dependency_monitor": _start_power_dependency_monitor,
        "_stop_power_dependency_monitor": _stop_power_dependency_monitor,
        "_stop_error_timer": _stop_error_timer,
        "send_state_archive": send_state_archive,
        "fix_state": fix_state,
        "check_func_allowance": check_func_allowance,
        "_get_lifecycle_lock": _get_lifecycle_lock,
        "_fault_recovery_due": _fault_recovery_due,
        "_record_controller_status": _record_controller_status,
        "_power_dependency_allows_hardware_operation": _power_dependency_allows_hardware_operation,
    }
