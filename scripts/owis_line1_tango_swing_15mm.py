#!/usr/bin/env python3
"""Tango-only OWIS axis-1 swing test: +15 mm, -15 mm, return to start."""

from __future__ import annotations

import argparse
import time
from datetime import datetime

from tango import DeviceProxy


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def read_pos(dev: DeviceProxy, axis: int) -> float:
    return float(dev.read_attribute(f"pos{axis}").value)


def move_abs(dev: DeviceProxy, axis: int, target: float) -> str:
    return str(dev.move_axis([float(axis), float(target)]))


def wait_target(
    dev: DeviceProxy,
    axis: int,
    target: float,
    tol_mm: float,
    timeout_s: float,
    poll_s: float,
) -> tuple[bool, float, float]:
    t0 = time.time()
    last = float("nan")
    while time.time() - t0 < timeout_s:
        last = read_pos(dev, axis)
        if abs(last - target) <= tol_mm:
            return True, last, time.time() - t0
        time.sleep(poll_s)
    return False, last, time.time() - t0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="manip/general/DS_OWIS_PS90_IP")
    parser.add_argument("--axis", type=int, default=1)
    parser.add_argument("--offset-mm", type=float, default=15.0)
    parser.add_argument("--tol-mm", type=float, default=0.5)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--poll-s", type=float, default=0.05)
    args = parser.parse_args()

    dev = DeviceProxy(args.device)
    dev.set_timeout_millis(30000)

    axis = int(args.axis)
    offset = float(args.offset_mm)
    tol = float(args.tol_mm)
    timeout = float(args.timeout_s)
    poll = float(args.poll_s)

    start = read_pos(dev, axis)
    target_plus = start + offset
    target_minus = start - offset

    log(f"device={args.device}, axis={axis}")
    log(f"start={start:.4f} mm")
    log(f"targets: plus={target_plus:.4f} mm, minus={target_minus:.4f} mm, return={start:.4f} mm")

    ok = True
    t_global = time.time()

    try:
        log("MOVE +15 mm")
        cmd = move_abs(dev, axis, target_plus)
        log(f"move_axis response={cmd}")
        done, pos, dt = wait_target(dev, axis, target_plus, tol, timeout, poll)
        log(f"done={done} dt={dt:.2f}s pos={pos:.4f} mm")
        ok = ok and done

        log("MOVE -15 mm")
        cmd = move_abs(dev, axis, target_minus)
        log(f"move_axis response={cmd}")
        done, pos, dt = wait_target(dev, axis, target_minus, tol, timeout, poll)
        log(f"done={done} dt={dt:.2f}s pos={pos:.4f} mm")
        ok = ok and done
    finally:
        log("RETURN to start")
        cmd = move_abs(dev, axis, start)
        log(f"move_axis response={cmd}")
        done, pos, dt = wait_target(dev, axis, start, tol, timeout, poll)
        log(f"done={done} dt={dt:.2f}s pos={pos:.4f} mm")
        ok = ok and done

    total = time.time() - t_global
    log(f"SUMMARY ok={ok} total={total:.2f}s")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
