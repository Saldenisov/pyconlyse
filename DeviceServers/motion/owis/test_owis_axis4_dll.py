#!/usr/bin/env python
"""
Direct DLL test for OWIS PS90 axis 4 — validates correct current initialization
and basic movement using the same logic as the TCP adapter.

This script bypasses the Tango Device Server and talks to the controller via
ps90_64.dll so that OWIS OWISoft can also be used side-by-side for verification.

Usage:
    python test_owis_axis4_dll.py
"""

import ctypes
from ctypes import windll, c_long, c_double
import os
import sys
import time

# ── Configuration ──────────────────────────────────────────────────────────
AXIS = 4
CONTROL_UNIT = 1
SERIAL_NUMBER = 15110070      # from Tango DB

# Stage parameters (from add_ds_OWIS_PS90.py, axis 4)
PITCH = 5.0                   # mm per revolution
REVOLUTION = 200              # increments per revolution
GEAR_RATIO = 1.0

# Current settings (Amperes — same as Tango DB)
DRIVE_CURRENT_A = 2.5
HOLD_CURRENT_A = 0.5

# Low current level: max 2.4 A → 100 %
# High current level: max 5.45 A → capped at 66 % (= 3.6 A)
LOW_LEVEL_MAX_A = 2.4
HIGH_LEVEL_MAX_A = 5.45
HIGH_LEVEL_CAP_PCT = 66

# Movement test
SPEED = 30.0                  # mm/s
LIMIT_MIN = -900.0
LIMIT_MAX = 100.0
TEST_MOVE_TARGET = -10.0      # small safe move (mm)
MOVE_TIMEOUT = 30.0           # seconds


# ── Helpers ────────────────────────────────────────────────────────────────
def log(msg, indent=0):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}")


def amps_to_percent(amps: float, level: int) -> int:
    """Convert Amperes to DLL percent for a given current level (0=low, 1=high)."""
    v = abs(float(amps))
    if level == 0:
        pct = int(round((v / LOW_LEVEL_MAX_A) * 100.0))
        return max(0, min(100, pct))
    pct = int(round((v / HIGH_LEVEL_MAX_A) * 100.0))
    return max(0, min(HIGH_LEVEL_CAP_PCT, pct))


# ── DLL wrapper ────────────────────────────────────────────────────────────
class OWISDirect:
    """Thin ctypes wrapper — types match the DLL signatures exactly."""

    def __init__(self, dll_path=None):
        if dll_path is None:
            drivers = os.path.join(os.path.dirname(os.path.abspath(__file__)), "drivers")
            dll_path = os.path.join(drivers, "ps90_64.dll")
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL not found: {dll_path}")
        dll_dir = os.path.dirname(dll_path)
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_dir)
        self.lib = windll.LoadLibrary(dll_path)

        # Set return types for functions that return double
        self.lib.PS90_GetPositionEx.restype = c_double
        self.connected = False
        self.cu = c_long(CONTROL_UNIT)

    # ── connection ─────────────────────────────────────────────────────────
    def simple_connect(self, ser_num: bytes = b"") -> int:
        return self.lib.PS90_SimpleConnect(self.cu, ser_num)

    def disconnect(self) -> int:
        return self.lib.PS90_Disconnect(self.cu)

    # ── current level ──────────────────────────────────────────────────────
    def get_current_level(self, axis: int) -> int:
        """0 = low (2.4 A), 1 = high (5.45 A)."""
        return self.lib.PS90_GetCurrentLevel(self.cu, c_long(axis))

    def set_current_level(self, axis: int, level: int) -> int:
        return self.lib.PS90_SetCurrentLevel(self.cu, c_long(axis), c_long(level))

    # ── currents (percent, long Value) ─────────────────────────────────────
    def set_drive_current(self, axis: int, pct: int) -> int:
        return self.lib.PS90_SetDriveCurrent(self.cu, c_long(axis), c_long(pct))

    def set_hold_current(self, axis: int, pct: int) -> int:
        return self.lib.PS90_SetHoldCurrent(self.cu, c_long(axis), c_long(pct))

    # ── init / on / off ────────────────────────────────────────────────────
    def motor_init(self, axis: int) -> int:
        return self.lib.PS90_MotorInit(self.cu, c_long(axis))

    def motor_on(self, axis: int) -> int:
        return self.lib.PS90_MotorOn(self.cu, c_long(axis))

    def motor_off(self, axis: int) -> int:
        return self.lib.PS90_MotorOff(self.cu, c_long(axis))

    # ── stage / motion ─────────────────────────────────────────────────────
    def set_stage_attributes(self, axis, pitch, inc_rev, gear_ratio) -> int:
        return self.lib.PS90_SetStageAttributes(
            self.cu, c_long(axis), c_double(pitch), c_long(int(inc_rev)), c_double(gear_ratio)
        )

    def set_pos_f(self, axis: int, speed: float) -> int:
        """PS90_SetPosFEx — positioning velocity in selected unit/s."""
        return self.lib.PS90_SetPosFEx(self.cu, c_long(axis), c_double(speed))

    def set_limit_min(self, axis: int, value: float) -> int:
        return self.lib.PS90_SetLimitMinEx(self.cu, c_long(axis), c_double(value))

    def set_limit_max(self, axis: int, value: float) -> int:
        return self.lib.PS90_SetLimitMaxEx(self.cu, c_long(axis), c_double(value))

    def set_target_mode(self, axis: int, mode: int) -> int:
        return self.lib.PS90_SetTargetMode(self.cu, c_long(axis), c_long(mode))

    def set_target(self, axis: int, pos: float) -> int:
        return self.lib.PS90_SetTargetEx(self.cu, c_long(axis), c_double(pos))

    def go_target(self, axis: int) -> int:
        return self.lib.PS90_GoTarget(self.cu, c_long(axis))

    def get_position(self, axis: int) -> float:
        return self.lib.PS90_GetPositionEx(self.cu, c_long(axis))

    def get_axis_state(self, axis: int) -> int:
        """0=not active, 1=not init, 2=off, 3=on"""
        return self.lib.PS90_GetAxisState(self.cu, c_long(axis))

    def get_move_state(self, axis: int) -> int:
        """>0 = moving, 0 = stopped"""
        return self.lib.PS90_GetMoveState(self.cu, c_long(axis))

    def stop(self, axis: int) -> int:
        return self.lib.PS90_Stop(self.cu, c_long(axis))


# ── Main test ──────────────────────────────────────────────────────────────
def main():
    log("=" * 70)
    log("OWIS PS90 — Axis 4 DLL Test (current init + movement)")
    log("=" * 70)

    # ── 1. Load DLL ────────────────────────────────────────────────────────
    log("Loading DLL...")
    try:
        ow = OWISDirect()
        log("OK DLL loaded", 1)
    except Exception as e:
        log(f"FAIL DLL load: {e}", 1)
        return 1

    # ── 2. Connect ─────────────────────────────────────────────────────────
    log("Connecting (SimpleConnect)...")
    res = ow.simple_connect()
    if res != 0:
        log(f"FAIL SimpleConnect returned {res}", 1)
        return 1
    log("OK connected", 1)

    try:
        # ── 3. Current level ───────────────────────────────────────────────
        level = ow.get_current_level(AXIS)
        log(f"Current level before: {level} (0=low/2.4A, 1=high/5.45A)", 1)

        need_high = DRIVE_CURRENT_A > LOW_LEVEL_MAX_A
        if need_high and level != 1:
            log(f"Drive current {DRIVE_CURRENT_A}A > {LOW_LEVEL_MAX_A}A, switching to high level", 1)
            res = ow.set_current_level(AXIS, 1)
            if res != 0:
                log(f"FAIL SetCurrentLevel returned {res}", 1)
                return 1
            level = ow.get_current_level(AXIS)
            log(f"Current level after: {level}", 1)

        # ── 4. Drive / hold currents (percent) ────────────────────────────
        drive_pct = amps_to_percent(DRIVE_CURRENT_A, level)
        hold_pct = amps_to_percent(HOLD_CURRENT_A, level)
        log(f"Drive: {DRIVE_CURRENT_A}A -> {drive_pct}%  (level={level})", 1)
        log(f"Hold:  {HOLD_CURRENT_A}A -> {hold_pct}%  (level={level})", 1)

        res = ow.set_drive_current(AXIS, drive_pct)
        if res != 0:
            log(f"FAIL SetDriveCurrent returned {res}", 1)
            return 1
        log("OK drive current set", 1)

        res = ow.set_hold_current(AXIS, hold_pct)
        if res != 0:
            log(f"FAIL SetHoldCurrent returned {res}", 1)
            return 1
        log("OK hold current set", 1)

        # ── 5. Motor init ─────────────────────────────────────────────────
        log(f"MotorInit axis {AXIS}...")
        res = ow.motor_init(AXIS)
        if res != 0:
            log(f"FAIL MotorInit returned {res}", 1)
            return 1
        log("OK motor initialized", 1)

        # ── 6. Stage attributes ────────────────────────────────────────────
        log(f"SetStageAttributes pitch={PITCH} rev={REVOLUTION} gear={GEAR_RATIO}")
        res = ow.set_stage_attributes(AXIS, PITCH, REVOLUTION, GEAR_RATIO)
        if res != 0:
            log(f"FAIL SetStageAttributes returned {res}", 1)
            return 1
        log("OK stage attributes", 1)

        # ── 7. Velocity, limits, absolute mode ─────────────────────────────
        res = ow.set_pos_f(AXIS, SPEED)
        log(f"SetPosFEx speed={SPEED}: {res}", 1)

        res = ow.set_limit_min(AXIS, LIMIT_MIN)
        log(f"SetLimitMin {LIMIT_MIN}: {res}", 1)

        res = ow.set_limit_max(AXIS, LIMIT_MAX)
        log(f"SetLimitMax {LIMIT_MAX}: {res}", 1)

        res = ow.set_target_mode(AXIS, 1)  # absolute
        log(f"SetTargetMode absolute: {res}", 1)

        # ── 8. Motor on ───────────────────────────────────────────────────
        log("MotorOn...")
        res = ow.motor_on(AXIS)
        if res != 0:
            log(f"FAIL MotorOn returned {res}", 1)
            return 1
        time.sleep(0.2)
        state = ow.get_axis_state(AXIS)
        log(f"Axis state: {state} (3=ON)", 1)

        # ── 9. Read position ──────────────────────────────────────────────
        pos0 = ow.get_position(AXIS)
        log(f"Current position: {pos0:.4f} mm", 1)

        # ── 10. Move ──────────────────────────────────────────────────────
        target = TEST_MOVE_TARGET
        log(f"Moving to {target} mm ...")
        res = ow.set_target(AXIS, target)
        if res != 0:
            log(f"FAIL SetTargetEx returned {res}", 1)
            return 1

        res = ow.go_target(AXIS)
        if res != 0:
            log(f"FAIL GoTarget returned {res}", 1)
            return 1

        t0 = time.time()
        while ow.get_move_state(AXIS) > 0:
            pos = ow.get_position(AXIS)
            log(f"  moving... pos={pos:.4f}", 2)
            if time.time() - t0 > MOVE_TIMEOUT:
                log("FAIL movement timeout, stopping", 1)
                ow.stop(AXIS)
                return 1
            time.sleep(0.5)

        pos1 = ow.get_position(AXIS)
        err = abs(pos1 - target)
        log(f"Final position: {pos1:.4f} mm  (error={err:.4f} mm)", 1)

        if err < 1.0:
            log("OK movement successful", 1)
        else:
            log("FAIL large position error", 1)
            return 1

        # ── 11. Return to original position ───────────────────────────────
        log(f"Returning to {pos0:.4f} mm ...")
        ow.set_target(AXIS, pos0)
        ow.go_target(AXIS)
        t0 = time.time()
        while ow.get_move_state(AXIS) > 0:
            if time.time() - t0 > MOVE_TIMEOUT:
                ow.stop(AXIS)
                break
            time.sleep(0.5)
        pos2 = ow.get_position(AXIS)
        log(f"Returned to: {pos2:.4f} mm", 1)

        # ── 12. Motor off ─────────────────────────────────────────────────
        ow.motor_off(AXIS)
        log("Motor off", 1)

        log("=" * 70)
        log("ALL TESTS PASSED")
        log("=" * 70)
        return 0

    except Exception as e:
        log(f"EXCEPTION: {e}", 1)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        log("Disconnecting...")
        ow.disconnect()
        log("Disconnected", 1)


if __name__ == "__main__":
    sys.exit(main())
