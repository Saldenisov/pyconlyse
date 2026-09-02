#!/usr/bin/env python


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

    _version_ = "0.6"
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

    def get_temp(self):
        return self._temperature

    @attribute(
        label="Power current",
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        unit="mA",
        polling_period=polling_local,
    )
    def power_current(self):
        return self._power_current

    def get_current(self):
        return self._power_current

    @attribute(
        label="Power voltage",
        access=AttrWriteType.READ,
        display_level=DispLevel.OPERATOR,
        unit="V",
        polling_period=polling_local,
    )
    def power_voltage(self):
        return self._power_voltage

    def get_voltage(self):
        return self._power_voltage

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
        # Device-server startup only discovers the controller.  It must not
        # initialise axes, stop a motion, or energise a motor.
        if self._device_id_internal != -1 and self.get_state() != DevState.FAULT:
            self.set_state(DevState.STANDBY)
            self.info(
                f"{self.device_name} controller discovered; awaiting explicit turn_on.",
                True,
            )
        _startup_trace("init_device_exit")
        _STARTUP_TRACE_ENABLED = False


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

    def _transport_lock(self, timeout_s=None):
        timeout = (
            self.usb_transport_lock_timeout_s
            if timeout_s is None
            else timeout_s
        )
        if self.usb_transport_lock_path:
            return exclusive_standa_transport(
                self.usb_transport_lock_path,
                timeout_seconds=max(0.1, float(timeout or 1.0)),
            )
        return exclusive_standa_device_transport(
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
        return exclusive_standa_transport(
            self.usb_transport_lock_path or None,
            timeout_seconds=max(0.1, float(timeout or 1.0)),
        )

    @staticmethod
    def _utc_now_iso():
        return datetime.now(timezone.utc).isoformat()

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
            if result == Result.Ok:
                return result
            self._record_transport_error(operation, result)
            if result != Result.Error:
                return result
            reset_locks = getattr(lib, "reset_locks", None)
            if not callable(reset_locks):
                return result
            for _attempt in range(retries):
                reset_locks()
                time.sleep(
                    max(0.0, float(getattr(self, "usb_read_retry_delay_s", 0.05)))
                )
                result = function(*args)
                if result == Result.Ok:
                    self._transport_retry_success_count = int(
                        getattr(self, "_transport_retry_success_count", 0)
                    ) + 1
                    return result
                self._record_transport_error(operation, result)
                if result != Result.Error:
                    return result
            return result

    def _has_open_transport(self) -> bool:
        return bool(
            getattr(
                self,
                "_standa_handle_open",
                getattr(self, "_device_id_internal", -1) not in (-1, None),
            )
        )

    @staticmethod
    def _close_handle_locked(device_handle) -> int:
        if device_handle in (-1, None):
            return 0
        handle = ctypes.cast(device_handle, ctypes.POINTER(ctypes.c_int))
        return lib.close_device(ctypes.byref(handle))

    def _invalidate_transport(self) -> None:
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
        self._next_fault_recovery_at = time.monotonic() + delay
        self._standa_recovery_delay_s = min(max_delay, delay * 2.0)

    def _reset_transport_recovery(self) -> None:
        self._status_check_fault = 0
        self._standa_auto_recovery_blocked = False
        self._standa_recovery_delay_s = max(
            0.1, float(self.usb_recovery_initial_delay_s or 3.0)
        )

    @staticmethod
    def _enumerated_serial(devenum, index):
        get_serial = getattr(lib, "get_enumerate_device_serial", None)
        if not callable(get_serial):
            return None
        serial = ctypes.c_uint()
        result = get_serial(devenum, index, ctypes.byref(serial))
        if result == Result.Ok:
            return int(serial.value)
        return None

    def _serial_by_temporary_open(self, uri):
        """Compatibility fallback for legacy enumeration without serial data."""

        device_handle = lib.open_device(uri)
        if device_handle < 0:
            return None
        try:
            serial = ctypes.c_uint()
            result = lib.get_serial_number(device_handle, ctypes.byref(serial))
            if result == Result.Ok:
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
        _startup_trace("find_device_enter")
        state_ok = self.check_func_allowance(self.find_device)
        discovered_uri = b""
        if not state_ok:
            return

        self.info(f"Searching for STANDA device {self.device_id}", True)
        cache_ttl = max(0.0, float(self.usb_discovery_cache_ttl_s or 0.0))
        cached_devices = load_discovery_snapshot(cache_ttl)
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
            _startup_trace("transport_lock_wait")
            # A complete probe can take longer than an ordinary controller
            # command. Once inside the host-wide lock, recheck the cache: a
            # preceding Tango process may already have completed the scan.
            with self._discovery_transport_lock(
                timeout_s=max(
                    0.1, float(self.usb_discovery_lock_timeout_s or 15.0)
                )
            ):
                _startup_trace("transport_lock_acquired")
                cached_devices = load_discovery_snapshot(cache_ttl)
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
                set_bindy_key = getattr(lib, "set_bindy_key", None)
                keyfile = Path(ximc_dir / arch_type / "keyfile.sqlite")
                if callable(set_bindy_key) and keyfile.exists():
                    set_bindy_key(str(keyfile).encode("utf-8"))
                probe_flags = EnumerateFlags.ENUMERATE_PROBE
                enum_hints = b""
                if bool(int(self.enumerate_network_devices or 0)):
                    probe_flags |= EnumerateFlags.ENUMERATE_NETWORK
                    enum_hints = f"addr={self.ip_address}".encode()
                _startup_trace("enumerate_devices_enter")
                devenum = lib.enumerate_devices(probe_flags, enum_hints)
                _startup_trace("enumerate_devices_exit")
                device_counts = lib.get_device_count(devenum)
                for index in range(max(0, device_counts)):
                    uri = lib.get_device_name(devenum, index)
                    serial = self._enumerated_serial(devenum, index)
                    if serial is None:
                        serial = self._serial_by_temporary_open(uri)
                    if serial is not None:
                        discovered_devices[int(serial)] = uri
                    if int(self.device_id) == serial:
                        discovered_uri = uri
                store_discovery_map(discovered_devices)
        except StandaTransportBusyError as error:
            self.warn(f"STANDA discovery deferred: {error}", True)
        except Exception as error:
            self.warn(f"STANDA discovery failed: {error}", True)
        finally:
            if devenum is not None:
                free_enumeration = getattr(lib, "free_enumerate_devices", None)
                if callable(free_enumeration):
                    try:
                        free_enumeration(devenum)
                    except Exception as error:
                        self.warn(f"STANDA enumeration cleanup failed: {error}")

        # A closed probe handle remains only as a discovery marker. Commands
        # use it only after turn_on_local reopens and verifies the selected URI.
        self._set_passive_discovery_result(discovered_uri)
        if discovered_uri:
            self.set_state(DevState.STANDBY)
        _startup_trace("find_device_exit")

    def read_position_local(self) -> Union[int, str]:
        if not self._has_open_transport():
            return (
                f"Could not read position of {self.device_name}: "
                "STANDA transport is not open."
            )
        pos = get_position_t()
        try:
            result = self._read_transport_call(
                "get_position",
                lib.get_position,
                self._device_id_internal,
                ctypes.byref(pos),
            )
        except StandaTransportBusyError:
            return (
                f"Could not read position of {self.device_name}: "
                "STANDA USB transport is busy."
            )
        except Exception as error:
            return f"Could not read position of {self.device_name}: {error}."
        if result == Result.Ok:
            pos_microsteps = pos.Position * 256 + pos.uPosition
            pos_basic_units = pos_microsteps / 256
            self._position = round(pos_basic_units / self.conversion, 3)
            return 0
        return f"Could not read position of {self.device_name}: {result}."

    def write_position_local(self, pos) -> Union[int, str]:
        self.move_axis(pos)
        return 0

    def _standa_error(self, error: int) -> Tuple[bool, str]:
        # TODO: finish filling different errors values
        if error == 0:
            res, comments = True, ""
        elif error == -1:
            res, comments = False, "Standa: generic error."
        else:
            res, comments = False, "Standa: unknown error."

        return res, comments

    def define_position_local(self, position) -> Union[str, int]:
        if not self._has_open_transport():
            return (
                f"Could not define position of {self.device_name}: "
                "STANDA transport is not open."
            )
        position = position * self.conversion
        pos_steps = int(position // 1)
        pos_microsteps = int(position % 1 * 256)
        pos_standa = set_position_t()
        pos_standa.Position = ctypes.c_int(pos_steps)
        pos_standa.uPosition = ctypes.c_int(pos_microsteps)
        pos_standa.EncPosition = ctypes.c_longlong(0)
        pos_standa.PosFlags = ctypes.c_uint(PositionFlags.SETPOS_IGNORE_ENCODER)
        try:
            with self._transport_lock():
                result = lib.set_position(
                    self._device_id_internal, ctypes.byref(pos_standa)
                )
        except StandaTransportBusyError as error:
            return f"Could not define position of {self.device_name}: {error}."
        except Exception as error:
            return f"Could not define position of {self.device_name}: {error}."
        if result == Result.Ok:
            return 0
        return f"Could not define position of {self.device_name}: {result}."

    def _open_verified_transport(self, uri):
        """Open one URI and verify that it is the configured controller."""

        if not uri:
            return -1, "empty URI"
        try:
            with self._transport_lock():
                handle = lib.open_device(uri)
                if handle < 0:
                    return handle, f"open_device returned {handle}"
                serial = ctypes.c_uint()
                result = lib.get_serial_number(handle, ctypes.byref(serial))
                if result != Result.Ok or int(serial.value) != int(self.device_id):
                    self._close_handle_locked(handle)
                    return -1, (
                        f"serial verification failed: result={result}, "
                        f"serial={serial.value}"
                    )
                return handle, ""
        except StandaTransportBusyError as error:
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

        status = status_t()
        try:
            result = self._read_transport_call(
                "reopen_get_status",
                lib.get_status,
                handle,
                ctypes.byref(status),
            )
            if result != Result.Ok or self.read_position_local() != 0:
                self._invalidate_transport()
                return False
        except Exception as error:
            self._record_transport_error("reopen_validation", error)
            self._invalidate_transport()
            return False

        self._reset_transport_recovery()
        self.set_state(DevState.ON)
        self.set_hardware_lifecycle(
            HardwareConnectionState.READY,
            InitializationState.SUCCEEDED,
            "STANDA transport automatically reopened and verified; no movement or stop command was issued",
        )
        self.info(
            f"STANDA transport safely resumed for {self.device_name} without movement.",
            True,
        )
        return True

    def turn_on_local(self) -> Union[int, str]:
        self.set_hardware_lifecycle(
            HardwareConnectionState.CONNECTING,
            InitializationState.IN_PROGRESS,
            "opening STANDA transport for explicit axis initialisation",
        )
        if self._device_id_internal == -1 or not self._uri:
            self.info(f"Searching for device: {self.device_id}", True)
            self.find_device()

        if self._device_id_internal == -1:
            self.set_hardware_lifecycle(
                HardwareConnectionState.DISCONNECTED,
                InitializationState.FAILED,
                "STANDA controller was not found during explicit initialisation",
            )
            return f"Could NOT turn on {self.device_name}: Device could not be found."

        res, open_error = self._open_verified_transport(self._uri)
        if res < 0:
            self.set_hardware_lifecycle(
                HardwareConnectionState.DISCONNECTED,
                InitializationState.FAILED,
                f"could not open and verify STANDA transport: {open_error}",
            )
            return f"Could NOT turn on {self.device_name}: {open_error}."

        if res >= 0:
            self._device_id_internal = res
            self._standa_handle_open = True
            self._reset_transport_recovery()
            self.set_state(DevState.ON)
            stop_result = self.stop_movement_local()
            if stop_result not in (None, 0):
                self._invalidate_transport()
                self.set_state(DevState.FAULT)
                self.set_hardware_lifecycle(
                    HardwareConnectionState.CONNECTED,
                    InitializationState.FAILED,
                    str(stop_result),
                )
                return stop_result
            position_result = self.read_position_local()
            if position_result not in (None, 0):
                self._invalidate_transport()
                self.set_state(DevState.FAULT)
                self.set_hardware_lifecycle(
                    HardwareConnectionState.CONNECTED,
                    InitializationState.FAILED,
                    str(position_result),
                )
                return position_result
            self.set_hardware_lifecycle(
                HardwareConnectionState.READY,
                InitializationState.SUCCEEDED,
                "STANDA transport is open and the axis is initialised",
            )
            self._standa_resume_after_recovery = bool(
                int(self.resume_connection_after_loss or 0)
            )
            return 0
        self.set_state(DevState.FAULT)
        self.set_hardware_lifecycle(
            HardwareConnectionState.DISCONNECTED,
            InitializationState.FAILED,
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
        self.set_state(DevState.FAULT)
        self.set_hardware_lifecycle(
            HardwareConnectionState.DISCONNECTED,
            InitializationState.NOT_REQUESTED,
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
            self.set_state(DevState.STANDBY)
            self.set_hardware_lifecycle(
                HardwareConnectionState.CONNECTED,
                InitializationState.NOT_REQUESTED,
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
            HardwareConnectionState.DISCONNECTED,
            InitializationState.NOT_REQUESTED,
            f"STANDA passive discovery deferred: {res}",
        )
        self.warn(f"STANDA recovery deferred for {self.device_name}: {res}", True)
        return False

    def turn_off_local(self) -> Union[int, str]:
        self._standa_resume_after_recovery = False
        if not self._has_open_transport():
            self._device_id_internal = -1
            self._uri = b""
            self.set_state(DevState.OFF)
            return 0

        try:
            with self._transport_lock():
                result = self._close_handle_locked(self._device_id_internal)
        except StandaTransportBusyError as error:
            return f"Could not turn off device {self.device_name}: {error}."
        except Exception as error:
            return f"Could not turn off device {self.device_name}: {error}."
        sleep(0.05)
        if result == 0:
            self.set_state(DevState.OFF)
            self._device_id_internal = -1
            self._uri = ""
            self._standa_handle_open = False
            return 0
        self.set_state(DevState.FAULT)
        return self.error(f"Could not turn off device {self.device_name}: {result}.")

    def release_power_dependency_local(self) -> None:
        """Close a local controller handle after external PDU power loss."""
        self._invalidate_transport()

    def move_axis_local(self, pos) -> Union[int, str]:
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
                result = lib.command_move(self._device_id_internal, steps, microsteps)
        except StandaTransportBusyError as error:
            return f"Move command for {self.device_name} did NOT work: {error}."
        except Exception as error:
            return f"Move command for {self.device_name} did NOT work: {error}."
        self.set_state(DevState.MOVING)
        if result == Result.Ok:
            try:
                # Do not hold the host-wide lock while waiting: a concurrent
                # stop command must stay able to reach a moving axis.
                result = lib.command_wait_for_stop(
                    self._device_id_internal, self.wait_time
                )
            except Exception as error:
                return f"{self.device_name} did NOT stop moving yet: {error}."
        else:
            return f"Move command for {self.device_name} did NOT work: {result}."

        if result != Result.Ok:
            return f"{self.device_name} did NOT stop moving yet: {result}."
        self.set_state(DevState.ON)
        return 0

    def stop_movement_local(self) -> Union[int, str]:
        if not self._has_open_transport():
            return (
                f"Axis movement of device {self.device_name} cannot be stopped: "
                "STANDA transport is not open."
            )
        try:
            with self._transport_lock():
                result = lib.command_stop(self._device_id_internal)
        except StandaTransportBusyError as error:
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
            self.set_state(DevState.ON)
            self.info(
                f"Axis movement of device {self.device_name} was stopped by user."
            )
            return 0
        return f"Axis movement of device {self.device_name} WAS NOT stopped by user."

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
