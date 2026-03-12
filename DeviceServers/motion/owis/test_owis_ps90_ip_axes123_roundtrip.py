#!/usr/bin/env python3
"""OWIS PS90 IP Tango test for axes 1,2,3 roundtrip sequence.

Sequence per cycle:
1) Move axis 1, then 2, then 3 to (start + delta_mm)
2) Wait until all three reach targets
3) Move axis 1, then 2, then 3 back to start positions
4) Wait until all three return

No artificial dwell delays between move commands.
"""

from __future__ import annotations

import argparse
import ast
import os
import time
from typing import Dict, List, Tuple

from tango import DeviceProxy


def _log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def _parse_axes(raw: str) -> List[int]:
    axes: List[int] = []
    for token in str(raw).split(","):
        token = token.strip()
        if not token:
            continue
        axis = int(token)
        if axis <= 0:
            raise ValueError(f"Axis must be > 0, got {axis}")
        axes.append(axis)
    if not axes:
        raise ValueError("No axes provided")
    return axes


def _parse_positions_attr(raw) -> Dict[int, float]:
    if isinstance(raw, dict):
        parsed = raw
    elif isinstance(raw, str):
        parsed = ast.literal_eval(raw)
    else:
        return {}

    if not isinstance(parsed, dict):
        return {}

    out: Dict[int, float] = {}
    for key, value in parsed.items():
        try:
            out[int(key)] = float(value)
        except Exception:
            continue
    return out


def read_positions(device: DeviceProxy, axes: List[int]) -> Dict[int, float]:
    pos = _parse_positions_attr(device.positions)

    # Fallback to per-axis attributes if needed.
    for axis in axes:
        if axis in pos:
            continue
        attr_name = f"pos{axis}"
        try:
            pos[axis] = float(getattr(device, attr_name))
        except Exception as exc:
            raise RuntimeError(
                f"Could not read position for axis {axis} via positions/{attr_name}: {exc}"
            ) from exc

    return {axis: pos[axis] for axis in axes}


def send_moves(device: DeviceProxy, targets: Dict[int, float], ordered_axes: List[int]) -> None:
    for axis in ordered_axes:
        target = float(targets[axis])
        _log(f"move_axis([{axis}, {target:.3f}])")
        res = device.move_axis([axis, target])
        if str(res) != "0":
            raise RuntimeError(f"move_axis for axis {axis} failed: {res}")


def wait_targets(
    device: DeviceProxy,
    targets: Dict[int, float],
    tol_mm: float,
    timeout_s: float,
    poll_s: float,
) -> Tuple[bool, Dict[int, float], float]:
    start = time.time()
    while True:
        current = read_positions(device, list(targets.keys()))
        pending = [
            axis
            for axis, target in targets.items()
            if abs(current[axis] - target) > tol_mm
        ]
        if not pending:
            return True, current, time.time() - start

        elapsed = time.time() - start
        if elapsed >= timeout_s:
            return False, current, elapsed

        time.sleep(max(0.01, poll_s))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Roundtrip test for OWIS TCP/IP controller via Tango DS"
    )
    parser.add_argument(
        "--device",
        default="manip/general/DS_OWIS_PS90_IP",
        help="Tango device name (default: manip/general/DS_OWIS_PS90_IP)",
    )
    parser.add_argument(
        "--axes",
        default="1,2,3",
        help="Comma-separated axes list (default: 1,2,3)",
    )
    parser.add_argument(
        "--delta-mm",
        type=float,
        default=5.0,
        help="Forward shift in mm for each axis (default: 5.0)",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=2,
        help="Number of forward/back cycles (default: 2)",
    )
    parser.add_argument(
        "--tol-mm",
        type=float,
        default=0.10,
        help="Position tolerance in mm (default: 0.10)",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=180.0,
        help="Timeout per forward/back phase in seconds (default: 180)",
    )
    parser.add_argument(
        "--poll-s",
        type=float,
        default=0.05,
        help="Polling interval while waiting for targets (default: 0.05)",
    )
    args = parser.parse_args()

    axes = _parse_axes(args.axes)
    if args.cycles <= 0:
        raise ValueError("--cycles must be > 0")

    tango_host = os.environ.get("TANGO_HOST", "<not set>")
    _log("=" * 68)
    _log("OWIS PS90 IP axes roundtrip test (Tango)")
    _log(f"TANGO_HOST: {tango_host}")
    _log(f"Device: {args.device}")
    _log(f"Axes: {axes}")
    _log(f"Delta: +{args.delta_mm:.3f} mm")
    _log(f"Cycles: {args.cycles}")
    _log("=" * 68)

    device = DeviceProxy(args.device)

    # Best effort to ensure the controller is ON.
    try:
        device.ensure_on()
    except Exception:
        pass

    start_pos = read_positions(device, axes)
    _log(
        "Start positions: "
        + ", ".join(f"a{axis}={start_pos[axis]:.3f}" for axis in axes)
    )

    for cycle in range(1, args.cycles + 1):
        _log("-" * 68)
        _log(f"Cycle {cycle}/{args.cycles}: forward (+{args.delta_mm:.3f} mm)")

        forward_targets = {axis: start_pos[axis] + args.delta_mm for axis in axes}
        send_moves(device, forward_targets, axes)

        ok, cur, dt = wait_targets(
            device,
            forward_targets,
            tol_mm=args.tol_mm,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        if not ok:
            raise TimeoutError(
                "Forward phase timeout. "
                + ", ".join(
                    f"a{axis}: cur={cur[axis]:.3f}, target={forward_targets[axis]:.3f}"
                    for axis in axes
                )
            )
        _log(f"Forward reached in {dt:.2f}s")

        _log(f"Cycle {cycle}/{args.cycles}: return (to start)")
        send_moves(device, start_pos, axes)

        ok, cur, dt = wait_targets(
            device,
            start_pos,
            tol_mm=args.tol_mm,
            timeout_s=args.timeout_s,
            poll_s=args.poll_s,
        )
        if not ok:
            raise TimeoutError(
                "Return phase timeout. "
                + ", ".join(
                    f"a{axis}: cur={cur[axis]:.3f}, target={start_pos[axis]:.3f}"
                    for axis in axes
                )
            )
        _log(f"Return reached in {dt:.2f}s")

    final_pos = read_positions(device, axes)
    _log("=" * 68)
    _log(
        "Final positions: "
        + ", ".join(f"a{axis}={final_pos[axis]:.3f}" for axis in axes)
    )
    _log(
        "Total drift from start: "
        + ", ".join(
            f"a{axis}={final_pos[axis] - start_pos[axis]:+.4f} mm" for axis in axes
        )
    )
    _log("Test PASSED")
    _log("=" * 68)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
