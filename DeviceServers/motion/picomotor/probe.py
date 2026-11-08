"""Read controller identification and counters without issuing any movement."""

from __future__ import annotations

import argparse
import json

from DeviceServers.motion.picomotor.transport import Picomotor8742


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=23)
    parser.add_argument("--address", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=1.0)
    args = parser.parse_args(argv)
    controller = Picomotor8742(
        args.host,
        port=args.port,
        timeout_s=args.timeout,
        controller_address=args.address,
    )
    try:
        report = {
            "identification": controller.connect(),
            "host": args.host,
            "port": args.port,
            "controller_address": args.address,
        }
        report["positions_steps"] = [controller.position(axis) for axis in range(1, 5)]
        report["motion_done"] = [controller.motion_done(axis) for axis in range(1, 5)]
        print(json.dumps(report, indent=2))
    finally:
        controller.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
