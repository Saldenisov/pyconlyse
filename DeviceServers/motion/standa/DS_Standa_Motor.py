#!/usr/bin/env python


from sys import modules as _refactor_modules

import ctypes
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Tuple, Union

_STARTUP_TRACE_ORIGIN = time.perf_counter()
_STARTUP_TRACE_ENABLED = os.environ.get("PYCONLYSE_STARTUP_TIMING", "").strip() == "1"


def _startup_trace(label):
    if _STARTUP_TRACE_ENABLED:
        print(
            "STARTUP_TIMING "
            f"{label} elapsed_ms={(time.perf_counter() - _STARTUP_TRACE_ORIGIN) * 1000:.3f} "
            f"wall_ns={time.time_ns()}",
            flush=True,
        )


app_folder = Path(__file__).resolve().parents[3]
sys.path.append(str(app_folder))

from DeviceServers.motion.standa.standa_motor_methods_get_temp import _bind_standa_motor_methods_get_temp
from DeviceServers.motion.standa.standa_motor_methods_turn_on_local import _bind_standa_motor_methods_turn_on_local

from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, device_property

from DeviceServers.base.hardware_lifecycle import (
    HardwareConnectionState,
    InitializationState,
)
from DeviceServers.base.motor import DS_MOTORIZED_MONO_AXIS
from DeviceServers.motion.standa.discovery_cache import (
    load_discovery_snapshot,
    store_discovery_map,
)
from DeviceServers.motion.standa.transport import (
    StandaTransportBusyError,
    exclusive_standa_device_transport,
    exclusive_standa_transport,
)

try:
    from DeviceServers.motion.standa.ximc import (
        EnumerateFlags,
        GPIOFlags,
        PositionFlags,
        Result,
        XIMC_BACKEND,
        XIMC_BACKEND_ERROR,
        arch_type,
        get_position_t,
        lib,
        runtime_version,
        set_position_t,
        status_t,
        ximc_dir,
    )
except Exception:
    # Provide lightweight stubs so the module can be imported without native libs
    class _EnumerateFlags:
        ENUMERATE_PROBE = 0
        ENUMERATE_NETWORK = 0

    EnumerateFlags = _EnumerateFlags

    class _GPIOFlags:
        STATE_RIGHT_EDGE = 0x0001
        STATE_LEFT_EDGE = 0x0002

    GPIOFlags = _GPIOFlags
    PositionFlags = object

    class _Result:
        Ok = 0

    Result = _Result
    XIMC_BACKEND = "unavailable"
    XIMC_BACKEND_ERROR = "libximc import failed"
    arch_type = "win64"

    def get_position_t():
        return type("_pos", (), {"Position": 0, "uPosition": 0})()

    class _DummyLib:
        def __getattr__(self, _):
            raise RuntimeError("libximc not available in this environment")

    lib = _DummyLib()

    def runtime_version():
        return "unavailable"

    def set_position_t(*_, **__):
        return None

    status_t = object
    ximc_dir = Path()


class DS_Standa_Motor(DS_MOTORIZED_MONO_AXIS):
    """Device Server (Tango) controlling Standa hardware through libximc.dll."""

    _version_ = "0.7"
    _model_ = "STANDA step motor"
    polling_local = 1500
    recovery_fault_threshold = 10

    unit = device_property(dtype=str, default_value="")
    conversion = device_property(dtype=float, default_value=1.0)
    ip_address = device_property(dtype=str, default_value="10.20.30.204")
    usb_transport_lock_path = device_property(dtype=str, default_value="")
    usb_transport_lock_timeout_s = device_property(dtype=float, default_value=1.0)
    usb_status_failure_threshold = device_property(dtype=int, default_value=3)
    usb_recovery_initial_delay_s = device_property(dtype=float, default_value=3.0)
    usb_recovery_max_delay_s = device_property(dtype=float, default_value=60.0)
    usb_discovery_lock_timeout_s = device_property(dtype=float, default_value=15.0)
    usb_discovery_cache_ttl_s = device_property(dtype=float, default_value=30.0)
    usb_read_retry_count = device_property(dtype=int, default_value=1)
    usb_read_retry_delay_s = device_property(dtype=float, default_value=0.05)
    resume_connection_after_loss = device_property(dtype=int, default_value=1)
    enumerate_network_devices = device_property(dtype=int, default_value=0)
    initialize_on_startup = device_property(dtype=int, default_value=1)

    # if it is done so leave it like this
    position = attribute(
        label="Position",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        format="8.4f",
        doc="the position of axis",
        polling_period=polling_local,
        abs_change=0.001,
    )

    @attribute(
        label="Temperature",
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        unit="degC",
        polling_period=polling_local,
        doc="Temperature in tenths of degrees C.",
    )
    def temperature(self):
        return self._temperature

    _standa_motor_methods_get_temp = _bind_standa_motor_methods_get_temp(_refactor_modules[__name__])
    get_temp = _standa_motor_methods_get_temp["get_temp"]

    @attribute(
        label="Power current",
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        unit="mA",
        polling_period=polling_local,
    )
    def power_current(self):
        return self._power_current

    get_current = _standa_motor_methods_get_temp["get_current"]

    @attribute(
        label="Power voltage",
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        unit="V",
        polling_period=polling_local,
    )
    def power_voltage(self):
        return self._power_voltage

    get_voltage = _standa_motor_methods_get_temp["get_voltage"]

    @attribute(
        label="Power status",
        access=AttrWriteType.READ,
        dtype=str,
        display_level=DispLevel.OPERATOR,
        polling_period=polling_local,
    )
    def power_status(self):
        return self._power_status

    @attribute(
        label="libximc backend",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.EXPERT,
    )
    def libximc_backend(self):
        return str(getattr(self, "_libximc_backend", XIMC_BACKEND))

    @attribute(
        label="libximc runtime version",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.EXPERT,
    )
    def libximc_runtime_version(self):
        return str(getattr(self, "_libximc_runtime_version", "unknown"))

    @attribute(
        label="libximc backend error",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.EXPERT,
    )
    def libximc_backend_error(self):
        return str(getattr(self, "_libximc_backend_error", ""))

    @attribute(
        label="Transport error count",
        dtype=int,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
    )
    def transport_error_count(self):
        return int(getattr(self, "_transport_error_count", 0))

    @attribute(
        label="Recovered read count",
        dtype=int,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
    )
    def transport_retry_success_count(self):
        return int(getattr(self, "_transport_retry_success_count", 0))

    @attribute(
        label="Last transport error",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
    )
    def last_transport_error(self):
        return str(getattr(self, "_last_transport_error", ""))

    @attribute(
        label="Last transport error at (UTC)",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
    )
    def last_transport_error_at_utc(self):
        return str(getattr(self, "_last_transport_error_at_utc", ""))

    @attribute(
        label="Physical endpoint state",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        polling_period=polling_local,
        doc=(
            "Hardware end-switch readback. RIGHT or LEFT identifies the active "
            "physical endpoint; BETWEEN means neither switch is active."
        ),
    )
    def endpoint_state(self):
        # A passively discovered controller has a closed transport and its
        # numeric position may merely be the process-start default.  End-switch
        # status can still be sampled safely without initialising or moving it.
        if not self._has_open_transport():
            self._refresh_endpoint_state_passively()
        return str(getattr(self, "_endpoint_state", "UNKNOWN"))

    @attribute(
        label="Commanded flipper state",
        dtype=str,
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        polling_period=polling_local,
        doc=(
            "Last completed state command: UP_BLOCKED for -1, DOWN_CLEAR "
            "for +1. This is software command history, not physical readback."
        ),
    )
    def commanded_flipper_state(self):
        return str(getattr(self, "_commanded_flipper_state", "UNKNOWN"))

    def init_device(self):
        global _STARTUP_TRACE_ENABLED
        _startup_trace("init_device_enter")
        self._power_status = self.POWER_STATES[0]
        self._temperature = None
        self._power_current = 0
        self._power_voltage = 0
        self._standa_handle_open = False
        self._standa_resume_after_recovery = False
        self._last_known_uri = b""
        self._standa_auto_recovery_blocked = False
        self._transport_error_count = 0
        self._transport_retry_success_count = 0
        self._last_transport_error = ""
        self._last_transport_error_at_utc = ""
        self._endpoint_state = "UNKNOWN"
        self._commanded_flipper_state = "UNKNOWN"
        self._libximc_backend = XIMC_BACKEND
        self._libximc_backend_error = XIMC_BACKEND_ERROR
        self._libximc_runtime_version = runtime_version()
        self._standa_recovery_delay_s = max(
            0.1, float(self.usb_recovery_initial_delay_s or 3.0)
        )
        _startup_trace("base_init_enter")
        super().init_device()
        _startup_trace("base_init_exit")
        attr_prop = self.position.get_properties()
        attr_prop.unit = self.unit
        self.position.set_properties(attr_prop)
        self.register_variables_for_archive()
        # The base power monitor may have scheduled a delayed safe probe.  Keep
        # startup initialisation and that monitor mutually exclusive so the
        # probe cannot invalidate a handle while it is being opened.
        with self._get_lifecycle_lock():
            self._initialize_on_startup_if_requested()
        _startup_trace("init_device_exit")
        _STARTUP_TRACE_ENABLED = False

    _initialize_on_startup_if_requested = _standa_motor_methods_get_temp["_initialize_on_startup_if_requested"]


    def register_variables_for_archive(self):
        super().register_variables_for_archive()
        self.archive_state.update(
            {
                "current": (self.get_current, "float16"),
                "voltage": (self.get_voltage, "float16"),
                "temperature": (self.get_temp, "float16"),
                "position": (self.get_pos, "float16"),
            }
        )

    _transport_lock = _standa_motor_methods_get_temp["_transport_lock"]

    _discovery_transport_lock = _standa_motor_methods_get_temp["_discovery_transport_lock"]

    _utc_now_iso = (staticmethod)(_standa_motor_methods_get_temp["_utc_now_iso"])

    _record_transport_error = _standa_motor_methods_get_temp["_record_transport_error"]

    _read_transport_call = _standa_motor_methods_get_temp["_read_transport_call"]

    _endpoint_state_from_gpio_flags = (staticmethod)(_standa_motor_methods_get_temp["_endpoint_state_from_gpio_flags"])

    _update_endpoint_state = _standa_motor_methods_get_temp["_update_endpoint_state"]

    _refresh_endpoint_state_passively = _standa_motor_methods_get_temp["_refresh_endpoint_state_passively"]

    _has_open_transport = _standa_motor_methods_get_temp["_has_open_transport"]

    _close_handle_locked = (staticmethod)(_standa_motor_methods_get_temp["_close_handle_locked"])

    _invalidate_transport = _standa_motor_methods_get_temp["_invalidate_transport"]

    _schedule_transport_recovery = _standa_motor_methods_get_temp["_schedule_transport_recovery"]

    _reset_transport_recovery = _standa_motor_methods_get_temp["_reset_transport_recovery"]

    _enumerated_serial = (staticmethod)(_standa_motor_methods_get_temp["_enumerated_serial"])

    _serial_by_temporary_open = _standa_motor_methods_get_temp["_serial_by_temporary_open"]

    _set_passive_discovery_result = _standa_motor_methods_get_temp["_set_passive_discovery_result"]

    find_device = _standa_motor_methods_get_temp["find_device"]

    read_position_local = _standa_motor_methods_get_temp["read_position_local"]

    write_position_local = _standa_motor_methods_get_temp["write_position_local"]

    _standa_error = _standa_motor_methods_get_temp["_standa_error"]

    define_position_local = _standa_motor_methods_get_temp["define_position_local"]

    _open_verified_transport = _standa_motor_methods_get_temp["_open_verified_transport"]

    _resume_open_transport = _standa_motor_methods_get_temp["_resume_open_transport"]
    del _standa_motor_methods_get_temp

    _standa_motor_methods_turn_on_local = _bind_standa_motor_methods_turn_on_local(_refactor_modules[__name__])
    turn_on_local = _standa_motor_methods_turn_on_local["turn_on_local"]

    _attempt_recover_connection = _standa_motor_methods_turn_on_local["_attempt_recover_connection"]

    turn_off_local = _standa_motor_methods_turn_on_local["turn_off_local"]

    release_power_dependency_local = _standa_motor_methods_turn_on_local["release_power_dependency_local"]

    move_axis_local = _standa_motor_methods_turn_on_local["move_axis_local"]

    _flipper_state_for_target = (staticmethod)(_standa_motor_methods_turn_on_local["_flipper_state_for_target"])

    _uses_commanded_flipper_state = _standa_motor_methods_turn_on_local["_uses_commanded_flipper_state"]

    def _motion_target_reached(self, target):
        if self._uses_commanded_flipper_state():
            expected = self._flipper_state_for_target(target)
            return expected != "UNKNOWN" and getattr(
                self, "_commanded_flipper_state", "UNKNOWN"
            ) == expected
        return super()._motion_target_reached(target)

    def _refresh_motion_readback(self):
        if not self._uses_commanded_flipper_state():
            super()._refresh_motion_readback()

    stop_movement_local = _standa_motor_methods_turn_on_local["stop_movement_local"]
    del _standa_motor_methods_turn_on_local

    def get_controller_status_local(self) -> Union[int, str]:
        if not self._has_open_transport():
            if self.get_state() != DevState.FAULT:
                self.set_state(DevState.FAULT)
                self._schedule_transport_recovery()
            if self._attempt_recover_connection():
                return 0
            return f"STANDA transport is unavailable for {self.device_name}."

        x_status = status_t()
        try:
            result = self._read_transport_call(
                "get_status",
                lib.get_status,
                self._device_id_internal,
                ctypes.byref(x_status),
            )
        except StandaTransportBusyError:
            # A competing server is using libximc.  Skipping one health sample
            # is safer than treating ordinary bus serialization as a USB fault.
            self.warn("STANDA status poll skipped: shared USB transport is busy.")
            return 0
        except Exception as error:
            self._record_transport_error("get_status_exception", error)
            result = f"USB exception: {error}"

        if result == Result.Ok:
            self._update_endpoint_state(x_status)
            self._temperature = x_status.CurT / 10.0
            self._power_current = x_status.Ipwr
            self._power_voltage = x_status.Upwr / 100.0
            self._power_status = self.POWER_STATES.get(
                x_status.PWRSts, self.POWER_STATES[0]
            )

            self._status_check_fault = 0
            self._reset_transport_recovery()
            if self.get_state() == DevState.FAULT:
                self.set_state(DevState.ON)
            return super().get_controller_status_local()

        self._status_check_fault += 1
        threshold = max(
            1,
            int(
                getattr(
                    self, "usb_status_failure_threshold", self.recovery_fault_threshold
                )
                or self.recovery_fault_threshold
            ),
        )
        if self._status_check_fault < threshold:
            self.warn(
                f"STANDA USB status failure {self._status_check_fault}/{threshold} "
                f"for {self.device_name}: {result}; retaining current transport.",
                True,
            )
            return 0

        was_moving = self.get_state() == DevState.MOVING
        self._invalidate_transport()
        self._status_check_fault = 0
        self.set_state(DevState.FAULT)
        self.set_hardware_lifecycle(
            HardwareConnectionState.DISCONNECTED,
            InitializationState.FAILED,
            f"STANDA USB connection was lost: {result}",
        )
        if was_moving:
            self._standa_auto_recovery_blocked = True
            self._next_fault_recovery_at = float("inf")
            return (
                f"STANDA USB connection lost during motion for {self.device_name}: "
                f"{result}. Automatic recovery is blocked pending safety inspection."
            )

        self._schedule_transport_recovery()
        return (
            f"STANDA USB connection lost for {self.device_name}: {result}. "
            "Passive rediscovery will use exponential backoff."
        )


if __name__ == "__main__":
    DS_Standa_Motor.run_server()
