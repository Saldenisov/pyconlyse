"""One Tango owner for all four axes of a New Focus 8742 Ethernet controller."""

from __future__ import annotations

import math
import operator
import sys
import threading
import time
from pathlib import Path

from tango import DevState
from tango.server import Device, attribute, command, device_property

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from DeviceServers.motion.picomotor.transport import Picomotor8742


def integer_steps(value):
    if isinstance(value, bool):
        raise ValueError("Steps and axes must be integers, not booleans")
    try:
        result = operator.index(value)
    except TypeError as exc:
        raise ValueError("Steps and axes must be integers") from exc
    if not -(2**31) <= result < 2**31:
        raise ValueError("Value is outside the signed 32-bit controller range")
    return result


class DS_Picomotor8742(Device):  # noqa: N801 - Tango server naming convention
    """Position means the controller step counter, not measured mirror position.

    Move returns after command acceptance. A monitor checks completion without
    holding the Tango request thread. Faults remain latched until Reconnect.
    """

    host = device_property(dtype=str, default_value="")
    tcp_port = device_property(dtype=int, default_value=23)
    controller_address = device_property(dtype=int, default_value=0)
    io_timeout_s = device_property(dtype=float, default_value=1.0)
    motion_timeout_s = device_property(dtype=float, default_value=30.0)
    poll_interval_s = device_property(dtype=float, default_value=0.25)
    expected_identification = device_property(dtype=str, default_value="")
    motion_enabled = device_property(dtype=bool, default_value=False)
    # [axis1_min, axis1_max, ... axis4_min, axis4_max], in step-counter units.
    step_limits = device_property(dtype=(int,), default_value=[])

    def init_device(self):
        if getattr(self, "_active", None) is not None:
            raise RuntimeError("Cannot initialize during an active Picomotor operation")
        self._stop_monitor()
        previous = getattr(self, "_controller", None)
        if previous is not None:
            previous.close()
        super().init_device()
        self._lock = threading.RLock()
        self._quit = threading.Event()
        self._monitor = None
        self._active = None
        self._last_error = ""
        self._identification = ""
        self._positions = None
        self._done = None
        self._sample_time = 0.0
        self._controller = None
        self.set_state(DevState.INIT)
        try:
            for name in ("io_timeout_s", "motion_timeout_s", "poll_interval_s"):
                value = float(getattr(self, name))
                if not math.isfinite(value) or value <= 0:
                    raise ValueError(f"{name} must be finite and positive")
            if self.motion_enabled:
                self._limits()
            self._controller = Picomotor8742(
                host=self.host,
                port=self.tcp_port,
                timeout_s=self.io_timeout_s,
                controller_address=self.controller_address,
            )
            self._connect()
            self._start_monitor()
        except Exception as exc:
            if self._controller is not None:
                self._controller.close()
            self._fault(exc)

    def _limits(self):
        limits = [integer_steps(value) for value in self.step_limits]
        if len(limits) != 8:
            raise ValueError("Configure eight step_limits before enabling motion")
        if any(limits[i] > limits[i + 1] for i in range(0, 8, 2)):
            raise ValueError("Each minimum step limit must be <= its maximum")
        return limits

    def _connect(self):
        identity = self._controller.connect()
        if self.expected_identification and identity != self.expected_identification:
            self._controller.close()
            raise RuntimeError(
                "Controller identification differs from configured identity"
            )
        self._identification = identity
        self._refresh()

    def _fault(self, exc):
        if not self._last_error:
            self._last_error = str(exc)
        self.set_state(DevState.FAULT)
        self.set_status(
            f"Picomotor fault: {self._last_error}; use Reconnect; "
            "motion outcome may be unknown"
        )

    def _require_connection(self, *, allow_fault=False):
        if self._controller is None or not self._controller.connected:
            raise RuntimeError("Picomotor is disconnected; use Reconnect")
        if self._last_error and not allow_fault:
            raise RuntimeError(f"Picomotor fault is latched: {self._last_error}")

    def _refresh(self):
        """Publish only a complete fresh snapshot; failed reads invalidate access."""
        with self._lock:
            self._require_connection()
            done = [self._controller.motion_done(axis) for axis in range(1, 5)]
            # Read counters after idle confirmation, avoiding a mid-move TP?
            # followed by an idle MD? being misclassified as a target mismatch.
            positions = [self._controller.position(axis) for axis in range(1, 5)]
            operation = self._active
            if (
                operation is not None
                and not all(done)
                and time.monotonic() >= operation[2]
            ):
                try:
                    self._controller.abort()
                finally:
                    self._active = (operation[0], None, operation[2])
                    self._fault(
                        RuntimeError(
                            "Motion deadline expired; Abort requested, stop unverified"
                        )
                    )
                return
            if operation is not None and all(done):
                error = self._controller.error_code()
                if error:
                    raise RuntimeError(
                        f"Controller reported error {error} at completion"
                    )
                axis, target, _deadline = operation
                if target is not None and positions[axis - 1] != target:
                    raise RuntimeError("Idle counter differs from requested target")
                self._active = None
            self._positions, self._done = positions, done
            self._sample_time = time.time()
            self.set_state(DevState.ON if all(done) else DevState.MOVING)
            self.set_status(
                f"{self._identification}; step counters {positions}; "
                f"motion {'enabled' if self.motion_enabled else 'disabled'}"
            )

    def _tick(self):
        if self._last_error:
            return
        try:
            self._refresh()
        except Exception as exc:
            with self._lock:
                self._fault(exc)

    def _start_monitor(self):
        self._quit = threading.Event()

        def run():
            while not self._quit.wait(self.poll_interval_s):
                self._tick()

        self._monitor = threading.Thread(
            target=run, name="picomotor-status", daemon=True
        )
        self._monitor.start()

    def _stop_monitor(self):
        quit_event = getattr(self, "_quit", None)
        monitor = getattr(self, "_monitor", None)
        if quit_event is not None:
            quit_event.set()
        if monitor is not None and monitor.is_alive():
            monitor.join(timeout=10 * float(self.io_timeout_s) + 1)
            if monitor.is_alive():
                raise RuntimeError(
                    "Picomotor monitor did not stop; keep existing session"
                )

    def delete_device(self):
        self._stop_monitor()
        controller = getattr(self, "_controller", None)
        if controller is not None:
            try:
                if getattr(self, "_active", None) is not None and controller.connected:
                    controller.abort()
            finally:
                controller.close()

    def _sample(self):
        with self._lock:
            self._require_connection()
            try:
                self._refresh()
                self._require_connection()
            except Exception as exc:
                self._fault(exc)
                raise
            return list(self._positions), list(self._done), self._sample_time

    @attribute(dtype=str)
    def identification(self):
        return self._identification

    @attribute(
        dtype=(int,),
        max_dim_x=4,
        unit="steps",
        doc="TP? controller counters; no encoder feedback",
    )
    def positions_steps(self):
        return self._sample()[0]

    @attribute(dtype=(bool,), max_dim_x=4)
    def motion_done(self):
        return self._sample()[1]

    @attribute(
        dtype=float, unit="s", doc="UTC Unix time of last complete controller snapshot"
    )
    def sample_time(self):
        self._require_connection()
        return self._sample_time

    @attribute(dtype=str)
    def last_error(self):
        return self._last_error

    def _arguments(self, args):
        if len(args) != 2:
            raise ValueError("Expected [axis, integer_steps]")
        axis, value = map(integer_steps, args)
        if not 1 <= axis <= 4:
            raise ValueError("Axis must be 1..4")
        return axis, value

    def _move(self, args, *, relative):
        axis, value = self._arguments(args)
        with self._lock:
            self._require_connection()
            if not self.motion_enabled:
                raise RuntimeError("motion_enabled is False")
            limits = self._limits()
            self._sample()
            if self._active is not None or not all(self._done):
                raise RuntimeError("Controller already moving")
            target = integer_steps(
                self._positions[axis - 1] + value if relative else value
            )
            if not limits[2 * (axis - 1)] <= target <= limits[2 * (axis - 1) + 1]:
                raise ValueError("Target exceeds configured step-counter limits")
            self._active = (axis, target, time.monotonic() + self.motion_timeout_s)
            try:
                operation = (
                    self._controller.move_relative
                    if relative
                    else self._controller.move_absolute
                )
                operation(axis, value)
            except Exception as exc:
                # An I/O failure can follow an accepted move. Keep it pending.
                self._fault(exc)
                raise
            self.set_state(DevState.MOVING)
            self.set_status(f"Move accepted on axis {axis}; completion pending")

    @command(dtype_in=(int,), doc_in="[axis 1..4, signed relative steps]")
    def MoveRelative(self, args):
        self._move(args, relative=True)

    @command(dtype_in=(int,), doc_in="[axis 1..4, absolute step-counter target]")
    def MoveAbsolute(self, args):
        self._move(args, relative=False)

    @command(dtype_in=int, doc_in="Axis 1..4; decelerate with ST")
    def Stop(self, axis):
        axis = integer_steps(axis)
        if not 1 <= axis <= 4:
            raise ValueError("Axis must be 1..4")
        with self._lock:
            self._require_connection(allow_fault=True)
            try:
                self._controller.stop(axis)
                if self._active is None or self._active[0] == axis:
                    self._active = (
                        axis,
                        None,
                        time.monotonic() + self.motion_timeout_s,
                    )
                if not self._last_error:
                    self.set_state(DevState.MOVING)
                    self.set_status("Stop requested; waiting for fresh idle status")
            except Exception as exc:
                self._fault(exc)
                raise

    @command
    def Abort(self):
        with self._lock:
            self._require_connection(allow_fault=True)
            try:
                self._controller.abort()
                self._active = (1, None, time.monotonic() + self.motion_timeout_s)
                if not self._last_error:
                    self.set_state(DevState.MOVING)
                    self.set_status("Abort requested; waiting for fresh idle status")
            except Exception as exc:
                self._fault(exc)
                raise

    @command
    def Reconnect(self):
        """Explicitly resynchronize through reads; never replay a lost command."""
        with self._lock:
            if self._active is not None and not self._last_error:
                raise RuntimeError("Stop or Abort and confirm idle before Reconnect")
        self._stop_monitor()
        with self._lock:
            if self._controller is None:
                raise RuntimeError(
                    "Invalid configuration; correct properties and initialize"
                )
            unresolved_operation = self._active
            self._controller.close()
            self._active = None
            self._last_error = ""
            try:
                self._connect()
            except Exception as exc:
                self._active = unresolved_operation
                self._controller.close()
                self._fault(exc)
                raise
            if unresolved_operation is not None and not all(self._done):
                self._active = (
                    unresolved_operation[0],
                    None,
                    time.monotonic() + self.motion_timeout_s,
                )
            self._start_monitor()


if __name__ == "__main__":
    DS_Picomotor8742.run_server()
