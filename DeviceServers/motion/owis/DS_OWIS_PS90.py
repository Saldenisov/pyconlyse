#!/usr/bin/env python


import ast
import os
import sys
from pathlib import Path

p = os.path.realpath(__file__)

app_folder = Path(p).resolve().parents[0]
app_folder1 = Path(p).resolve().parents[3]
sys.path.append(str(app_folder1))

import ctypes
from threading import Thread
from time import sleep
from typing import Optional, Tuple, Union

from tango import AttrWriteType, DevState, DispLevel
from tango.server import attribute, device_property, command

from utilities.tools.decorators import development_mode

dev_mode = False
# Strange delay for ps90.dll
time_ps_delay = 0.005

try:
    from DeviceServers.base.motor import DS_MOTORIZED_MULTI_AXES
except ModuleNotFoundError:
    from base.motor import DS_MOTORIZED_MULTI_AXES


class _PS90TcpAdapter:
    """Minimal DLL-like adapter for OWIS PS90 direct TCP access."""

    def __init__(
        self,
        host: str,
        port: int = 8777,
        timeout: float = 5.0,
        command_delay: float = 0.005,
        velocity_scale: float = 16.0,
        velocity_scale_map: Optional[dict[int, float]] = None,
    ):
        from owis_ps90_tcp import OwisPS90TCP

        self._controller = OwisPS90TCP(ip=host, port=port, timeout=timeout)
        self._controller.command_delay = max(0.0, float(command_delay))
        self._last_error = 0
        self._target_modes = {}
        self._stage_attrs = {}
        self._limits = {}
        self._microsteps = {}
        self._velocity_scale = max(0.01, float(velocity_scale))
        self._velocity_scale_map = {}
        if isinstance(velocity_scale_map, dict):
            for axis, scale in velocity_scale_map.items():
                try:
                    axis_i = int(axis)
                    scale_f = float(scale)
                except Exception:
                    continue
                if axis_i > 0 and scale_f > 0:
                    self._velocity_scale_map[axis_i] = scale_f

    def _velocity_scale_for_axis(self, axis: int) -> float:
        return float(self._velocity_scale_map.get(int(axis), self._velocity_scale))

    @staticmethod
    def _to_int(value) -> int:
        if hasattr(value, "value"):
            value = value.value
        return int(value)

    @staticmethod
    def _to_float(value) -> float:
        if hasattr(value, "value"):
            value = value.value
        return float(value)

    def _ok(self) -> int:
        self._last_error = 0
        return 0

    def _fail(self, code: int = -2) -> int:
        self._last_error = int(code)
        return int(code)

    def _ensure_connected(self) -> None:
        if self._controller.connected:
            return
        if not self._controller.connect():
            raise ConnectionError(
                f"Cannot connect to OWIS controller at {self._controller.ip}:{self._controller.port}"
            )

    def _axis_params(self, axis: int) -> tuple[float, float, float]:
        pitch, inc_rev, gear_ratio = self._stage_attrs.get(axis, (1.0, 200.0, 1.0))
        pitch = float(pitch) if pitch else 1.0
        inc_rev = float(inc_rev) if inc_rev else 200.0
        gear_ratio = float(gear_ratio) if gear_ratio else 1.0
        return pitch, inc_rev, gear_ratio

    def _microstep_factor(self, axis: int) -> float:
        cached = self._microsteps.get(axis)
        if cached and cached > 0:
            return float(cached)
        try:
            resp = self._controller.query(f"?MCSTP{axis}")
            val = int(str(resp).strip())
            if val > 0:
                self._microsteps[axis] = val
                return float(val)
        except Exception:
            pass
        self._microsteps[axis] = 1
        return 1.0

    def _units_per_mm(self, axis: int) -> float:
        pitch, inc_rev, gear_ratio = self._axis_params(axis)
        microstep = self._microstep_factor(axis)
        denom = pitch if pitch else 1.0
        units = (inc_rev * gear_ratio * microstep) / denom
        return units if units else 1.0

    def _mm_to_counts(self, axis: int, mm: float) -> int:
        units = self._units_per_mm(axis)
        return int(round(mm * units))

    def _counts_to_mm(self, axis: int, counts: float) -> float:
        units = self._units_per_mm(axis)
        return float(counts) / units if units else float(counts)

    def _get_current_level(self, axis: int) -> Optional[int]:
        """Return current level from controller (0=low, 1=high), or None if unknown."""
        try:
            resp = self._controller.query(f"?AMPSHNT{axis}")
            level = int(str(resp).strip())
            return level if level in (0, 1) else None
        except Exception:
            return None

    def _set_current_level(self, axis: int, level: int) -> None:
        self._controller.send_command(f"AMPSHNT{axis}={int(level)}", expect_response=False)

    def _normalize_current_to_percent(self, axis: int, value) -> int:
        """Accept either percent (0-100) or amperes (~0-6A) and return controller percent."""
        v = abs(self._to_float(value))
        # Legacy/expected controller format
        if v > 10.0:
            return max(0, min(100, int(round(v))))

        # Ampere mode: convert using current level.
        level = self._get_current_level(axis)
        if level is None:
            # Fallback when level cannot be queried: treat as legacy percent-like value.
            return max(0, min(100, int(round(v))))

        # If requested current exceeds low range, switch to high range automatically.
        if v > 2.4 and level == 0:
            self._set_current_level(axis, 1)
            level = 1

        # Conversion basis from SDK docs:
        # low level max = 2.4 A (100%), high level max = 5.45 A (capped at 66% ~= 3.6 A).
        if level == 0:
            pct = int(round((v / 2.4) * 100.0))
            return max(0, min(100, pct))

        pct = int(round((v / 5.45) * 100.0))
        return max(0, min(66, pct))

    # ---------- DLL-like methods ----------
    def PS90_Connect(self, *_args):
        try:
            self._ensure_connected()
            return self._ok()
        except Exception:
            # DLL convention: positive connection errors (caller flips sign)
            self._last_error = -5
            return 5

    def PS90_Disconnect(self, *_args):
        try:
            self._controller.disconnect()
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_GetReadError(self, *_args):
        return int(self._last_error)

    def PS90_GetSerNumber(self, _control_unit, buf, length):
        try:
            self._ensure_connected()
            serial = (self._controller.get_serial_number() or "").strip()
            if not serial:
                serial = "0"
            max_len = max(0, self._to_int(length) - 1)
            encoded = serial.encode("utf-8", errors="ignore")[:max_len]
            buf.value = encoded
            self._ok()
            return len(encoded)
        except Exception:
            try:
                buf.value = b""
            except Exception:
                pass
            return self._fail(-1)

    def PS90_GetAxisState(self, _control_unit, axis):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            state = int(self._controller.get_axis_state(axis_i))
            if state < 0:
                return self._fail(-2)
            self._ok()
            return state
        except Exception:
            return self._fail(-2)

    def PS90_GetPosition(self, _control_unit, axis):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            counts = self._controller.get_position(axis_i)
            mm = self._counts_to_mm(axis_i, counts)
            pitch, _inc_rev, _ratio = self._axis_params(axis_i)
            value = int(round((mm * 10000.0) / pitch))
            self._ok()
            return value
        except Exception:
            return self._fail(-2)

    def PS90_GetTargetEx(self, _control_unit, axis):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            counts = self._controller.get_target(axis_i)
            mm = self._counts_to_mm(axis_i, counts)
            value = int(round(mm * 10000.0))
            self._ok()
            return value
        except Exception:
            return self._fail(-2)

    def PS90_GetTargetMode(self, _control_unit, axis):
        try:
            axis_i = self._to_int(axis)
            self._ok()
            return int(self._target_modes.get(axis_i, 1))
        except Exception:
            return self._fail(-1)

    def PS90_GoTarget(self, _control_unit, axis):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            self._controller.clear_error()
            ok = self._controller.go_target(axis_i)
            if not ok:
                return self._fail(-4)
            err = self._controller.get_error()
            if err == -1:
                return self._fail(-2)
            if err != 0:
                return self._fail(-4)
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_MotorInit(self, _control_unit, axis):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            self._controller.send_command(f"AXIS{axis_i}=1", expect_response=False)
            ok = self._controller.motor_init(axis_i)
            return self._ok() if ok else self._fail(-4)
        except Exception:
            return self._fail(-2)

    def PS90_MotorOn(self, _control_unit, axis):
        try:
            self._ensure_connected()
            ok = self._controller.motor_on(self._to_int(axis))
            return self._ok() if ok else self._fail(-4)
        except Exception:
            return self._fail(-2)

    def PS90_MotorOff(self, _control_unit, axis):
        try:
            self._ensure_connected()
            ok = self._controller.motor_off(self._to_int(axis))
            return self._ok() if ok else self._fail(-4)
        except Exception:
            return self._fail(-2)

    def PS90_Stop(self, _control_unit, axis):
        try:
            self._ensure_connected()
            self._controller.stop(self._to_int(axis))
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_SetLimitMinEx(self, _control_unit, axis, value):
        try:
            axis_i = self._to_int(axis)
            self._limits.setdefault(axis_i, {})["min"] = self._to_float(value)
            return self._ok()
        except Exception:
            return self._fail(-1)

    def PS90_SetLimitMaxEx(self, _control_unit, axis, value):
        try:
            axis_i = self._to_int(axis)
            self._limits.setdefault(axis_i, {})["max"] = self._to_float(value)
            return self._ok()
        except Exception:
            return self._fail(-1)

    def PS90_SetPositionEx(self, _control_unit, axis, pos):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            pos_mm = self._to_float(pos)
            counts = self._mm_to_counts(axis_i, pos_mm)
            self._controller.set_position(axis_i, counts)
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_SetPosMode(self, *_args):
        return self._ok()

    def PS90_SetPosFEx(self, _control_unit, axis, value):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            speed_mm_s = self._to_float(value)
            axis_scale = self._velocity_scale_for_axis(axis_i)
            # On the tested PS90 TCP firmware, PVEL behaves as if values are
            # expected in ~1/16 increments/s units. Keep the factor configurable.
            speed_counts = max(
                1,
                int(
                    round(
                        abs(
                            self._mm_to_counts(axis_i, speed_mm_s)
                            * axis_scale
                        )
                    )
                ),
            )
            self._controller.set_velocity(axis_i, speed_counts)
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_SetStageAttributes(self, _control_unit, axis, pitch, inc_rev, gear_ratio):
        try:
            axis_i = self._to_int(axis)
            self._stage_attrs[axis_i] = (
                self._to_float(pitch),
                self._to_float(inc_rev),
                self._to_float(gear_ratio),
            )
            return self._ok()
        except Exception:
            return self._fail(-1)

    def PS90_SetTargetMode(self, _control_unit, axis, mode):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            mode_i = self._to_int(mode)
            self._target_modes[axis_i] = mode_i
            self._controller.send_command(
                f"ABSOL{axis_i}={mode_i}", expect_response=False
            )
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_SetTarget(self, _control_unit, axis, value):
        try:
            self._ensure_connected()
            self._controller.set_target(self._to_int(axis), self._to_int(value))
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_SetTargetEx(self, _control_unit, axis, value):
        try:
            self._ensure_connected()
            axis_i = self._to_int(axis)
            target_mm = self._to_float(value)
            counts = self._mm_to_counts(axis_i, target_mm)
            self._controller.set_target(axis_i, counts)
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_SetDriveCurrent(self, *_args):
        try:
            self._ensure_connected()
            _control_unit, axis, value = _args[:3]
            axis_i = self._to_int(axis)
            pct = self._normalize_current_to_percent(axis_i, value)
            self._controller.send_command(f"DRICUR{axis_i}={pct}", expect_response=False)
            return self._ok()
        except Exception:
            return self._fail(-2)

    def PS90_SetHoldCurrent(self, *_args):
        try:
            self._ensure_connected()
            _control_unit, axis, value = _args[:3]
            axis_i = self._to_int(axis)
            pct = self._normalize_current_to_percent(axis_i, value)
            self._controller.send_command(f"HOLCUR{axis_i}={pct}", expect_response=False)
            return self._ok()
        except Exception:
            return self._fail(-2)


class DS_OWIS_PS90(DS_MOTORIZED_MULTI_AXES):
    """ "
    Device Server (Tango) which controls the OWIS delay lines using ps90.dll
    """

    RULES = {
        **DS_MOTORIZED_MULTI_AXES.RULES,
        # Idempotent bring-up command: allowed even when already ON
        "ensure_on": [
            DevState.OFF,
            DevState.FAULT,
            DevState.STANDBY,
            DevState.INIT,
            DevState.ON,
        ],
    }

    baudrate = device_property(dtype=int, default_value=9600)
    com_port = device_property(dtype=int, default_value=4)
    interface = device_property(dtype=int, default_value=0)
    control_unit_id = device_property(dtype=int, default_value=1)
    serial_number = device_property(dtype=int)
    transport = device_property(dtype=str, default_value="tcp")
    controller_ip = device_property(dtype=str, default_value="")
    controller_port = device_property(dtype=int, default_value=8777)
    tcp_timeout = device_property(dtype=float, default_value=5.0)
    tcp_command_delay = device_property(dtype=float, default_value=0.005)
    tcp_velocity_scale = device_property(dtype=float, default_value=16.0)
    tcp_velocity_scale_map = device_property(dtype=str, default_value="")

    _version_ = "0.3"
    _model_ = "OWIS controller PS90 multi-axes 4 axes"
    recovery_fault_threshold = 3

    @attribute(
        label="Axis 1 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos1(self):
        return self._delay_lines_parameters[1]["position"]

    def write_pos1(self, pos):
        self.move_axis([1, pos])

    @attribute(
        label="Axis 2 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos2(self):
        return self._delay_lines_parameters[2]["position"]

    def write_pos2(self, pos):
        self.move_axis([2, pos])

    @attribute(
        label="Axis 3 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos3(self):
        return self._delay_lines_parameters[3]["position"]

    def write_pos3(self, pos):
        self.move_axis([3, pos])

    @attribute(
        label="Axis 4 pos",
        dtype=float,
        display_level=DispLevel.OPERATOR,
        access=AttrWriteType.READ_WRITE,
        polling_period=DS_MOTORIZED_MULTI_AXES.polling,
    )
    def pos4(self):
        # Some installations use only 3 axes for this device instance.
        if 4 not in self._delay_lines_parameters:
            return float("nan")
        return self._delay_lines_parameters[4]["position"]

    def write_pos4(self, pos):
        if 4 not in self._delay_lines_parameters:
            self.error(f"{self.device_name} has no axis 4 configured.")
            return
        self.move_axis([4, pos])

    def get_pos(self, axis):
        return self._delay_lines_parameters[axis]["position"]

    def init_device(self):
        super().init_device()
        self.follow = {}
        self.turn_on()

    def register_variables_for_archive(self):
        from functools import partial

        super().register_variables_for_archive()
        archive_items = {}
        for axis in sorted(self._delay_lines_parameters.keys()):
            archive_items[f"position_axis_{axis}"] = (partial(self.get_pos, axis), "float16")
        self.archive_state.update(archive_items)

    def find_device(self):
        state_ok = self.check_func_allowance(self.find_device)
        argreturn = -1, b""
        if state_ok:
            transport = str(getattr(self, "transport", "tcp")).strip().lower()
            ip = str(getattr(self, "controller_ip", "")).strip()
            port = int(getattr(self, "controller_port", 8777))
            tcp_aliases = {"tcp", "ip", "ethernet", "socket"}
            dll_aliases = {"dll", "windll"}

            if transport in tcp_aliases:
                use_tcp_backend = True
            elif transport in dll_aliases:
                use_tcp_backend = False
            else:
                use_tcp_backend = bool(ip)
                fallback = "TCP" if use_tcp_backend else "DLL"
                self.info(
                    f"Unknown transport '{transport}', fallback to {fallback}.", True
                )

            if not hasattr(ctypes, "WinDLL") and not use_tcp_backend:
                if ip:
                    self.info(
                        "ctypes.WinDLL is unavailable on this platform; forcing TCP backend.",
                        True,
                    )
                    use_tcp_backend = True
                else:
                    self.error(
                        "DLL transport requested on non-Windows platform without controller_ip."
                    )
                    self.set_state(DevState.FAULT)
                    self._device_id_internal, self._uri = -1, b""
                    return

            if use_tcp_backend:
                if not ip:
                    self.error(
                        "OWIS TCP backend requires 'controller_ip' device property."
                    )
                    self.set_state(DevState.FAULT)
                    self._device_id_internal, self._uri = -1, b""
                    return
                timeout = float(getattr(self, "tcp_timeout", 5.0))
                command_delay = float(getattr(self, "tcp_command_delay", 0.005))
                velocity_scale = float(getattr(self, "tcp_velocity_scale", 16.0))
                velocity_scale_map_raw = str(
                    getattr(self, "tcp_velocity_scale_map", "")
                ).strip()
                velocity_scale_map = {}
                if velocity_scale_map_raw:
                    try:
                        parsed = ast.literal_eval(velocity_scale_map_raw)
                        if isinstance(parsed, dict):
                            for axis, scale in parsed.items():
                                axis_i = int(axis)
                                scale_f = float(scale)
                                if axis_i > 0 and scale_f > 0:
                                    velocity_scale_map[axis_i] = scale_f
                        else:
                            self.error(
                                "tcp_velocity_scale_map must be a dict, "
                                f"got {type(parsed).__name__}"
                            )
                    except Exception as e:
                        self.error(
                            f"Invalid tcp_velocity_scale_map '{velocity_scale_map_raw}': {e}"
                        )
                self.info(
                    f"Using OWIS TCP backend: {ip}:{port} "
                    f"(timeout={timeout}s, command_delay={command_delay}s, "
                    f"velocity_scale={velocity_scale})",
                    True,
                )
                if velocity_scale_map:
                    self.info(
                        f"TCP velocity scale overrides by axis: {velocity_scale_map}",
                        True,
                    )
                self.lib = _PS90TcpAdapter(
                    ip,
                    port=port,
                    timeout=timeout,
                    command_delay=command_delay,
                    velocity_scale=velocity_scale,
                    velocity_scale_map=velocity_scale_map,
                )
                # TCP adapter: connect via PS90_Connect (supported by _PS90TcpAdapter)
                res, comments = self._connect_ps90(
                    self.control_unit_id,
                    interface=self.interface,
                    port=self.com_port,
                    baudrate=self.baudrate,
                )
            else:
                # Resolve DLL path robustly: prefer valid device property, else fall back to local drivers dir
                dll_candidate = None
                try:
                    cfg_path = str(self.dll_path).strip()
                except Exception:
                    cfg_path = ""
                if cfg_path:
                    p = Path(cfg_path)
                    if p.exists():
                        dll_candidate = p

                if dll_candidate is None:
                    drivers_dir = Path(__file__).resolve().parent / "drivers"
                    # Prefer arch-specific DLL name; fall back to generic
                    arch_name = "ps90_64.dll" if sys.maxsize > 2**32 else "ps90_32.dll"
                    for name in (arch_name, "ps90.dll"):
                        cand = drivers_dir / name
                        if cand.exists():
                            dll_candidate = cand
                            break

                if dll_candidate is None:
                    self.error(
                        f"OWIS DLL not found. Checked property path '{cfg_path}' and drivers dir '{drivers_dir}'."
                    )
                    self.set_state(DevState.FAULT)
                    self._device_id_internal, self._uri = -1, b""
                    return

                # Ensure Windows can locate any adjacent DLL dependencies (Python 3.8+)
                try:
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(str(dll_candidate.parent))
                except Exception as e:
                    self.info(f"add_dll_directory failed: {e}", True)

                self.dll_path = dll_candidate
                self.info(f"Using OWIS DLL: {self.dll_path}", True)
                self.lib = ctypes.WinDLL(str(self.dll_path))

                # DLL: use Ethernet (PS90_SimpleConnect) if controller_ip is set, else COM/USB
                _eth_ip = str(getattr(self, "controller_ip", "")).strip()
                if _eth_ip:
                    _eth_port = int(getattr(self, "controller_port", 8777))
                    self.info(
                        f"Using OWIS DLL over Ethernet: {_eth_ip}:{_eth_port}", True
                    )
                    res, comments = self._connect_simple_ps90(
                        self.control_unit_id,
                        ser_num=f"net:{_eth_ip}:{_eth_port}".encode("ascii"),
                    )
                else:
                    res, comments = self._connect_ps90(
                        self.control_unit_id,
                        interface=self.interface,
                        port=self.com_port,
                        baudrate=self.baudrate,
                    )
            if res:
                self.set_state(DevState.STANDBY)
                argreturn = self.control_unit_id, f"{self.serial_number}".encode()
            else:
                self.set_state(DevState.FAULT)
        self._device_id_internal, self._uri = argreturn

    def turn_on_local(self) -> Union[int, str]:
        if self._device_id_internal == -1:
            self.info(f"Searching for device: {self.device_id}", True)
            self.find_device()

        if self._device_id_internal == -1:
            self.set_state(DevState.FAULT)
            return f"Could NOT turn on {self.device_name}: Device could not be found."

        self.set_state(DevState.ON)

        for axis in self._delay_lines_parameters.keys():
            self.init_axis(axis)
        return 0

    def turn_off_local(self) -> Union[int, str]:
        self._device_id_internal = -1
        res, comments = self._disconnect_ps90(self.control_unit_id)
        if res:
            self.set_state(DevState.OFF)
            return 0
        self.set_state(DevState.FAULT)
        return comments

    def _attempt_recover_connection(self) -> bool:
        self.info(f"Attempting OWIS recovery for {self.device_name}.", True)
        self.set_state(DevState.FAULT)
        self._device_id_internal = -1
        self._uri = b""
        try:
            res = self.turn_on_local()
        except Exception as e:
            self.error(f"Recovery attempt failed for {self.device_name}: {e}")
            return False

        if res == 0:
            self._status_check_fault = 0
            self.info(f"OWIS recovery succeeded for {self.device_name}.", True)
            return True

        self.error(f"OWIS recovery failed for {self.device_name}: {res}")
        return False

    def is_ensure_on_allowed(self):
        return self.get_state() in self.RULES.get("ensure_on", [])

    @command
    def ensure_on(self):
        """Ensure the controller is ON (idempotent).

        If already ON, this is a no-op. Otherwise, delegates to turn_on().
        """
        state_ok = self.check_func_allowance(self.ensure_on)
        if state_ok == 1:
            if self.get_state() != DevState.ON:
                self.turn_on()
            else:
                self.info(f"{self.device_name} already ON; ensure_on is a no-op.", True)

    def get_controller_status_local(self) -> Union[int, str]:
        ser_num = self._get_serial_number_ps90(self.control_unit_id)
        if ser_num < 0:
            self._status_check_fault += 1
            if self._status_check_fault > self.recovery_fault_threshold:
                self._status_check_fault = 0
                if self._attempt_recover_connection():
                    return 0
            self.set_state(DevState.FAULT)
            return "Connection with PS90 is lost"
        self._status_check_fault = 0
        for axis in self._delay_lines_parameters.keys():
            self.get_status_axis_local(axis)
            self.read_position_axis_local(axis)
        return 0

    def init_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._motor_init_ps90(self.control_unit_id, axis)
        if not res:
            result = f"ERROR: Device {self.device_name} motor_init for axis {axis} func did NOT work: {comments}."
            self.error(result)
            self._delay_lines_parameters[axis]["state"] = DevState.FAULT
        else:
            res, comments = self._set_target_mode_ps90(self.control_unit_id, axis, 1)
            if not res:
                result = (
                    f"ERROR: Device {self.device_name} set_target_mode to ABS for axis {axis} "
                    f"did NOT work {comments}."
                )
                self.error(result)
            else:
                self._delay_lines_parameters[axis]["state"] = DevState.INIT
                res = self.set_param_axis(axis)
                if res == "0":
                    result = 0
                else:
                    result = res
            self._motor_off_ps90(self.control_unit_id, axis)
        return result

    def get_status_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._get_axis_state_ps90(self.control_unit_id, axis)
        if res == 0:
            result = DevState.OFF
        elif res == 1:
            result = DevState.STANDBY
        elif res == 2:
            result = DevState.INIT
        elif res == 3:
            result = DevState.ON
        else:
            error = f"ERROR: {comments}"
            self.error(error)
            result = DevState.FAULT
        self._delay_lines_parameters[axis]["state"] = result
        return 0

    def read_position_axis_local(self, axis: int) -> Union[int, str]:
        res, com = self._get_pos_ex_ps90(self.control_unit_id, axis)
        if not com:
            self._delay_lines_parameters[axis]["position"] = res
            self.info(f"Reading position localy for axis {axis}: {res}", False)
            result = 0
        else:
            result = f"Device {self.device_name} reading position of axis {axis} was not successful."
            self.error(result)
        return result

    def set_param_axis_local(self, axis: int) -> Union[int, str]:
        param = self._delay_lines_parameters[axis]
        pitch = param["pitch"]
        revolution = param["revolution"]
        gear_ratio = param["gear_ratio"]
        speed = param["speed"]
        limit_min = param["limit_min"]
        limit_max = param["limit_max"]
        drive_current = param["drive_current"]
        hold_current = param["hold_current"]

        res1, com1 = self._set_stage_attributes_ps90(
            self.control_unit_id, axis, pitch, revolution, gear_ratio
        )
        res2, com2 = self._set_pos_velocity_ps90(self.control_unit_id, axis, speed)
        res3, com3 = self._set_limit_min_ps90(self.control_unit_id, axis, limit_min)
        res4, com4 = self._set_limit_max_ps90(self.control_unit_id, axis, limit_max)
        res5, com5 = self._set_drive_current_ex_ps90(
            self.control_unit_id, axis, drive_current
        )
        res6, com6 = self._set_hold_current_ex_ps90(
            self.control_unit_id, axis, hold_current
        )

        if all([res1, res2, res3, res4, res5, res6]):
            result = 0
        else:
            result = f"ERROR: {com1}:{com2}:{com3}:{com4}:{com5}:{com6}"
            self.error(result)
        return result

    def turn_on_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._motor_on_ps90(self.control_unit_id, axis)
        if not res:
            result = f"ERROR: Device {self.device_name} turn_on_axis for axis {axis} func did NOT work {comments}."
            self.error(result)
        else:
            self._delay_lines_parameters[axis]["state"] = DevState.ON
            result = 0
        return result

    def turn_off_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._motor_off_ps90(self.control_unit_id, axis)
        if not res:
            # OWIS may report "axis is in wrong state" when it's already effectively off.
            if isinstance(comments, str) and "wrong state" in comments.lower():
                self._delay_lines_parameters[axis]["state"] = DevState.OFF
                result = 0
            else:
                result = f"ERROR: Device {self.device_name} turn_off_axis for axis {axis} func did NOT work {comments}."
                self.error(result)
        else:
            self._delay_lines_parameters[axis]["state"] = DevState.OFF
            result = 0
        return result

    def move_axis_local(self, args) -> Union[int, str]:
        axis = int(args[0])
        pos: float = args[1]

        if self._delay_lines_parameters[axis]["state"] != DevState.ON:
            turn_on_res = self.turn_on_axis(axis)
            sleep(0.05)
            if turn_on_res != "0":
                return (
                    f"ERROR: Device {self.device_name} axis {axis} could not be turned on: "
                    f"{turn_on_res}"
                )

        res, comments = self._set_target_ex_ps90(self.control_unit_id, axis, pos)
        if not res:
            result = (
                f"ERROR: Device {self.device_name} set_target_ex to {pos} for axis {axis} "
                f"did NOT work {comments}."
            )
            self.error(result)
        else:
            res, comments = self._go_target_ps90(self.control_unit_id, axis)

            if res:
                self.info(
                    f"Device {self.device_name} axis {axis} started moving to {pos}.",
                    True,
                )
                if axis not in self.follow:
                    self.follow[axis] = Thread(
                        target=self.follow_after_moving, args=(axis,), daemon=True
                    )
                    self.follow[axis].start()
                result = 0
            else:
                self.turn_off_axis(axis)
                result = f"ERROR: Device {self.device_name} axis {axis} did NOT start moving: {comments}."
                self.error(result)
        return result

    def follow_after_moving(self, axis, wait=1.0, stable_needed=5, eps=1e-4, max_wait_s=180.0):
        stable = 0
        checks = 0
        max_checks = max(1, int(max_wait_s / wait))
        try:
            while checks < max_checks:
                if axis not in self._delay_lines_parameters:
                    break
                pos_prev = float(self._delay_lines_parameters[axis]["position"])
                sleep(wait)
                pos_now = float(self._delay_lines_parameters[axis]["position"])
                if abs(pos_now - pos_prev) <= eps:
                    stable += 1
                    if stable >= stable_needed:
                        self.turn_off_axis(axis)
                        break
                else:
                    stable = 0
                checks += 1
            if checks >= max_checks:
                self.info(
                    f"follow_after_moving timeout for axis {axis}, leaving motor state unchanged.",
                    True,
                )
        finally:
            self.follow.pop(axis, None)

    def stop_axis_local(self, axis: int) -> Union[int, str]:
        res, comments = self._stop_axis_ps90(self.control_unit_id, axis)
        if not res:
            result = (
                f"ERROR: Device {self.device_name} stop_axis axis {axis} "
                f"did NOT work {comments}."
            )
            self.error(result)
        else:
            result = 0
        return result

    def define_position_axis_local(self, args) -> Union[int, str]:
        axis = int(args[0])
        pos = float(args[1])
        res, comments = self._set_position_ex_ps90(self.control_unit_id, axis, pos)
        if not res:
            result = (
                f"ERROR: Device {self.device_name} define_pos axis {axis} "
                f"did NOT work {comments}."
            )
            self.error(result)
        else:
            result = 0
        return result

    # Hardware controller functions
    # Be aware that OWIS PS90 counts axis from 1, not from 0!!!
    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _connect_ps90(
        self,
        control_unit: int,
        interface: int,
        port: int,
        baudrate: int,
        par3=0,
        par4=0,
        par5=0,
        par6=0,
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_Connect (long Index, long Interface, long p1, long p2, long p3, long p4, long p5, long p6)
        Description
        open interface and connect to PS 90. Serial interface (communication via USB or serial com_port)
        The application software can access this interface in the same way as it would access a standard serial com_port (COM). The parameters for Baudrate, Parity, Databits and Stopbits are predefined (9600, no parity, 8 databits, 1 stopbit).

        Example:
        Open COM3 and connect to PS 90 (Index=1):
        long error = PS90_Connect(1, 0, 3, 9600, 0, 0, 0, 0);
        :param control_unit: Index control unit index 1–10 (default=1, range=1...20)  11...20 – debug mode 1...10 – standard mode
        :param interface: Interface define interface (default=0) USB or serial com_port (=0)
        :param com_port or p1: p1 define COM com_port (default=1 – COM1, range=0...255)
        :param baudrate or p2: p2 define request mode for communication (default=9600) 115200 – fast read (all bytes, fast check) 19200 – fast read (all bytes, slow check)  9600* – standard read (byte-by-byte)
        :param par3: p3 define delay value (=20+x) for serial communication (default=20 ms)
        :param par4: p4 system value (default=0) 10 – without check 0* – with check (firmware, terminal mode, clear error)
        :param par5: p5 system value (default=0) 10 – with com_port flush  0* – without com_port flush
        :param par6: p6 system value (default=0) 5 – reconnect for every message  0* – without reconnect

        :return: 0 – function was successful 1...9 – error
        1 function error (invalid parameters)
        3 invalid serial com_port (com_port is not found)
        4 access react_denied (com_port is busy)
        5 no response from control unit (check cable, connection or reset control unit)
        8 no connection to modbus/tcp
        9 no connection to tcp/ip socket

        """
        control_unit = ctypes.c_long(control_unit)
        interface = ctypes.c_long(int(interface))
        port = ctypes.c_long(int(port))
        baudrate = ctypes.c_long(int(baudrate))
        par3 = ctypes.c_long(par3)
        par4 = ctypes.c_long(par4)
        par5 = ctypes.c_long(par5)
        par6 = ctypes.c_long(par6)
        # res x -1 is according official documentation
        sleep(time_ps_delay)
        res = (
            self.lib.PS90_Connect(
                control_unit, interface, port, baudrate, par3, par4, par5, par6
            )
            * -1
        )
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _connect_simple_ps90(
        self, control_unit=1, ser_num=""
    ) -> Tuple[Union[bool, str]]:
        r"""Long PS90_SimpleConnect (long Index, const char* pszSerNum)
        Description
        find control unit with the specified serial number and connect to it.
        Serial interface (communication via USB or serial com_port)
        The application software can access this interface in the same way as it would access a standard serial com_port (COM). The parameters for Baudrate, Parity, Databits and Stopbits are predefined (9600, no parity, 8 databits, 1 stopbit).
        The software handshake character is CR.
        Ethernet interface (communication via Com-Server)
        As Com-Server the OWIS software tool “OWISerialServer.exe” may be used (..\OWISoft\Application\system). Alternatively, you can use other commercial products (hardware/software). The application software can access this interface via Windows TCP socket: special communication for OWIS software (command + delay). The software handshake character is CR.

        Example:
        Find control unit and connect to it (empty string, COMx):
        long error = PS90_SimpleConnect(1, “”);
        :param control_unit: Index control unit index 1-10 (default=1, range=1...20)
                             11...20 – debug mode
                             1...10 – standard mode
        :param ser_num: pszSerNum control unit serial number (default=empty string)
                       USB or serial com_port
                       empty string – the first found control unit is connected;
                       “12345678” – control unit with the specified serial number is connected;
                       Ethernet interface
                       “net” – control unit is connected to the Com-Server (local application) by the first found local IP address and com_port number 1200.
        :return: 0 – function was successful
                 1...9 – error
                 1 function error (invalid parameters)
                 5 no response from control unit (check cable, connection or reset control unit)
                 7 control unit with the specified serial number is not found
                 9 no connection to tcp/ip socket

        """
        control_unit = ctypes.c_long(control_unit)
        ser_num = ctypes.c_char_p(ser_num)
        sleep(time_ps_delay)
        res = (
            self.lib.PS90_SimpleConnect(control_unit, ser_num) * -1
        )  # *-1 is according official documentation
        return True if res == 0 else False, self._error_OWIS_ps90(res, 0)

    def _convert_axis_state_format_ps90(self, axis_state_OWIS: int) -> int:
        """Converts OWIS controller axis state to the used for stpmtr_controller
        :param axis_state_OWIS: 0     axis is not active
                                1     axis is not initialized
                                2     axis is switched off
                                3     axis is active and initialized and switched on
        :return: 0 - axis is not initialized, 1 - is active
        """
        if axis_state_OWIS in [0, 1, 2]:
            return 0
        if axis_state_OWIS == 3:
            return 1
        return 0

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _disconnect_ps90(self, control_unit: int) -> Tuple[Union[bool, str]]:
        """Long PS90_Disconnect (long Index)
        Description
        disconnect PS 90
        Example
        Disconnect a control unit (Index=1):
        long error = PS90_Disconnect(1);
        :param control_unit: Index control unit index (1-10)
        :return:  0 – function was successful -1 – function error

        """
        control_unit = ctypes.c_long(control_unit)
        sleep(time_ps_delay)
        res = self.lib.PS90_Disconnect(control_unit)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _free_switch_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_FreeSwitch (long Index, long AxisId)
        Description
        release active limit switches of an axis.
        After an axis has driven into a limit switch, it can release a limit switch with this function. This is valid only for released axes. Besides, the direction of the movement is selected automatically, depending on whether a positive or negative limit switch is activated.

        Example:
        Release active limit switches of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetLimitSwitch(1,1,15);
        error = PS90_SetLimitSwitchMode(1,1,15);
        long state = PS90_GetSwitchState(1,1);
        if( state & 15 ) error = PS90_FreeSwitch(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
                -4 – axis in wrong state

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_FreeSwitch(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _get_connection_info(self, control_unit: int) -> Tuple[Union[bool, str]]:
        """Synopsis
        long PS90_GetConnectInfo (long Index, char* pszBuffer, long Length, long Mode)
        Description
        read connecting configuration
        Parameters
        Index control unit index (1-10)
        pszBuffer address of buffer for reading
        Length length of the buffer
        Mode mode (default=0, range=0...3)
        0 – connecting configuration
        1 – connecting configuration (short format)
        2 – last transferred data
        3 – connecting state (online or offline)

        Returns
        -------
        length of the string
        Example
        Read a connecting configuration for the control unit (Index=1):
        char szString[50];
        long len = PS90_GetConnectInfo(1, szString, 50, 0);
        long error = PS90_GetReadError(1);

        """

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _get_serial_number_ps90(self, control_unit: int) -> Tuple[Union[bool, str]]:
        """Synopsis
                    long PS90_GetSerNumber (long Index, char* pszBuffer, long Length)


        Description
        read serial number of the control unit


        Parameters
        ----------
        Index control unit index (1-10)
        pszBuffer address of the buffer for reading
        Length length of the buffer



        Returns
        -------
        length of the string


        Example
        Read serial number of the control unit (Index=1):
        char szString[25];
        long len = PS90_GetSerNumber(1, 1, szString, 25);
        long error = PS90_GetReadError(1);

        """
        buf = ctypes.create_string_buffer(25)
        control_unit = ctypes.c_long(control_unit)
        res = self.lib.PS90_GetSerNumber(control_unit, buf, 25)
        result = buf.value.decode("utf-8")
        return int(result)

    @development_mode(dev=dev_mode, with_return=(3, "DEV MODE"))
    def _get_axis_state_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[int, bool, str]]:
        """Long PS90_GetAxisState (long Index, long AxisId)
        Description
        read axis state
        Example
            Read axis state of the control unit (Index=1, Axis=1):
            long ready = PS90_GetAxisState(1,1);
            long error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId=0 read state of all axes AxisId=1...9 read state of an axis
        :return: AxisId Value Meaning
                 0      0     any axis is not active
                        1     any axis is not initialized
                        2     any axis is switch off
                        3     all axes are active and initialized and switched on
                1...9   0     axis is not active
                        1     axis is not initialized
                        2     axis is switched off
                        3     axis is active and initialized and switched on
        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_GetAxisState(control_unit, axis)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(0.0, "DEV MODE"))
    def _get_target_ex_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[float, bool, str]]:
        """Double PS90_GetTargetEx (long Index, long AxisId)
        Description
        read target position or distance of an axis (values in selected unit)

        Parameters
        ----------
        Index control unit index (1-10)
        AxisId axis number (1...9)
        Example
        Read target position or distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        double dValue = PS90_GetTargetEx(1,1);
        error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: target position or distance (values in selected unit)


        """
        if not control_unit:
            control_unit = self.control_unit_id
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        res = self.lib.PS90_GetTargetEx(control_unit, axis) / 10000
        sleep(time_ps_delay)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(0.0, "DEV MODE"))
    def _get_pos_ex_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[float, bool, str]]:
        """Double PS90_GetPositionEx (long Index, long AxisId)
        Description
        read current value of a position counter of an axis (values in selected unit)

        Example:
        Read current position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        double dValue = PS90_GetPositionEx(1,1);
        error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: value of the current position (values in selected unit) or False if error

        """
        if not control_unit:
            control_unit = self.control_unit_id
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        pitch = self._delay_lines_parameters[axis]["pitch"]
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_GetPosition(control_unit, axis) / 10000 * pitch
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        error = self._error_OWIS_ps90(error, 1)
        return res, error

    @development_mode(dev=dev_mode, with_return=(0.0, "DEV MODE"))
    def _get_target_mode_ps90(
        self, control_unit: int, axis: int
    ) -> Tuple[Union[float, bool, str]]:
        """Description
        read target mode of an axis
        Parameters
        Index control unit index (1-10)
        AxisId axis number (1...9)

        Returns:
        0 – relative positioning (target value is distance)
        1 – absolute positioning (target value is target position)

        Example:
        Read target mode of an axis of the control unit (Index=1, Axis=1):
        long mode = PS90_GetTargetMode(1,1);
        long error = PS90_GetReadError(1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)

        """
        if not control_unit:
            control_unit = self.control_unit_id
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_GetTargetMode(control_unit, axis)
        error = self.__get_read_error_ps90(control_unit)
        if error != 0:
            res = False
        return res, self._error_OWIS_ps90(error, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _go_target_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """Long PS90_GoTarget (long Index, long AxisId)
        Description
        start positioning of an axis.
        The axis goes to a new target position or a distance either in the trapezoidal or S-curve profile. This is valid only for released axes.

        Example:
        Drive an axis of the control unit (Index=1, Axis=1) to a target in trapezoidal profile:
        long error = PS90_SetPosMode(1,1,0);
        error = PS90_SetTargetMode(1,1,1);
        error = PS90_SetTarget(1,1,0);
        error = PS90_GoTarget(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
                -4 – axis in wrong state

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_GoTarget(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def __get_read_error_ps90(self, control_unit: int) -> int:
        if not isinstance(control_unit, ctypes.c_long):
            control_unit = ctypes.c_long(control_unit)
        sleep(time_ps_delay)
        res = self.lib.PS90_GetReadError(control_unit)
        return res

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _motor_init_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """Long PS90_MotorInit (long Index, long AxisId)
        Description
        initialize an axis and switch on.
        With this function the axis is completely initialized and afterwards is with a current and with active positioning regulator.
        It must be executed after the turning on of the control unit, so that the axis can be moved afterwards with the commands REF, PGO, VGO etc.
        Before the following parameters must have been set: limit switch mask and polarity, start regulator parameters.

        Example:
        Initialize an axis of the control unit (Index=1, Axis=1) and switch on:
        long error = PS90_MotorInit(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_MotorInit(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Motor of axis {axis} is initialized"
        )

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _motor_on_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """Long PS90_MotorOn (long Index, long AxisId)
        Description
        switch an axis on.
        With this function the axis, after the motor was switched off, is switched on again and afterwards is with a current and with active positioning regulator.

        Example:
        Switch an axis of the control unit (Index=1, Axis=1) on:
        long error = PS90_MotorOff(1,1);
        error = PS90_MotorOn(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_MotorOn(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Motor of axis {axis} is on."
        )

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _motor_off_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """Long PS90_MotorOff (long Index, long AxisId)
        Description
        switch an axis off.
        With this function the position regulator is deactivated and the power amplifier is switched off.

        Example:
        Switch an axis of the control unit (Index=1, Axis=1) off:
        long error = PS90_MotorOff(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_int(control_unit)
        axis = int(axis)
        axis = ctypes.c_int(axis)
        sleep(time_ps_delay)
        res = self.lib.PS90_MotorOff(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Motor of axis {axis} is off."
        )

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _stop_axis_ps90(self, control_unit: int, axis: int) -> Tuple[Union[bool, str]]:
        """Long PS90_Stop (long Index, long AxisId)
        Description
        stop movement of an axis.
        Any active movement of an axis is terminated. The axis is stopped with the programmed brake ramp and stands still.

        Example:
        Stop movement of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_Stop(1,1);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :return:  0 – function was successful -1 – function error -2 – communication error -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        res = self.lib.PS90_Stop(control_unit, axis)
        return True if res == 0 else False, self._error_OWIS_ps90(
            res, 1, f"Axis {axis} movement is stopped."
        )

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_limit_min_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetLimitMinEx (long Index, long AxisId, double dValue)
        Description
        set negative limit position of an axis (values in selected unit).
        This limit position is evaluated with moving in negative direction.

        Example:
        Set negative limit position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetLimitMinEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue negative limit position (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetLimitMinEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_limit_max_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetLimitMinEx (long Index, long AxisId, double dValue)
        Description
        set negative limit position of an axis (values in selected unit).
        This limit position is evaluated with moving in negative direction.

        Example:
        Set positive limit position of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetLimitMaxEx(1,1,50.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue negative limit position (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetLimitMaxEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_position_ex_ps90(
        self, control_unit: int, axis: int, pos: float
    ) -> Tuple[Union[bool, str]]:
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        pos = ctypes.c_double(pos)
        res = self.lib.PS90_SetPositionEx(control_unit, axis, pos)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_pos_mode_ps90(
        self, control_unit: int, axis: int, mode: int
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetPosMode (long Index, long AxisId, long Mode)
        Description
        set positioning mode of an axis
        Example
        Set positioning mode of an axis of the control unit (Index=1, Axis=1, trapezoidal profile):
        long error = PS90_SetPosMode(1,1,0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param mode: Mode positioning mode Mode=0 trapezoidal profile Mode=1 S-curve profile
        :return: 0 – function was successful -1 – function error -2 – communication error -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        mode = ctypes.c_long(mode)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetPosMode(control_unit, axis, mode)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_pos_velocity_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetPosFEx (long Index, long AxisId, double dValue)
        Description
        set positioning velocity of an axis (values in selected unit).
        It is used for a trapezoidal and a S-curve profile.
        velocity = unit/s
        Example
        Set positioning velocity of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetPosFEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param speed: dValue positioning velocity (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetPosFEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_stage_attributes_ps90(
        self,
        control_unit: int,
        axis: int,
        pitch: float,
        inc_rev: int,
        gear_ratio: float,
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetStageAttributes (long Index, long AxisId, double dPitch, long IncRev, double dRatio)
        Description
        set stage attributes for an axis.
        The control unit uses for positioning of the axes internal values (increments). To allow the positioning in other units (e.g., for linear measuring stages - mm, µm, for rotary measuring stages - degrees, mrad etc.), these parameters should be defined. Then one is able to use the extended functions (...Ex) with a desired unit. The specified values are converted internally into increments. The movement of the slide per spindle revolution (pitch) is specified in a desired unit (e.g., 1 mm), as the first parameter for linear measuring stages. With rotary measuring stages a revolution of the rotary table is specified in a desired unit (e.g., 360 degrees). The number of the increments per motor revolution is defined as the second parameter. With the step motors it is the number of the full steps per revolution (e.g., 200). If a motor with the encoder is controlled, it is the number of the increments per revolution (e.g., encoder with 4-fold evaluation: encoder lines number x 4 = 500x4). The whole gear reduction ratio specified as the third parameter.

        Example:
        Define stage attributes of the control unit (Index=1, Axis=1)
        (linear measuring stage + servo motor with encoder: pitch = 1.0 mm, pulses/rev = 2000, ratio =1.0):
        long error = PS90_SetStageAttributes(1,1,1.0,2000,1.0);
        double dValue = PS90_GetPositionEx(1,1);
        Define stage attributes of the control unit (Index=1, Axis=2)
        (rotary measuring stage + step motor without encoder: revolution = 360.0 degrees, full steps/rev = 200, ratio =180.0):
        error = PS90_SetStageAttributes(1,2,360.0,200,180.0);
        dValue = PS90_GetPositionEx(1,2);
        :param control_unit:Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param pitch: dPitch pitch
        :param inc_rev: IncRev pulses/steps per motor revolution
        :param gear_ratio: dRatio gear reduction ratio
        :return: 0 – function was successful
                -1 – function error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        pitch = ctypes.c_double(pitch)
        inc_rev = ctypes.c_long(int(inc_rev))
        gear_ratio = ctypes.c_double(gear_ratio)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetStageAttributes(
            control_unit, axis, pitch, inc_rev, gear_ratio
        )
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_target_mode_ps90(
        self, control_unit: int, axis: int, mode: int
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetTargetMode (long Index, long AxisId, long Mode)
        Description
        set target mode of an axis
        Example
        Set target mode of the control unit (Index=1, Axis=1) for relative positioning:
        long error = PS90_SetTargetMode(1,1,0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param mode: Mode target mode Mode=0 relative positioning (target value is distance) Mode=1 absolute positioning (target value is target position)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error
        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        mode = ctypes.c_long(mode)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetTargetMode(control_unit, axis, mode)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_target_ps90(
        self, control_unit: int, axis: int, value: int
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetTarget (long Index, long AxisId, long Value)
        Description
        set target position or distance of an axis (values in increments).
        The definition depends on the target mode. The sign determines the positioning direction.

        Example:
        Set distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetTargetMode(1,1,0);
        error = PS90_SetTarget(1,1,100);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1…9)
        :param value: Value target position or distance (values in increments)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_long(value)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetTarget(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_target_ex_ps90(
        self, control_unit: int, axis: int, value: float
    ) -> Tuple[Union[bool, str]]:
        """Long PS90_SetTargetEx (long Index, long AxisId, double dValue)
        Description
        set target position or distance of an axis (values in selected unit).
        The definition depends on the target mode. The sign determines the positioning direction.

        Example:
        Set distance of an axis of the control unit (Index=1, Axis=1):
        long error = PS90_SetCalcResol(1,1,0.0001);
        error = PS90_SetTargetMode(1,1,0);
        error = PS90_SetTargetEx(1,1,10.0);
        :param control_unit: Index control unit index (1-10)
        :param axis: AxisId axis number (1...9)
        :param value: dValue target position or distance (values in selected unit)
        :return: 0 – function was successful
                -1 – function error
                -2 – communication error
                -3 – syntax error

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetTargetEx(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_drive_current_ex_ps90(self, control_unit: int, axis: int, value: float):
        """Synopsis
        long PS90_SetDriveCurrent (long Index, long AxisId, long Value)

        Description
        set drive current for an axis (values in percent).
        For step motor axes (Open Loop) it is an adjustable current. For dc servo motor axes (DC-Brush) it is an adjustable current limiting. For BLDC and step motor axes (Closed Loop) it is an adjustable current limiting. For step motor axes the maximum current will be defined with the function “PS90_SetCurrentLevel” (low – 2.4 A, high – 5.45 A). A maximum allowed current is 3.6 A. Therefore the maximum value for high current level is 66 percent.
        For dc servo motor axes the maximum current limiting is defined (12 A). The function “PS90_SetCurrentLevel” has no effect.
        For BLDC and step motor axes (Closed Loop) the maximum current limiting is defined (6 A). The function “PS90_SetCurrentLevel” has no effect.

        Parameters
        ----------
        Index control unit index (1-10)
        AxisId axis number (1...9)
        Value drive current (values in percent)

        Returns
        -------
         0 – function was successful
        -1 – function error
        -2 – communication error
        -3 – syntax error


        Example
        Set drive current of the control unit (Index=1, Axis=1):
        long error = PS90_SetDriveCurrent(1,1,50);

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetDriveCurrent(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    @development_mode(dev=dev_mode, with_return=(True, "DEV MODE"))
    def _set_hold_current_ex_ps90(self, control_unit: int, axis: int, value: float):
        """Synopsis
        long PS90_SetHoldCurrent (long Index, long AxisId, long Value)

        Description
        set hold current for an axis (values in percent).
        This setting is valid only for step motor axes (Open Loop). The maximum current will be defined with the
        function “PS90_SetCurrentLevel” (low – 2.4 A, high – 5.45 A). A maximum allowed current is 3.6 A.
        Therefore the maximum value for high current level is 66 percent.

        Parameters
        ----------
        Index control unit index (1-10)
        AxisId axis number (1...9)
        Value hold current (values in percent)

        Returns
        -------
         0 – function was successful
        -1 – function error
        -2 – communication error
        -3 – syntax error


        Example
        Set hold current of the control unit (Index=1, Axis=1):
        long error = PS90_SetHoldCurrent(1,1,30);

        """
        control_unit = ctypes.c_long(control_unit)
        axis = int(axis)
        axis = ctypes.c_long(axis)
        value = ctypes.c_double(value)
        sleep(time_ps_delay)
        res = self.lib.PS90_SetHoldCurrent(control_unit, axis, value)
        return True if res == 0 else False, self._error_OWIS_ps90(res, 1)

    def _error_OWIS_ps90(self, code: int, type: int, user_def="") -> str:
        """:param code: <=0
        :param type: 0 for Connection error codes, 1 for Function error codes
        :return: error as string
        """
        errors_connections = {
            0: "no error",
            -1: "function error",
            -3: "invalid serial com_port (com_port is not found)",
            -4: "access react_denied  (com_port is busy)",
            -5: "no response from control unit",
            -7: "control unit with the specified serial number is not found",
            -8: "no connection to modbus/tcp",
            -9: "no connection to tcp/ip socket",
        }
        errors_functions = {
            0: "no error",
            -1: "function error",
            -2: "communication error",
            -3: "syntax error",
            -4: "axis is in wrong state",
            -9: "OWISid chip is not found",
            -10: "OWISid parameter is empty (not defined)",
        }
        if code > 0:
            return "Wrong code number"
        if type not in [0, 1]:
            return "Wrong type of error"
        if type == 0 and code not in errors_connections:
            return "Wrong code number"
        if type == 1 and code not in errors_functions:
            return "Wrong code number"
        if code != 0:
            return errors_connections[code] if type == 0 else errors_functions[code]
        return user_def


def main(device_name=None):
    sys.argv.append(device_name)
    DS_OWIS_PS90.run_server()


if __name__ == "__main__":
    DS_OWIS_PS90.run_server()
