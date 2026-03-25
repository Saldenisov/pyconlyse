#!/usr/bin/env python3
"""Monitor incoming payloads on manip/general/PSP and log message structure."""

import argparse
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from tango import DeviceProxy


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor PSP Tango payloads.")
    parser.add_argument(
        "--device",
        default="manip/general/PSP",
        help="Tango device name (default: manip/general/PSP)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.4,
        help="Polling interval in seconds (default: 0.4)",
    )
    parser.add_argument(
        "--log-file",
        default="",
        help="Output log path. If omitted, auto-generated under logs/.",
    )
    return parser.parse_args()


def _ensure_log_path(raw_path: str) -> Path:
    if raw_path:
        path = Path(raw_path).expanduser().resolve()
    else:
        logs_dir = Path.cwd() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = (logs_dir / f"psp_monitor_{stamp}.log").resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> int:
    args = _parse_args()
    log_path = _ensure_log_path(args.log_file)

    tango_host = os.environ.get("TANGO_HOST", "")
    with log_path.open("a", encoding="utf-8") as logf:
        logf.write(f"[{_now_iso()}] monitor_start\n")
        logf.write(f"device={args.device}\n")
        logf.write(f"interval={args.interval}\n")
        logf.write(f"TANGO_HOST={tango_host}\n")
        logf.flush()

        dev = DeviceProxy(args.device)
        last_count = int(dev.read_attribute("messages_received").value)
        key_counter: Counter[str] = Counter()
        parse_error_count = 0

        logf.write(f"[{_now_iso()}] initial_messages_received={last_count}\n")
        logf.flush()
        print(f"Monitoring {args.device}, starting count={last_count}")
        print(f"Log file: {log_path}")

        while True:
            try:
                count = int(dev.read_attribute("messages_received").value)
                if count > last_count:
                    delta = count - last_count
                    payload = str(dev.read_attribute("last_payload").value)
                    ts = float(dev.read_attribute("last_timestamp").value)
                    line = f"[{_now_iso()}] msg#{count} delta={delta} ts={ts} payload={payload}\n"
                    logf.write(line)

                    try:
                        obj = json.loads(payload)
                        if isinstance(obj, dict):
                            for key in obj.keys():
                                key_counter[key] += 1
                            logf.write(
                                f"[{_now_iso()}] msg#{count} json_keys={sorted(obj.keys())}\n"
                            )
                        else:
                            logf.write(
                                f"[{_now_iso()}] msg#{count} json_type={type(obj).__name__}\n"
                            )
                    except Exception:
                        parse_error_count += 1
                        logf.write(f"[{_now_iso()}] msg#{count} json_parse=error\n")

                    last_count = count

                    logf.write(
                        f"[{_now_iso()}] summary total={last_count} parse_errors={parse_error_count} key_freq={dict(key_counter)}\n"
                    )
                    logf.flush()

                time.sleep(args.interval)
            except KeyboardInterrupt:
                logf.write(f"[{_now_iso()}] monitor_stop keyboard_interrupt\n")
                logf.flush()
                print("Stopped.")
                return 0
            except Exception as exc:
                logf.write(f"[{_now_iso()}] monitor_error {type(exc).__name__}: {exc}\n")
                logf.flush()
                time.sleep(max(0.5, args.interval))


if __name__ == "__main__":
    sys.exit(main())
