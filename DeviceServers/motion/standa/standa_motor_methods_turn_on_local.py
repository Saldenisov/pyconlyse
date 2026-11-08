"""Implementation for turn_on_local and related operations."""


def _bind_standa_motor_methods_turn_on_local(api):
    """Bind implementation to the owning module and its runtime state."""

    def turn_on_local(self) -> api.Union[int, str]:
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.CONNECTING,
            api.InitializationState.IN_PROGRESS,
            "opening STANDA transport for axis initialisation",
        )
        if self._device_id_internal == -1 or not self._uri:
            self.info(f"Searching for device: {self.device_id}", True)
            self.find_device()

        if self._device_id_internal == -1:
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.DISCONNECTED,
                api.InitializationState.FAILED,
                "STANDA controller was not found during axis initialisation",
            )
            return f"Could NOT turn on {self.device_name}: Device could not be found."

        res, open_error = self._open_verified_transport(self._uri)
        if res < 0:
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.DISCONNECTED,
                api.InitializationState.FAILED,
                f"could not open and verify STANDA transport: {open_error}",
            )
            return f"Could NOT turn on {self.device_name}: {open_error}."

        if res >= 0:
            self._device_id_internal = res
            self._standa_handle_open = True
            self._reset_transport_recovery()
            self.set_state(api.DevState.ON)
            stop_result = self.stop_movement_local()
            if stop_result not in (None, 0):
                self._invalidate_transport()
                self.set_state(api.DevState.FAULT)
                self.set_hardware_lifecycle(
                    api.HardwareConnectionState.CONNECTED,
                    api.InitializationState.FAILED,
                    str(stop_result),
                )
                return stop_result
            position_result = self.read_position_local()
            if position_result not in (None, 0):
                self._invalidate_transport()
                self.set_state(api.DevState.FAULT)
                self.set_hardware_lifecycle(
                    api.HardwareConnectionState.CONNECTED,
                    api.InitializationState.FAILED,
                    str(position_result),
                )
                return position_result
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.READY,
                api.InitializationState.SUCCEEDED,
                "STANDA transport is open and the axis is initialised",
            )
            self._standa_resume_after_recovery = bool(
                int(self.resume_connection_after_loss or 0)
            )
            return 0
        self.set_state(api.DevState.FAULT)
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.DISCONNECTED,
            api.InitializationState.FAILED,
            f"STANDA open_device returned {res}",
        )
        return f"Could NOT turn on {self.device_name}: {res}."

    def _attempt_recover_connection(self) -> bool:
        if getattr(self, "_standa_auto_recovery_blocked", False):
            self.warn(
                "STANDA automatic recovery is blocked after USB loss during motion; "
                "inspect the axis before an explicit turn_on.",
                True,
            )
            return False
        self.info(
            f"Attempting STANDA transport discovery for {self.device_name}; "
            "no axis initialisation or movement will be issued.",
            True,
        )
        self.set_state(api.DevState.FAULT)
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.DISCONNECTED,
            api.InitializationState.NOT_REQUESTED,
            "STANDA transport is unavailable; passive discovery is pending",
        )
        self._invalidate_transport()
        should_resume = bool(
            getattr(self, "_standa_resume_after_recovery", False)
            and int(getattr(self, "resume_connection_after_loss", 1) or 0)
        )
        if should_resume:
            last_uri = getattr(self, "_last_known_uri", b"")
            if last_uri and self._resume_open_transport(last_uri):
                return True
        try:
            self.find_device()
            res = 0 if self._device_id_internal != -1 else "controller unavailable"
        except Exception as e:
            self._schedule_transport_recovery()
            self.warn(f"STANDA recovery discovery failed: {e}", True)
            return False

        if res == 0 and should_resume:
            if self._resume_open_transport(self._uri):
                return True
            self._invalidate_transport()
            res = "controller rediscovered but safe reopen verification failed"

        if res == 0:
            self._reset_transport_recovery()
            self.set_state(api.DevState.STANDBY)
            self.set_hardware_lifecycle(
                api.HardwareConnectionState.CONNECTED,
                api.InitializationState.NOT_REQUESTED,
                "STANDA controller discovered passively; explicit initialisation is required",
            )
            self.info(
                f"STANDA transport discovery succeeded for {self.device_name}; "
                "awaiting explicit turn_on.",
                True,
            )
            return True

        self._schedule_transport_recovery()
        self.set_hardware_lifecycle(
            api.HardwareConnectionState.DISCONNECTED,
            api.InitializationState.NOT_REQUESTED,
            f"STANDA passive discovery deferred: {res}",
        )
        self.warn(f"STANDA recovery deferred for {self.device_name}: {res}", True)
        return False

    def turn_off_local(self) -> api.Union[int, str]:
        self._standa_resume_after_recovery = False
        if not self._has_open_transport():
            self._device_id_internal = -1
            self._uri = b""
            self.set_state(api.DevState.OFF)
            return 0

        try:
            with self._transport_lock():
                result = self._close_handle_locked(self._device_id_internal)
        except api.StandaTransportBusyError as error:
            return f"Could not turn off device {self.device_name}: {error}."
        except Exception as error:
            return f"Could not turn off device {self.device_name}: {error}."
        api.sleep(0.05)
        if result == 0:
            self.set_state(api.DevState.OFF)
            self._device_id_internal = -1
            self._uri = ""
            self._standa_handle_open = False
            self._commanded_flipper_state = "UNKNOWN"
            return 0
        self.set_state(api.DevState.FAULT)
        return self.error(f"Could not turn off device {self.device_name}: {result}.")

    def release_power_dependency_local(self) -> None:
        """Close a local controller handle after external PDU power loss."""
        self._invalidate_transport()

    def move_axis_local(self, pos) -> api.Union[int, str]:
        is_flipper = self._uses_commanded_flipper_state()
        target_state = self._flipper_state_for_target(pos)
        if is_flipper:
            self._commanded_flipper_state = "UNKNOWN"
        if not self._has_open_transport():
            return (
                f"Move command for {self.device_name} did NOT work: "
                "STANDA transport is not open."
            )
        pos = pos * self.conversion
        microsteps = int(pos % 1 * 256)
        steps = int(pos // 1)
        try:
            with self._transport_lock():
                result = api.lib.command_move(self._device_id_internal, steps, microsteps)
        except api.StandaTransportBusyError as error:
            return f"Move command for {self.device_name} did NOT work: {error}."
        except Exception as error:
            return f"Move command for {self.device_name} did NOT work: {error}."
        self.set_state(api.DevState.MOVING)
        if result == api.Result.Ok:
            try:
                # Do not hold the host-wide lock while waiting: a concurrent
                # stop command must stay able to reach a moving axis.
                result = api.lib.command_wait_for_stop(
                    self._device_id_internal, self.wait_time
                )
            except Exception as error:
                return f"{self.device_name} did NOT stop moving yet: {error}."
        else:
            return f"Move command for {self.device_name} did NOT work: {result}."

        if result != api.Result.Ok:
            return f"{self.device_name} did NOT stop moving yet: {result}."
        self.set_state(api.DevState.ON)
        if is_flipper:
            self._commanded_flipper_state = target_state
        return 0

    def _flipper_state_for_target(target):
        if float(target) == -1.0:
            return "UP_BLOCKED"
        if float(target) == 1.0:
            return "DOWN_CLEAR"
        return "UNKNOWN"

    def _uses_commanded_flipper_state(self):
        return (
            str(self.unit).strip().lower() == "state"
            and str(self.get_name()).strip().lower().endswith(("/s1", "/s2"))
        )

    def stop_movement_local(self) -> api.Union[int, str]:
        if self._uses_commanded_flipper_state():
            self._commanded_flipper_state = "UNKNOWN"
        if not self._has_open_transport():
            return (
                f"Axis movement of device {self.device_name} cannot be stopped: "
                "STANDA transport is not open."
            )
        try:
            with self._transport_lock():
                result = api.lib.command_stop(self._device_id_internal)
        except api.StandaTransportBusyError as error:
            return (
                f"Axis movement of device {self.device_name} WAS NOT stopped: "
                f"{error}."
            )
        except Exception as error:
            return (
                f"Axis movement of device {self.device_name} WAS NOT stopped: "
                f"{error}."
            )
        if result == 0:
            self.set_state(api.DevState.ON)
            self.info(
                f"Axis movement of device {self.device_name} was stopped by user."
            )
            return 0
        return f"Axis movement of device {self.device_name} WAS NOT stopped by user."

    return {
        "turn_on_local": turn_on_local,
        "_attempt_recover_connection": _attempt_recover_connection,
        "turn_off_local": turn_off_local,
        "release_power_dependency_local": release_power_dependency_local,
        "move_axis_local": move_axis_local,
        "_flipper_state_for_target": _flipper_state_for_target,
        "_uses_commanded_flipper_state": _uses_commanded_flipper_state,
        "stop_movement_local": stop_movement_local,
    }
