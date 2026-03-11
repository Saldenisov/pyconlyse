#!/usr/bin/env python3
"""Interactive Tango-only OWIS axis calibration helper for caliper checks.

Use cases:
1) Sequence mode: +10, +20, +30 mm (each with manual Start/Return).
2) Quick mode: single +40 mm (manual Start/Return).
"""

from __future__ import annotations

import argparse
import ast
import time
from datetime import datetime
from typing import Optional

from tango import DeviceProxy


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(msg: str) -> None:
    print(f"[{ts()}] {msg}", flush=True)


def read_pos(dev: DeviceProxy, axis: int) -> float:
    return float(dev.read_attribute(f"pos{axis}").value)


def move_abs(dev: DeviceProxy, axis: int, target_mm: float) -> str:
    return str(dev.move_axis([float(axis), float(target_mm)]))


def wait_target(
    dev: DeviceProxy,
    axis: int,
    target_mm: float,
    tol_mm: float,
    timeout_s: float,
    poll_s: float,
) -> tuple[bool, float, float]:
    t0 = time.time()
    last = float("nan")
    while time.time() - t0 < timeout_s:
        last = read_pos(dev, axis)
        if abs(last - target_mm) <= tol_mm:
            return True, last, time.time() - t0
        time.sleep(poll_s)
    return False, last, time.time() - t0


def wait_user(prompt: str) -> str:
    value = input(prompt).strip().lower()
    if value in {"q", "quit", "exit"}:
        raise KeyboardInterrupt("User requested exit")
    return value


def get_axis_limits_from_property(dev: DeviceProxy, axis: int) -> tuple[Optional[float], Optional[float]]:
    try:
        props = dev.get_property("delay_lines_parameters")
        raw = props.get("delay_lines_parameters", [])
        if not raw:
            return None, None
        data = ast.literal_eval(raw[0])
        item = data.get(axis)
        if not isinstance(item, dict):
            return None, None
        mn = item.get("limit_min")
        mx = item.get("limit_max")
        return (float(mn), float(mx))
    except Exception:
        return None, None


def check_target_within_limits(target: float, mn: Optional[float], mx: Optional[float]) -> None:
    if mn is None or mx is None:
        return
    if not (mn <= target <= mx):
        raise ValueError(f"Target {target:.4f} mm is outside limits [{mn:.4f}, {mx:.4f}]")


def run_single_offset(
    dev: DeviceProxy,
    axis: int,
    start_mm: float,
    offset_mm: float,
    tol_mm: float,
    timeout_s: float,
    poll_s: float,
    limit_min: Optional[float],
    limit_max: Optional[float],
) -> None:
    target = start_mm + offset_mm
    check_target_within_limits(target, limit_min, limit_max)
    check_target_within_limits(start_mm, limit_min, limit_max)

    wait_user(
        f"\n[{offset_mm:.1f} mm] Нажмите Enter для НАЧАТЬ (или q для выхода): "
    )
    log(f"Двигаю ось {axis} на +{offset_mm:.1f} мм: target={target:.4f} мм")
    resp = move_abs(dev, axis, target)
    log(f"move_axis response={resp}")
    ok, pos, dt = wait_target(dev, axis, target, tol_mm, timeout_s, poll_s)
    log(f"Движение завершено: ok={ok}, dt={dt:.2f}s, pos={pos:.4f} мм")

    wait_user(
        f"[{offset_mm:.1f} mm] Нажмите Enter для ВЕРНУТЬ в старт (или q для выхода): "
    )
    log(f"Возвращаю ось {axis} в старт: target={start_mm:.4f} мм")
    resp = move_abs(dev, axis, start_mm)
    log(f"move_axis response={resp}")
    ok, pos, dt = wait_target(dev, axis, start_mm, tol_mm, timeout_s, poll_s)
    log(f"Возврат завершен: ok={ok}, dt={dt:.2f}s, pos={pos:.4f} мм")


def parse_offsets(raw: str) -> list[float]:
    values: list[float] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        values.append(float(token))
    if not values:
        raise ValueError("No offsets parsed from --offsets")
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="manip/general/DS_OWIS_PS90_IP")
    parser.add_argument("--axis", type=int, default=1)
    parser.add_argument("--tol-mm", type=float, default=0.5)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--poll-s", type=float, default=0.05)
    parser.add_argument(
        "--offsets",
        default="10,20,30",
        help="Comma-separated positive offsets in mm for sequence mode.",
    )
    parser.add_argument(
        "--mode",
        choices=("sequence", "quick40"),
        default="sequence",
        help="sequence => offsets list, quick40 => single +40 mm",
    )
    args = parser.parse_args()

    dev = DeviceProxy(args.device)
    dev.set_timeout_millis(30000)

    axis = int(args.axis)
    start = read_pos(dev, axis)
    limit_min, limit_max = get_axis_limits_from_property(dev, axis)

    log(f"device={args.device}, axis={axis}, state={dev.state()}")
    log(f"start={start:.4f} мм")
    if limit_min is not None and limit_max is not None:
        log(f"limits=[{limit_min:.4f}, {limit_max:.4f}] мм")

    if args.mode == "quick40":
        offsets = [40.0]
    else:
        offsets = parse_offsets(args.offsets)

    log(f"planned offsets: {offsets}")
    log("Команды: Enter = продолжить, q = выход.")

    try:
        for offset in offsets:
            run_single_offset(
                dev=dev,
                axis=axis,
                start_mm=start,
                offset_mm=float(offset),
                tol_mm=float(args.tol_mm),
                timeout_s=float(args.timeout_s),
                poll_s=float(args.poll_s),
                limit_min=limit_min,
                limit_max=limit_max,
            )
    except KeyboardInterrupt:
        log("Остановлено пользователем.")
        return 130

    log("Готово: все шаги выполнены.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
