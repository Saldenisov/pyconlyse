"""Small Tango client; default action reads status and counters only."""

from __future__ import annotations

import argparse
import json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("device", help="Registered Tango domain/family/member")
    parser.add_argument(
        "action",
        choices=("status", "relative", "absolute", "stop", "abort", "reconnect"),
        nargs="?",
        default="status",
    )
    parser.add_argument("--axis", type=int, choices=range(1, 5))
    parser.add_argument("--steps", type=int)
    args = parser.parse_args(argv)
    if args.action in ("relative", "absolute") and (
        args.axis is None or args.steps is None
    ):
        parser.error("Motion needs --axis and --steps")
    if args.action == "stop" and args.axis is None:
        parser.error("Stop needs --axis")
    from tango import DeviceProxy

    proxy = DeviceProxy(args.device)
    proxy.set_timeout_millis(15000)
    if args.action in ("relative", "absolute"):
        name = "MoveRelative" if args.action == "relative" else "MoveAbsolute"
        proxy.command_inout(name, [args.axis, args.steps])
        print("Command accepted; completion is pending")
    elif args.action == "stop":
        proxy.command_inout("Stop", args.axis)
        print("Stop requested; confirm idle with status")
    elif args.action in ("abort", "reconnect"):
        proxy.command_inout(args.action.capitalize())
    else:
        report = {"state": str(proxy.state()), "status": proxy.status()}
        for name in (
            "identification",
            "positions_steps",
            "motion_done",
            "sample_time",
            "last_error",
        ):
            try:
                value = proxy.read_attribute(name).value
                report[name] = value.tolist() if hasattr(value, "tolist") else value
            except Exception as exc:
                report[name] = {"invalid": str(exc)}
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
