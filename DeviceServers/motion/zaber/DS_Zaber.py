"""Tango device server for the VD2 Zaber stage; public positions are millimetres."""

from __future__ import annotations

import threading
from pathlib import Path
import sys

from tango import DevState
from tango.server import Device, attribute, command, device_property

try:
    from DeviceServers.motion.zaber.reconnect import ZaberConnectionMonitor
    from DeviceServers.motion.zaber.stage import ZaberStage
except ModuleNotFoundError:
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from DeviceServers.motion.zaber.reconnect import ZaberConnectionMonitor
    from DeviceServers.motion.zaber.stage import ZaberStage


class DS_Zaber(Device):
    """Single-axis Zaber A-MCA / LSM050A-T4 on Elysium2.

    Startup validates the hardware and reads position; it never homes or moves.
    Motion commands return promptly so Tango can accept Stop during movement.
    """

    port = device_property(dtype=str, default_value="COM1")
    baud_rate = device_property(dtype=int, default_value=9600)
    address = device_property(dtype=int, default_value=1)
    motion_timeout_s = device_property(dtype=float, default_value=120.0)
    reconnect_interval_s = device_property(dtype=float, default_value=5.0)

    def init_device(self):
        previous_thread = getattr(self, "_motion_thread", None)
        if previous_thread is not None and previous_thread.is_alive():
            raise RuntimeError("Cannot reinitialize Zaber while it is moving")
        previous_monitor = getattr(self, "_connection_monitor", None)
        if previous_monitor is not None and not previous_monitor.stop():
            raise RuntimeError("Previous Zaber connection monitor is still running")
        previous_stage = getattr(self, "_stage", None)
        if previous_stage is not None:
            previous_stage.close()
        super().init_device()
        self._lock = threading.RLock()
        self._motion_thread = None
        self._last_error = ""
        self._motion_error = ""
        self._stage = ZaberStage(
            port=self.port, baud_rate=self.baud_rate, address=self.address
        )
        self._connection_monitor = ZaberConnectionMonitor(
            self._stage,
            self._lock,
            self._is_moving,
            self._connection_ready,
            self._connection_failed,
            interval_s=self.reconnect_interval_s,
        )
        self._connection_monitor.probe_once()
        self._connection_monitor.start()

    def _is_moving(self):
        thread = self._motion_thread
        return thread is not None and thread.is_alive()

    def _connection_ready(self, snapshot):
        if self._motion_error:
            self.set_state(DevState.FAULT)
            self.set_status("Zaber motion failed: {}; use Reconnect".format(self._motion_error))
            return
        self._last_error = ""
        self.set_state(DevState.ON if snapshot.status_code == 0 else DevState.MOVING)
        self.set_status("Zaber connected; position {:.6f} mm".format(snapshot.position_mm))

    def _connection_failed(self, exc):
        self._last_error = str(exc)
        self.set_state(DevState.FAULT)
        self.set_status(
            "Zaber disconnected; retrying every {:.1f} s: {}".format(
                self._connection_monitor.interval_s, exc
            )
        )

    def delete_device(self):
        monitor = getattr(self, "_connection_monitor", None)
        monitor_stopped = monitor is None or monitor.stop()
        stage = getattr(self, "_stage", None)
        thread = getattr(self, "_motion_thread", None)
        if stage is not None:
            if thread is not None and thread.is_alive():
                try:
                    stage.stop()
                except Exception:
                    pass
                thread.join(timeout=10)
            if monitor_stopped and (thread is None or not thread.is_alive()):
                stage.close()
        super().delete_device()

    def _snapshot(self):
        with self._lock:
            if not self._stage.connected:
                raise RuntimeError("Zaber is disconnected; automatic retry is pending")
            return self._stage.snapshot()

    def read_state(self):
        if self._is_moving():
            return DevState.MOVING
        if self._last_error or self._motion_error:
            return DevState.FAULT
        try:
            status = self._snapshot().status_code
            return DevState.ON if status == 0 else DevState.MOVING
        except Exception as exc:
            self._last_error = str(exc)
            self.set_status("Zaber status read failed: {}".format(exc))
            return DevState.FAULT

    @attribute(dtype=float, unit="mm", format="%.6f", label="Position")
    def position_mm(self):
        return self._snapshot().position_mm

    @attribute(dtype=float, unit="mm", format="%.6f", label="Minimum position")
    def minimum_mm(self):
        return self._snapshot().minimum_mm

    @attribute(dtype=float, unit="mm", format="%.6f", label="Maximum position")
    def maximum_mm(self):
        return self._snapshot().maximum_mm

    def _start_motion(self, operation, *args):
        with self._lock:
            if self._motion_thread is not None and self._motion_thread.is_alive():
                raise RuntimeError("Zaber is already moving")
            if self._last_error:
                raise RuntimeError("Zaber is in fault: {}; use Reconnect".format(self._last_error))
            snapshot = self._snapshot()
            if snapshot.status_code != 0:
                raise RuntimeError("Zaber is not idle")

            def run():
                try:
                    position_mm = operation(*args, timeout_s=self.motion_timeout_s)
                    with self._lock:
                        self._last_error = ""
                        self.set_state(DevState.ON)
                        self.set_status("Zaber stopped at {:.6f} mm".format(position_mm))
                except Exception as exc:
                    with self._lock:
                        self._last_error = str(exc)
                        self._motion_error = str(exc)
                        self.set_state(DevState.FAULT)
                        self.set_status("Zaber motion failed: {}".format(exc))

            self._motion_thread = threading.Thread(target=run, daemon=True)
            self.set_state(DevState.MOVING)
            self._motion_thread.start()

    @command(dtype_in=float, doc_in="Absolute target in millimetres")
    def MoveAbsoluteMm(self, target_mm):
        self._stage._target_native(target_mm)
        self._start_motion(self._stage.move_absolute_mm, target_mm)

    @command(dtype_in=float, doc_in="Relative displacement in millimetres")
    def MoveRelativeMm(self, displacement_mm):
        self._stage._target_native(self._snapshot().position_mm + displacement_mm)
        self._start_motion(self._stage.move_relative_mm, displacement_mm)

    @command
    def Home(self):
        self._start_motion(self._stage.home)

    @command
    def Stop(self):
        with self._lock:
            if not self._stage.connected:
                raise RuntimeError("Zaber is disconnected")
            position_mm = self._stage.stop()
            self.set_state(DevState.ON)
            self.set_status("Zaber stop requested at {:.6f} mm".format(position_mm))

    @command
    def Reconnect(self):
        with self._lock:
            if self._motion_thread is not None and self._motion_thread.is_alive():
                raise RuntimeError("Cannot reconnect while Zaber is moving")
            self._stage.close()
            try:
                snapshot = self._stage.connect()
            except Exception as exc:
                self._last_error = str(exc)
                self.set_state(DevState.FAULT)
                self.set_status("Zaber reconnect failed: {}".format(exc))
                raise
            self._last_error = ""
            self._motion_error = ""
            self.set_state(DevState.ON if snapshot.status_code == 0 else DevState.MOVING)
            self.set_status("Zaber connected; position {:.6f} mm".format(snapshot.position_mm))


if __name__ == "__main__":
    DS_Zaber.run_server()
