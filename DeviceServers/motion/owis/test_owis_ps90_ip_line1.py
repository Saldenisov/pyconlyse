#!/usr/bin/env python
"""
OWIS PS90 IP direct TCP test (no DS, no DLL).
Axis 1: move ±5 mm around initial position for 5 cycles.
"""

import time
import sys
from pathlib import Path

project_root = str(Path(__file__).resolve().parents[3])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from owis_ps90_tcp import OwisPS90TCP

IP = "10.20.30.134"
PORT = 8777
AXIS = 1

# Axis-1 stage parameters (from project config)
PITCH_MM_PER_REV = 1.0
STEPS_PER_REV = 200.0
GEAR_RATIO = 1.0

OFFSET_MM = 5.0
NUM_CYCLES = 5
POSITION_TOL_MM = 0.5
MOVE_TIMEOUT = 30.0
CHECK_INTERVAL = 0.2
SPEED_MM_S = 5.0
DRIVE_CURRENT_A = 2.5
HOLD_CURRENT_A = 0.5


def log(msg, indent=0):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {'  ' * indent}{msg}")


def to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def to_int(v, default=0):
    try:
        return int(float(v))
    except Exception:
        return default


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def axis_char_from_astat(astat, axis):
    idx = int(axis) - 1
    if not astat or idx < 0 or idx >= len(astat):
        return ""
    return astat[idx].upper()


def wait_not_moving(ctrl, axis, timeout=20.0, interval=0.1):
    t0 = time.time()
    while time.time() - t0 < timeout:
        ast = (ctrl.query("?ASTAT") or "").strip()
        if axis_char_from_astat(ast, axis) != "T":
            return ast
        time.sleep(interval)
    return (ctrl.query("?ASTAT") or "").strip()


def main():
    log("=" * 62)
    log("OWIS PS90 direct TCP oscillation test")
    log(f"Controller: {IP}:{PORT}, Axis: {AXIS}")
    log(f"Pattern: ±{OFFSET_MM} mm around initial position, {NUM_CYCLES} cycles")
    log("=" * 62)

    ctrl = OwisPS90TCP(ip=IP, port=PORT, timeout=5)
    if not ctrl.connect():
        log("FATAL: could not connect")
        return

    # Basic info
    log(f"Serial: {ctrl.get_serial_number()}", 1)
    log(f"Firmware: {ctrl.get_version()}", 1)
    log(f"Initial ASTAT: {ctrl.query('?ASTAT')}", 1)

    # Preflight: if axis already in transition, force stop and wait ready.
    ast0 = (ctrl.query("?ASTAT") or "").strip()
    if axis_char_from_astat(ast0, AXIS) == "T":
        log("Axis was already in transition; sending STOP before test", 1)
        ctrl.send_command(f"STOP{AXIS}", expect_response=False)
        ast_after = wait_not_moving(ctrl, AXIS, timeout=20.0)
        log(f"ASTAT after STOP: {ast_after}", 1)

    # Unit conversion from mm <-> counts.
    # On this setup, movement corresponds to stage units * microstep.
    microstep = to_float(ctrl.query(f"?MCSTP{AXIS}"), 1.0)
    if microstep <= 0:
        microstep = 1.0
    units_per_mm = (STEPS_PER_REV * GEAR_RATIO * microstep) / PITCH_MM_PER_REV

    def mm_to_counts(mm):
        return int(round(mm * units_per_mm))

    def counts_to_mm(cnt):
        return float(cnt) / units_per_mm

    tol_counts = mm_to_counts(POSITION_TOL_MM)
    delta_counts = mm_to_counts(OFFSET_MM)
    vel_counts_s = max(1, mm_to_counts(SPEED_MM_S))
    log(
        f"Conversion: microstep={microstep:.0f}, units/mm={units_per_mm:.1f}, "
        f"delta={delta_counts} counts",
        1,
    )

    # Initialize and power axis
    ctrl.send_command(f"AXIS{AXIS}=1", expect_response=False)
    ctrl.motor_init(AXIS)
    ctrl.motor_on(AXIS)
    ctrl.set_target_mode(AXIS, absolute=True)
    ctrl.set_velocity(AXIS, vel_counts_s)

    # Current setup:
    # low range (AMPSHNT=0): 2.4 A => 100%
    # high range (AMPSHNT=1): 5.45 A => 100% (effective capped at 66%)
    current_level = 0
    if DRIVE_CURRENT_A > 2.4:
        current_level = 1
    ctrl.send_command(f"AMPSHNT{AXIS}={current_level}", expect_response=False)

    if current_level == 0:
        drive_pct = clamp(int(round((DRIVE_CURRENT_A / 2.4) * 100.0)), 0, 100)
        hold_pct = clamp(int(round((HOLD_CURRENT_A / 2.4) * 100.0)), 0, 100)
    else:
        drive_pct = clamp(int(round((DRIVE_CURRENT_A / 5.45) * 100.0)), 0, 66)
        hold_pct = clamp(int(round((HOLD_CURRENT_A / 5.45) * 100.0)), 0, 66)

    ctrl.send_command(f"DRICUR{AXIS}={drive_pct}", expect_response=False)
    ctrl.send_command(f"HOLCUR{AXIS}={hold_pct}", expect_response=False)

    log(
        f"Speed set: {SPEED_MM_S:.2f} mm/s ({vel_counts_s} counts/s), "
        f"current level={current_level}, drive={drive_pct}%, hold={hold_pct}%",
        1,
    )
    log(f"Axis state after init: {ctrl.get_axis_state(AXIS)} (3=ON)", 1)

    initial_counts = to_int(ctrl.query(f"?CNT{AXIS}"))
    initial_mm = counts_to_mm(initial_counts)
    log(f"Initial position: {initial_counts} counts ({initial_mm:.3f} mm)", 1)

    plus_counts = initial_counts + delta_counts
    minus_counts = initial_counts - delta_counts
    log(
        f"Targets: {minus_counts} / {plus_counts} counts "
        f"({counts_to_mm(minus_counts):.3f} / {counts_to_mm(plus_counts):.3f} mm)",
        1,
    )
    log("")

    ok_moves = 0
    bad_moves = 0
    t_start = time.time()

    def move_and_wait(target_counts):
        ctrl.set_target(AXIS, target_counts)
        if not ctrl.go_target(AXIS):
            raise RuntimeError("go_target returned False")

        t0 = time.time()
        while time.time() - t0 < MOVE_TIMEOUT:
            pos = to_int(ctrl.query(f"?CNT{AXIS}"))
            err = abs(pos - target_counts)
            moving = ctrl.is_moving(AXIS)
            log(
                f"pos={pos} ({counts_to_mm(pos):.3f} mm), "
                f"err={err} counts, moving={moving}",
                2,
            )
            if not moving:
                return pos, err, time.time() - t0
            time.sleep(CHECK_INTERVAL)
        raise TimeoutError(f"move timeout {MOVE_TIMEOUT}s")

    try:
        for i in range(1, NUM_CYCLES + 1):
            log("-" * 62)
            log(f"Cycle {i}/{NUM_CYCLES}")
            log("-" * 62)
            for label, target in [("+ side", plus_counts), ("- side", minus_counts)]:
                log(f"Move to {label}: {target} counts ({counts_to_mm(target):.3f} mm)", 1)
                try:
                    _pos, err, dt = move_and_wait(target)
                    if err <= tol_counts:
                        log(f"OK reached in {dt:.1f}s (final err={err} counts)", 2)
                        ok_moves += 1
                    else:
                        log(f"BAD final err={err} counts in {dt:.1f}s", 2)
                        bad_moves += 1
                except Exception as e:
                    bad_moves += 1
                    log(f"ERROR: {e}", 2)
            log("")

        # Return to initial position
        log("=" * 62)
        log(f"Returning to initial position: {initial_counts} counts ({initial_mm:.3f} mm)")
        try:
            _pos, err, dt = move_and_wait(initial_counts)
            log(f"Return done in {dt:.1f}s, final err={err} counts", 1)
        except Exception as e:
            log(f"Return ERROR: {e}", 1)

    finally:
        log("Stopping axis before shutdown...")
        ctrl.send_command(f"STOP{AXIS}", expect_response=False)
        ast_end = wait_not_moving(ctrl, AXIS, timeout=20.0)
        log(f"ASTAT before motor_off: {ast_end}", 1)
        log("Motor off and disconnecting...")
        ctrl.motor_off(AXIS)
        ctrl.disconnect()

    total = time.time() - t_start
    attempted = NUM_CYCLES * 2
    log("")
    log("=" * 62)
    log("SUMMARY")
    log(f"Moves attempted: {attempted}")
    log(f"Successful: {ok_moves}")
    log(f"Failed: {bad_moves}")
    log(f"Total time: {total:.1f}s")
    log("=" * 62)
    if bad_moves == 0:
        log("ALL MOVES PASSED")
    else:
        log(f"{bad_moves} MOVE(S) FAILED")
    log("=" * 62)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nInterrupted by user")
    except Exception as exc:
        log(f"\nFATAL ERROR: {exc}")
        import traceback
        traceback.print_exc()
