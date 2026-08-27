#!/usr/bin/env python


import ctypes
import os
import sys
import time
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

from DeviceServers.base.motor import DS_MOTORIZED_MONO_AXIS
from DeviceServers.motion.standa.transport import (
    StandaTransportBusyError,
    exclusive_standa_transport,
)

try:
    from DeviceServers.motion.standa.ximc import (
        EnumerateFlags,
        PositionFlags,
        Result,
        arch_type,
        get_position_t,
        lib,
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
    arch_type = "win64"

    def get_position_t():
        return type("_pos", (), {"Position": 0, "uPosition": 0})()

    class _DummyLib:
        def __getattr__(self, _):
            raise RuntimeError("libximc not available in this environment")

    lib = _DummyLib()

    def set_position_t(*_, **__):
        return None

    status_t = object
    ximc_dir = Path()


class DS_Standa_Motor(DS_MOTORIZED_MONO_AXIS):
    """Device Server (Tango) controlling Standa hardware through libximc.dll."""

    _version_ = "0.5"
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

    def init_device(self):
        global _STARTUP_TRACE_ENABLED
        _startup_trace("init_device_enter")
        self._power_status = self.POWER_STATES[0]
        self._temperature = None
        self._power_current = 0
        self._power_voltage = 0
        self._standa_handle_open = False
        self._standa_auto_recovery_blocked = False
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
        return exclusive_standa_transport(
            self.usb_transport_lock_path or None,
            timeout_seconds=max(0.1, float(timeout or 1.0)),
        )

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

    def find_device(self):
        _startup_trace("find_device_enter")
        state_ok = self.check_func_allowance(self.find_device)
        discovered_uri = b""
        if not state_ok:
            return

        self.info(f"Searching for STANDA device {self.device_id}", True)
        try:
            # Enumeration itself opens every connected controller.  A single
            # host-wide lock prevents simultaneous recoveries from disrupting
            # one another when USB is noisy during accelerator operation.
            _startup_trace("transport_lock_wait")
            # Discovery is passive and can be retried by recovery. Do not hold
            # Tango registration for the normal one-second command lock wait.
            with self._transport_lock(timeout_s=0.1):
                _startup_trace("transport_lock_acquired")
                lib.set_bindy_key(
                    str(Path(ximc_dir / arch_type / "keyfile.sqlite")).encode("utf-8")
                )
                probe_flags = (
                    EnumerateFlags.ENUMERATE_PROBE + EnumerateFlags.ENUMERATE_NETWORK
                )
                enum_hints = f"addr={self.ip_address}".encode()
                _startup_trace("enumerate_devices_enter")
                devenum = lib.enumerate_devices(probe_flags, enum_hints)
                _startup_trace("enumerate_devices_exit")
                device_counts = lib.get_device_count(devenum)
                for index in range(max(0, device_counts)):
                    uri = lib.get_device_name(devenum, index)
                    device_handle = lib.open_device(uri)
                    if device_handle < 0:
                        continue
                    try:
                        serial = ctypes.c_uint()
                        result = lib.get_serial_number(
                            device_handle, ctypes.byref(serial)
                        )
                        if (
                            result == Result.Ok
                            and int(self.device_id) == int(serial.value)
                        ):
                            discovered_uri = uri
                            break
                    finally:
                        self._close_handle_locked(device_handle)
        except StandaTransportBusyError as error:
            self.warn(f"STANDA discovery deferred: {error}", True)
        except Exception as error:
            self.warn(f"STANDA discovery failed: {error}", True)

        self._standa_handle_open = False
        self._uri = discovered_uri
        # A closed probe handle remains only as a discovery marker.  Commands
        # use it only after turn_on_local reopens the selected URI.
        self._device_id_internal = 0 if discovered_uri else -1
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
            with self._transport_lock():
                result = lib.get_position(self._device_id_internal, ctypes.byref(pos))
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

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1 or not self._uri:
            self.info(f"Searching for device: {self.device_id}", True)
            self.find_device()

        if self._device_id_internal == -1:
            return f"Could NOT turn on {self.device_name}: Device could not be found."

        try:
            with self._transport_lock():
                res = lib.open_device(self._uri)
        except StandaTransportBusyError as error:
            return f"Could NOT turn on {self.device_name}: {error}."
        except Exception as error:
            return f"Could NOT turn on {self.device_name}: {error}."

        if res >= 0:
            self._device_id_internal = res
            self._standa_handle_open = True
            self._reset_transport_recovery()
            self.set_state(DevState.ON)
            self.stop_movement_local()
            self.read_position_local()
            return 0
        self.set_state(DevState.FAULT)
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
        self._invalidate_transport()
        try:
            self.find_device()
            res = 0 if self._device_id_internal != -1 else "controller unavailable"
        except Exception as e:
            self._schedule_transport_recovery()
            self.warn(f"STANDA recovery discovery failed: {e}", True)
            return False

        if res == 0:
            self._reset_transport_recovery()
            self.set_state(DevState.STANDBY)
            self.info(
                f"STANDA transport discovery succeeded for {self.device_name}; "
                "awaiting explicit turn_on.",
                True,
            )
            return True

        self._schedule_transport_recovery()
        self.warn(f"STANDA recovery deferred for {self.device_name}: {res}", True)
        return False

    def turn_off_local(self) -> Union[int, str]:
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
            with self._transport_lock():
                result = lib.get_status(
                    self._device_id_internal, ctypes.byref(x_status)
                )
        except StandaTransportBusyError:
            # A competing server is using libximc.  Skipping one health sample
            # is safer than treating ordinary bus serialization as a USB fault.
            self.warn("STANDA status poll skipped: shared USB transport is busy.")
            return 0
        except Exception as error:
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
