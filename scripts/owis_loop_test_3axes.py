#!/usr/bin/env python3
"""OWIS loop test for 3-axis DS_OWIS_PS90_IP.

Pattern (safe, non-drifting):
  For each cycle:
    1) Move ALL axes (1,2,3) by +5 mm from their initial positions
    2) Move ALL axes back to initial positions
"""

import ast
import time
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from tango import Database, DeviceProxy

TANGO_DEVICE = "manip/general/DS_OWIS_PS90_IP"
AXES = [1, 2, 3]
CYCLES = 10
DELTA_MM = 5.0
POS_TOL_MM = 0.8
MOVE_TIMEOUT_S = 60
POLL_S = 0.5
CMD_RETRIES = 8


_DEV: Optional[DeviceProxy] = None


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def _new_proxy() -> DeviceProxy:
    dev = DeviceProxy(TANGO_DEVICE)
    dev.set_timeout_millis(30000)
    return dev


def _reset_proxy() -> None:
    global _DEV
    _DEV = None


def _proxy() -> DeviceProxy:
    global _DEV
    if _DEV is None:
        _DEV = _new_proxy()
    return _DEV


def _short_err(err: Exception) -> str:
    text = str(err).strip()
    return text.splitlines()[0] if text else repr(err)


def call_with_retry(label: str, fn: Callable[[DeviceProxy], Any], retries: int = CMD_RETRIES):
    last_err: Optional[Exception] = None
    for i in range(retries):
        try:
            return fn(_proxy())
        except Exception as err:  # pragma: no cover - hardware runtime path
            last_err = err
            log(f"{label} retry {i + 1}/{retries}: {_short_err(err)}")
            _reset_proxy()
            time.sleep(0.5)
    raise RuntimeError(f"{label} failed after {retries} retries: {_short_err(last_err)}")


def read_pos(axis: int) -> float:
    return float(call_with_retry(f"read pos{axis}", lambda dev: dev.read_attribute(f"pos{axis}").value))


def move_abs(axis: int, target: float):
    return call_with_retry(
        f"move axis {axis} to {target:.3f}",
        lambda dev: dev.move_axis([float(axis), float(target)]),
    )


def wait_target(axis: int, target: float, timeout_s: float):
    t0 = time.time()
    last_pos = None
    while time.time() - t0 < timeout_s:
        try:
            last_pos = read_pos(axis)
            if abs(last_pos - target) <= POS_TOL_MM:
                return True, last_pos, time.time() - t0
        except Exception:
            pass
        time.sleep(POLL_S)
    return False, last_pos, time.time() - t0


def get_limits() -> Dict[int, Dict[str, float]]:
    db = Database()
    props = db.get_device_property(TANGO_DEVICE, ["delay_lines_parameters"])
    data = ast.literal_eval(props["delay_lines_parameters"][0])
    limits: Dict[int, Dict[str, float]] = {}
    for axis in AXES:
        limits[axis] = {
            "min": float(data[axis]["limit_min"]),
            "max": float(data[axis]["limit_max"]),
        }
    return limits


def main() -> None:
    state = call_with_retry("read state", lambda dev: dev.state())
    pos_start_raw = call_with_retry("read positions", lambda dev: dev.positions)
    friendly = call_with_retry("read friendly_names", lambda dev: dev.friendly_names)
    log(f"device={TANGO_DEVICE}")
    log(f"state={state}")
    log(f"positions_start={pos_start_raw}")
    log(f"friendly={friendly}")

    starts: Dict[int, float] = {}
    for axis in AXES:
        starts[axis] = read_pos(axis)
        log(f"axis {axis} start={starts[axis]:.3f} mm")

    limits = get_limits()
    plus_targets: Dict[int, float] = {}
    for axis in AXES:
        target = starts[axis] + DELTA_MM
        amin = limits[axis]["min"]
        amax = limits[axis]["max"]
        if not (amin <= target <= amax):
            raise RuntimeError(
                f"axis {axis}: target {target:.3f} out of limits [{amin:.3f}, {amax:.3f}]"
            )
        plus_targets[axis] = target

    ok_cycles = 0
    for cycle in range(1, CYCLES + 1):
        log(f"--- cycle {cycle}/{CYCLES}: ALL AXES PLUS ---")
        for axis in AXES:
            cmd = move_abs(axis, plus_targets[axis])
            log(f"axis {axis} PLUS cmd={cmd}")

        plus_ok = True
        for axis in AXES:
            ok, pos, dt = wait_target(axis, plus_targets[axis], MOVE_TIMEOUT_S)
            log(f"axis {axis} PLUS done ok={ok} pos={pos} dt={dt:.1f}s")
            if not ok:
                plus_ok = False

        log(f"--- cycle {cycle}/{CYCLES}: ALL AXES BACK ---")
        for axis in AXES:
            cmd = move_abs(axis, starts[axis])
            log(f"axis {axis} BACK cmd={cmd}")

        back_ok = True
        for axis in AXES:
            ok, pos, dt = wait_target(axis, starts[axis], MOVE_TIMEOUT_S)
            log(f"axis {axis} BACK done ok={ok} pos={pos} dt={dt:.1f}s")
            if not ok:
                back_ok = False

        if plus_ok and back_ok:
            ok_cycles += 1

    pos_end = call_with_retry("read final positions", lambda dev: dev.positions)
    state_end = call_with_retry("read final state", lambda dev: dev.state())
    log(f"positions_end={pos_end}")
    log(f"state_end={state_end}")
    log(f"SUMMARY cycles_ok={ok_cycles}/{CYCLES}")


if __name__ == "__main__":
    main()
