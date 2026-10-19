#!/usr/bin/env python
from __future__ import print_function

import argparse
import json
import socket
import time
import uuid

from elyse_agent.protocol import recv_message, send_message


def request(sock, command, params=None):
    message = {
        "id": str(uuid.uuid4()),
        "command": command,
        "params": params or {},
    }
    send_message(sock, message)
    response = recv_message(sock, 1048576)
    if not response.get("ok"):
        raise RuntimeError(json.dumps(response["error"], sort_keys=True))
    return response["result"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read simulated ELYSE telemetry over TCP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--scenario", choices=("idle", "beam_ready", "fault"), default="idle")
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--interval", type=float, default=0.2)
    args = parser.parse_args(argv)
    if args.count < 1 or args.interval < 0:
        parser.error("count must be positive and interval must be non-negative")

    sock = socket.create_connection((args.host, args.port), timeout=10.0)
    try:
        request(sock, "initialize")
        request(sock, "set_simulation_scenario", {"name": args.scenario})
        for unused in range(args.count):
            snapshot = request(sock, "get_snapshot")
            compact = {
                "sequence": snapshot["sequence"],
                "state": snapshot["acquisition_state"],
                "scenario": snapshot["scenario"],
                "simulation_time_seconds": snapshot["simulation_time_seconds"],
                "environment": snapshot["environment"],
                "alarms": snapshot["alarms"],
                "C1_ai0": snapshot["analog_inputs"]["C1_NI6071E_AI"][0],
                "C3_di0": snapshot["digital_inputs"]["C3_DIO96_DI"][0],
            }
            print(json.dumps(compact, sort_keys=True))
            time.sleep(args.interval)
    finally:
        sock.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
