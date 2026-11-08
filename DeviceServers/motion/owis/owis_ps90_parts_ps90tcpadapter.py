"""Implementation for _PS90TcpAdapter and related operations."""


def _bind_owis_ps90_parts_ps90tcpadapter(api):
    """Bind implementation to the owning module and its runtime state."""

    class _PS90TcpAdapter:
        """Minimal DLL-like adapter for OWIS PS90 direct TCP access."""

        def __init__(
            self,
            host: str,
            port: int = 8777,
            timeout: float = 5.0,
            command_delay: float = 0.005,
            velocity_scale: float = 16.0,
            velocity_scale_map: api.Optional[dict[int, float]] = None,
            allow_high_current_level: bool = True,
            strict_ovis_init_profile: bool = True,
            ovis_init_current_level: int = 0,
            ovis_init_hold_current_percent: int = 38,
            ovis_init_drive_current_percent: int = 50,
            ovis_init_ready_timeout: float = 6.0,
            ovis_init_poll_interval: float = 0.05,
        ):
            from owis_ps90_tcp import OwisPS90TCP

            self._controller = OwisPS90TCP(ip=host, port=port, timeout=timeout)
            self._controller.command_delay = max(0.0, float(command_delay))
            self._last_error = 0
            self._target_modes = {}
            self._stage_attrs = {}
            self._limits = {}
            self._microsteps = {}
            self._target_counts = {}
            self._velocity_scale = max(0.01, float(velocity_scale))
            self._velocity_scale_map = {}
            self._allow_high_current_level = bool(allow_high_current_level)
            self._strict_ovis_init_profile = bool(strict_ovis_init_profile)
            self._ovishnt_level = 0 if int(ovis_init_current_level) <= 0 else 1
            self._ovihold = max(0, min(100, int(round(ovis_init_hold_current_percent))))
            self._ovidrive = max(0, min(100, int(round(ovis_init_drive_current_percent))))
            self._ovi_ready_timeout = max(0.5, float(ovis_init_ready_timeout))
            self._ovi_poll_interval = max(0.01, float(ovis_init_poll_interval))
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

        def _astat_axis_char(self, axis: int) -> str:
            astat = (self._controller.query("?ASTAT") or "").strip().upper()
            idx = int(axis) - 1
            if 0 <= idx < len(astat):
                return astat[idx]
            return ""

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

        def _get_current_level(self, axis: int) -> api.Optional[int]:
            """Return current level from controller (0=low, 1=high), or None if unknown."""
            try:
                resp = self._controller.query(f"?AMPSHNT{axis}")
                level = int(str(resp).strip())
                return level if level in (0, 1) else None
            except Exception:
                return None

        def _set_current_level(self, axis: int, level: int) -> None:
            self._controller.send_command(f"AMPSHNT{axis}={int(level)}", expect_response=False)

        def _query_int(self, command: str) -> int:
            resp = self._controller.query(command)
            return int(str(resp).strip())

        def _set_and_verify_int(
            self,
            set_command: str,
            query_command: str,
            expected: int,
            retries: int = 3,
        ) -> bool:
            expected_i = int(expected)
            for _ in range(max(1, int(retries))):
                self._controller.send_command(set_command, expect_response=False)
                api.time.sleep(self._ovi_poll_interval)
                try:
                    if self._query_int(query_command) == expected_i:
                        return True
                except Exception:
                    pass
            return False

        def _wait_axis_ready(self, axis: int) -> bool:
            deadline = api.time.monotonic() + self._ovi_ready_timeout
            while api.time.monotonic() < deadline:
                ch = self._astat_axis_char(axis)
                if ch == "R":
                    return True
                api.time.sleep(self._ovi_poll_interval)
            return False

        @property
        def strict_ovis_init_profile(self) -> bool:
            return bool(self._strict_ovis_init_profile)

        def apply_ovis_current_profile(self, axis: int) -> tuple[bool, str]:
            """Apply OVIS-like current sequence with readback verification."""
            try:
                self._ensure_connected()
                axis_i = int(axis)
                if not self._set_and_verify_int(
                    f"AMPSHNT{axis_i}={self._ovishnt_level}",
                    f"?AMPSHNT{axis_i}",
                    self._ovishnt_level,
                ):
                    return False, f"AMPSHNT{axis_i} readback mismatch"
                if not self._set_and_verify_int(
                    f"HOLCUR{axis_i}={self._ovihold}",
                    f"?HOLCUR{axis_i}",
                    self._ovihold,
                ):
                    return False, f"HOLCUR{axis_i} readback mismatch"
                if not self._set_and_verify_int(
                    f"DRICUR{axis_i}={self._ovidrive}",
                    f"?DRICUR{axis_i}",
                    self._ovidrive,
                ):
                    return False, f"DRICUR{axis_i} readback mismatch"
                return True, "ok"
            except Exception as e:
                return False, str(e)

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

            # Switch to high range automatically when requested current exceeds low range.
            if self._allow_high_current_level and v > 2.4 and level == 0:
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
                # On some PS90 TCP firmware, ?AXISx reports 1 even while the axis moves.
                # Use ASTAT first as the effective runtime indicator.
                ch = self._astat_axis_char(axis_i)
                if ch in ("R", "T", "M"):
                    self._ok()
                    return 3
                if ch in ("O", "L"):
                    self._ok()
                    return 2
                if ch == "U":
                    self._ok()
                    return 1
                state = int(self._controller.get_axis_state(axis_i))
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
                pos_before = float(self._controller.get_position(axis_i))
                ok = self._controller.go_target(axis_i)
                if not ok:
                    return self._fail(-4)
                target = self._target_counts.get(axis_i)

                # Confirm movement start (or immediate target reach) to avoid false "success".
                deadline = api.time.monotonic() + 1.5
                while api.time.monotonic() < deadline:
                    ch = self._astat_axis_char(axis_i)
                    pos_now = float(self._controller.get_position(axis_i))
                    if ch == "T":
                        return self._ok()
                    if target is not None and abs(pos_now - float(target)) <= 2.0:
                        return self._ok()
                    if abs(pos_now - pos_before) >= 2.0:
                        return self._ok()
                    api.time.sleep(0.05)
                return self._fail(-4)
            except Exception:
                return self._fail(-2)

        def PS90_MotorInit(self, _control_unit, axis):
            try:
                self._ensure_connected()
                axis_i = self._to_int(axis)
                self._controller.send_command(f"AXIS{axis_i}=1", expect_response=False)
                if self._strict_ovis_init_profile:
                    ok_profile, _ = self.apply_ovis_current_profile(axis_i)
                    if not ok_profile:
                        return self._fail(-4)
                ok = self._controller.motor_init(axis_i)
                if not ok:
                    return self._fail(-4)
                if self._strict_ovis_init_profile and not self._wait_axis_ready(axis_i):
                    return self._fail(-4)
                return self._ok()
            except Exception:
                return self._fail(-2)

        def PS90_MotorOn(self, _control_unit, axis):
            try:
                self._ensure_connected()
                axis_i = self._to_int(axis)
                ok = self._controller.motor_on(axis_i)
                return self._ok() if ok else self._fail(-4)
            except Exception:
                return self._fail(-2)

        def PS90_MotorOff(self, _control_unit, axis):
            try:
                self._ensure_connected()
                axis_i = self._to_int(axis)
                ok = self._controller.motor_off(axis_i)
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
                axis_i = self._to_int(axis)
                target = self._to_int(value)
                self._controller.set_target(axis_i, target)
                self._target_counts[axis_i] = target
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
                self._target_counts[axis_i] = counts
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

    _PS90TcpAdapter.__module__ = api.__name__
    _PS90TcpAdapter.__qualname__ = "_PS90TcpAdapter"

    return {
        "_PS90TcpAdapter": _PS90TcpAdapter,
    }
