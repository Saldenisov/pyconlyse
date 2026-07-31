#!/usr/bin/env python

import os
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, Union

from tango import AttrWriteType, DevState, DeviceProxy, DispLevel
from tango.server import attribute, command, device_property

p = os.path.realpath(__file__)
app_folder1 = Path(p).resolve().parents[3]
sys.path.append(str(app_folder1))

try:
    from DeviceServers.base.motor import DS_MOTORIZED_MULTI_AXES
except ModuleNotFoundError:
    from base.motor import DS_MOTORIZED_MULTI_AXES


class DS_OWIS_Aggregator(DS_MOTORIZED_MULTI_AXES):
    """OWIS Aggregator DS.

    Presents a single 4-axis interface for legacy clients and routes axis calls:
    - axes 1..3 -> backend_three_axes_device (typically DS_OWIS_PS90_IP)
    - axis 4    -> backend_fourth_axis_device (typically DS_OWIS_PS90)
    """

    RULES = {
        **DS_MOTORIZED_MULTI_AXES.RULES,
        # Allow turn_on when already ON so LabVIEW pre-move calls succeed
        "turn_on": [
            DevState.OFF,
            DevState.FAULT,
            DevState.STANDBY,
            DevState.INIT,
            DevState.ON,
        ],
        "ensure_on": [
            DevState.OFF,
            DevState.FAULT,
            DevState.STANDBY,
            DevState.INIT,
            DevState.ON,
        ],
        "get_controller_status": [
            # This is a virtual routing device. OFF can mean that a reachable
            # backend controller had no PDU power, not that its Tango server
            # disappeared. Keep read-only health polling alive to reconnect
            # when that power returns; _refresh_backends never activates axes.
            DevState.OFF,
            DevState.STANDBY,
            DevState.ON,
            DevState.MOVING,
            DevState.RUNNING,
            DevState.INIT,
            DevState.FAULT,
        ],
    }

    backend_three_axes_device = device_property(
        dtype=str, default_value="manip/general/DS_OWIS_PS90_IP"
    )
    backend_fourth_axis_device = device_property(
        dtype=str, default_value="manip/general/DS_OWIS_PS90"
    )
    backend_timeout_ms = device_property(dtype=int, default_value=3000)
    reconnect_interval_seconds = device_property(dtype=float, default_value=5.0)
    recovery_connect_attempts = device_property(dtype=int, default_value=2)
    recovery_attempt_delay_seconds = device_property(dtype=float, default_value=0.5)

    _version_ = "0.1"
    _model_ = "OWIS Aggregator (3-axis TCP + 4th-axis USB/DLL)"

    @attribute(
        label="Axis 1 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos1(self):
        if 1 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[1]["position"]

    def write_pos1(self, pos):
        if 1 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 1 configured.")
            return
        self.move_axis([1, pos])

    @attribute(
        label="Axis 2 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos2(self):
        if 2 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[2]["position"]

    def write_pos2(self, pos):
        if 2 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 2 configured.")
            return
        self.move_axis([2, pos])

    @attribute(
        label="Axis 3 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos3(self):
        if 3 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[3]["position"]

    def write_pos3(self, pos):
        if 3 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 3 configured.")
            return
        self.move_axis([3, pos])

    @attribute(
        label="Axis 4 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos4(self):
        if 4 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[4]["position"]

    def write_pos4(self, pos):
        if 4 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 4 configured.")
            return
        self.move_axis([4, pos])

    def init_device(self):
        self._backend_proxies = {"three": None, "four": None}
        self._backend_alive = {"three": False, "four": False}
        self._backend_reason = {"three": "", "four": ""}
        self._next_recovery_attempt_ts = 0.0
        self._last_recovery_wait_log_ts = 0.0
        super().init_device()
        # Startup validates dependencies only.  It must not call ensure_on on
        # a backend whose physical controller may be intentionally unpowered.
        self.find_device()

    def register_variables_for_archive(self):
        from functools import partial

        super().register_variables_for_archive()
        archive_items = {}
        for axis in sorted(self._delay_lines_parameters.keys()):
            archive_items[f"position_axis_{axis}"] = (
                partial(self._get_pos_cached, axis),
                "float16",
            )
        self.archive_state.update(archive_items)

    def _get_pos_cached(self, axis: int):
        return float(self._delay_lines_parameters[axis]["position"])

    def _backend_name(self, backend_kind: str) -> str:
        if backend_kind == "three":
            return str(self.backend_three_axes_device).strip()
        if backend_kind == "four":
            return str(self.backend_fourth_axis_device).strip()
        return ""

    def _axis_route(self, axis: int) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        axis_i = int(axis)
        if axis_i not in self._delay_lines_parameters:
            return None, None, f"Axis {axis_i} is not configured on {self.device_name}."
        if axis_i in (1, 2, 3):
            return "three", axis_i, None
        if axis_i == 4:
            return "four", 4, None
        return None, None, f"Unsupported axis {axis_i}."

    def _normalize_state(self, value) -> DevState:
        if isinstance(value, DevState):
            return value
        try:
            iv = int(value)
        except Exception:
            return DevState.FAULT

        for st in (
            DevState.OFF,
            DevState.ON,
            DevState.STANDBY,
            DevState.INIT,
            DevState.MOVING,
            DevState.RUNNING,
            DevState.FAULT,
        ):
            try:
                if iv == int(st):
                    return st
            except Exception:
                pass

        # Backward compatibility with compact OWIS state mapping.
        if iv == 0:
            return DevState.OFF
        if iv == 1:
            return DevState.STANDBY
        if iv == 2:
            return DevState.INIT
        if iv == 3:
            return DevState.ON
        return DevState.FAULT

    def _command_ok(self, result) -> bool:
        if result is None:
            return True
        if isinstance(result, bool):
            return result
        if isinstance(result, (int, float)):
            return float(result) == 0.0
        txt = str(result).strip()
        return txt in ("0", "0.0", "")

    def _mark_backend_down(self, backend_kind: str, reason: str = ""):
        self._backend_alive[backend_kind] = False
        self._backend_proxies[backend_kind] = None
        previous_reason = self._backend_reason.get(backend_kind, "")
        self._backend_reason[backend_kind] = reason
        if reason and reason != previous_reason:
            self.error(
                f"{self.device_name}: backend '{backend_kind}' is down: {reason}"
            )

    def _backend_connection_detail(self, proxy: DeviceProxy) -> str:
        try:
            return str(proxy.read_attribute("controller_connection_status").value)
        except Exception:
            return ""

    def _unpowered_backend_reason(self) -> str:
        for backend_kind, reason in self._backend_reason.items():
            if "power is OFF" in reason:
                return f"backend '{backend_kind}' is intentionally OFF: {reason}"
        return ""

    def _set_off_for_unpowered_backend(self, reason: str) -> str:
        message = f"OWIS aggregator is OFF because {reason}"
        self._device_id_internal, self._uri = -1, b""
        self._next_recovery_attempt_ts = 0.0
        self.set_state(DevState.OFF)
        self.comment = message
        return message

    @staticmethod
    def _backend_is_ready(state: DevState) -> bool:
        return state in (DevState.ON, DevState.STANDBY, DevState.MOVING, DevState.RUNNING)

    def _connect_backend(
        self, backend_kind: str, *, activate: bool = False
    ) -> Tuple[bool, str]:
        name = self._backend_name(backend_kind)
        if not name:
            return False, f"empty device property for backend '{backend_kind}'"
        try:
            proxy = DeviceProxy(name)
            proxy.set_timeout_millis(int(self.backend_timeout_ms))
            proxy.ping()
            state = proxy.state()
            if activate and state != DevState.ON:
                # Activation is permitted only by an explicit aggregator
                # turn_on/ensure_on command, never by polling or startup.
                proxy.command_inout("ensure_on")
                state = proxy.state()
            if not self._backend_is_ready(state):
                detail = self._backend_connection_detail(proxy)
                if detail:
                    detail = f"; {detail}"
                return (
                    False,
                    f"{name} is {state}; controller may be unpowered or unreachable. "
                    f"No automatic recovery or axis initialisation was issued{detail}",
                )
            self._backend_proxies[backend_kind] = proxy
            self._backend_alive[backend_kind] = True
            self._backend_reason[backend_kind] = ""
            self.info(
                f"{self.device_name}: connected backend '{backend_kind}' -> {name}",
                True,
            )
            return True, "ok"
        except Exception as e:
            self._backend_proxies[backend_kind] = None
            self._backend_alive[backend_kind] = False
            return False, str(e)

    def _ping_backend(self, backend_kind: str) -> bool:
        proxy = self._backend_proxies.get(backend_kind)
        if proxy is None:
            return False
        try:
            proxy.ping()
            state = proxy.state()
            if not self._backend_is_ready(state):
                detail = self._backend_connection_detail(proxy)
                suffix = f"; {detail}" if detail else ""
                self._mark_backend_down(
                    backend_kind,
                    f"{self._backend_name(backend_kind)} is {state}; "
                    f"controller may be unpowered{suffix}",
                )
                return False
            self._backend_alive[backend_kind] = True
            self._backend_reason[backend_kind] = ""
            return True
        except Exception as e:
            self._mark_backend_down(backend_kind, str(e))
            return False

    def _refresh_backends(self, force: bool = False, *, activate: bool = False) -> bool:
        now = time.monotonic()
        if (not force) and now < self._next_recovery_attempt_ts:
            return all(self._backend_alive.values())

        # Validate current proxies first.
        for backend_kind in ("three", "four"):
            self._ping_backend(backend_kind)

        attempts = max(1, int(self.recovery_connect_attempts))
        attempt_delay = max(0.1, float(self.recovery_attempt_delay_seconds))
        for backend_kind in ("three", "four"):
            if self._backend_alive.get(backend_kind):
                continue
            ok = False
            last_comment = ""
            for attempt in range(1, attempts + 1):
                ok, last_comment = self._connect_backend(backend_kind, activate=activate)
                if ok:
                    break
                if attempt < attempts:
                    time.sleep(attempt_delay)
            if not ok and last_comment != self._backend_reason.get(backend_kind, ""):
                self._backend_reason[backend_kind] = last_comment
                self.error(
                    f"{self.device_name}: backend '{backend_kind}' connect failed: "
                    f"{last_comment}"
                )

        all_ok = all(self._backend_alive.values())
        if all_ok:
            self._next_recovery_attempt_ts = 0.0
            self._last_recovery_wait_log_ts = 0.0
            return True

        self._next_recovery_attempt_ts = now + max(
            1.0, float(self.reconnect_interval_seconds)
        )
        return False

    def _resolve_axis_proxy(self, axis: int) -> Tuple[Optional[DeviceProxy], Optional[int], Optional[str]]:
        backend_kind, backend_axis, route_error = self._axis_route(axis)
        if route_error:
            return None, None, route_error

        proxy = self._backend_proxies.get(backend_kind)
        if proxy is not None and self._ping_backend(backend_kind):
            return proxy, backend_axis, None

        self._refresh_backends(force=True)
        proxy = self._backend_proxies.get(backend_kind)
        if proxy is None:
            return None, None, (
                f"Backend '{backend_kind}' for axis {axis} is unavailable."
            )
        return proxy, backend_axis, None

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        if state_ok != 1:
            self._device_id_internal, self._uri = -1, b""
            self.set_state(DevState.FAULT)
            return

        if self._refresh_backends(force=True):
            self._device_id_internal, self._uri = 1, b"OWIS Aggregator"
            self.set_state(DevState.STANDBY)
        else:
            reason = self._unpowered_backend_reason()
            if reason:
                self._set_off_for_unpowered_backend(reason)
            else:
                self._device_id_internal, self._uri = -1, b""
                self.set_state(DevState.FAULT)

    def turn_on_local(self) -> Union[int, str]:
        # Idempotent: if already ON just return success (LabVIEW calls turn_on before moves)
        if self.get_state() == DevState.ON:
            return 0

        if not self._refresh_backends(force=True, activate=True):
            self.set_state(DevState.FAULT)
            return (
                f"Could NOT turn on {self.device_name}: at least one backend is down."
            )

        self._device_id_internal, self._uri = 1, b"OWIS Aggregator"
        for axis in sorted(self._delay_lines_parameters.keys()):
            self.get_status_axis_local(axis)
            self.read_position_axis_local(axis)
        self.set_state(DevState.ON)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self._backend_proxies = {"three": None, "four": None}
        self._backend_alive = {"three": False, "four": False}
        self._device_id_internal, self._uri = -1, b""
        self.set_state(DevState.OFF)
        return 0

    @command
    def ensure_on(self):
        state_ok = self.check_func_allowance(self.ensure_on)
        if state_ok == 1:
            if self.get_state() != DevState.ON:
                self.turn_on()
            else:
                self.info(f"{self.device_name} already ON; ensure_on is a no-op.", True)

    def get_controller_status_local(self) -> Union[int, str]:
        now = time.monotonic()
        if not self._refresh_backends(force=False):
            reason = self._unpowered_backend_reason()
            if reason:
                return self._set_off_for_unpowered_backend(reason)
            self.set_state(DevState.FAULT)
            if now - self._last_recovery_wait_log_ts >= 1.0:
                remain = max(0.0, self._next_recovery_attempt_ts - now)
                self.info(
                    f"{self.device_name}: waiting {remain:.1f}s before next reconnect attempt.",
                    True,
                )
                self._last_recovery_wait_log_ts = now
            missing = [
                kind for kind, alive in self._backend_alive.items() if not bool(alive)
            ]
            return (
                f"Backends unavailable ({', '.join(missing)}). "
                f"Will retry in {max(0.0, self._next_recovery_attempt_ts - now):.1f}s."
            )

        any_moving = False
        for axis in sorted(self._delay_lines_parameters.keys()):
            status_res = self.get_status_axis_local(axis)
            if status_res != 0:
                return status_res
            state = self._delay_lines_parameters[axis]["state"]
            if state == DevState.MOVING:
                any_moving = True
            pos_res = self.read_position_axis_local(axis)
            if pos_res != 0:
                return pos_res

        self.set_state(DevState.MOVING if any_moving else DevState.ON)
        return 0

    def init_axis_local(self, axis: int) -> Union[int, str]:
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            res = proxy.command_inout("init_axis", int(backend_axis))
            if not self._command_ok(res):
                return f"backend init_axis failed: {res}"
            return 0
        except Exception as e:
            return f"backend init_axis exception: {e}"

    def get_status_axis_local(self, axis: int) -> Union[int, str]:
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            self._delay_lines_parameters[axis]["state"] = DevState.FAULT
            return error
        try:
            state_raw = proxy.command_inout("get_status_axis", int(backend_axis))
            state = self._normalize_state(state_raw)
            self._delay_lines_parameters[axis]["state"] = state
            return 0
        except Exception as e:
            self._delay_lines_parameters[axis]["state"] = DevState.FAULT
            return f"backend get_status_axis exception: {e}"

    def read_position_axis_local(self, axis: int) -> Union[int, str]:
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            pos = float(proxy.command_inout("read_position_axis", int(backend_axis)))
            self._delay_lines_parameters[axis]["position"] = pos
            return 0
        except Exception as e:
            return f"backend read_position_axis exception: {e}"

    def set_param_axis_local(self, axis: int) -> Union[int, str]:
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            res = proxy.command_inout("set_param_axis", int(backend_axis))
            if not self._command_ok(res):
                return f"backend set_param_axis failed: {res}"
            return 0
        except Exception as e:
            return f"backend set_param_axis exception: {e}"

    def turn_on_axis_local(self, axis: int) -> Union[int, str]:
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            res = proxy.command_inout("turn_on_axis", int(backend_axis))
            if not self._command_ok(res):
                return f"backend turn_on_axis failed: {res}"
            self._delay_lines_parameters[axis]["state"] = DevState.ON
            return 0
        except Exception as e:
            return f"backend turn_on_axis exception: {e}"

    def turn_off_axis_local(self, axis: int) -> Union[int, str]:
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            res = proxy.command_inout("turn_off_axis", int(backend_axis))
            if not self._command_ok(res):
                return f"backend turn_off_axis failed: {res}"
            self._delay_lines_parameters[axis]["state"] = DevState.OFF
            return 0
        except Exception as e:
            return f"backend turn_off_axis exception: {e}"

    def move_axis_local(self, args) -> Union[int, str]:
        axis = int(args[0])
        pos = float(args[1])
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            res = proxy.command_inout("move_axis", [float(backend_axis), float(pos)])
            if not self._command_ok(res):
                return f"backend move_axis failed: {res}"
            self._delay_lines_parameters[axis]["state"] = DevState.MOVING
            return 0
        except Exception as e:
            return f"backend move_axis exception: {e}"

    def stop_axis_local(self, axis: int) -> Union[int, str]:
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            res = proxy.command_inout("stop_axis", int(backend_axis))
            if not self._command_ok(res):
                return f"backend stop_axis failed: {res}"
            self._delay_lines_parameters[axis]["state"] = DevState.ON
            return 0
        except Exception as e:
            return f"backend stop_axis exception: {e}"

    def define_position_axis_local(self, args) -> Union[int, str]:
        axis = int(args[0])
        pos = float(args[1])
        proxy, backend_axis, error = self._resolve_axis_proxy(axis)
        if error:
            return error
        try:
            res = proxy.command_inout(
                "define_position_axis", [float(backend_axis), float(pos)]
            )
            if not self._command_ok(res):
                return f"backend define_position_axis failed: {res}"
            self._delay_lines_parameters[axis]["position"] = pos
            return 0
        except Exception as e:
            return f"backend define_position_axis exception: {e}"


def main(device_name=None):
    if device_name:
        sys.argv.append(device_name)
    DS_OWIS_Aggregator.run_server()


if __name__ == "__main__":
    DS_OWIS_Aggregator.run_server()
