#!/usr/bin/env python
from __future__ import print_function

import argparse
import json
import socket
import sys
import uuid

from elyse_agent.protocol import recv_message, send_message


def main(argv=None):
    parser = argparse.ArgumentParser(description="ELYSE acquisition agent client")
    parser.add_argument("command", choices=(
        "ping", "initialize", "get_status", "get_capabilities",
        "get_channel_summary", "discover_hardware", "describe_legacy_tasks",
        "get_snapshot", "set_simulation_scenario", "advance_simulation",
        "get_psp_catalog", "get_psp_snapshot",
        "set_simulated_digital_output", "set_simulated_analog_output",
        "set_simulated_counter_output", "reset_simulated_outputs",
    ))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--scenario", choices=("idle", "beam_ready", "fault"))
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--task")
    parser.add_argument("--index", type=int)
    parser.add_argument("--value")
    parser.add_argument("--volts", type=float)
    parser.add_argument("--counter", type=int)
    parser.add_argument("--delay", type=float)
    parser.add_argument("--width", type=float)
    parser.add_argument("--enabled", choices=("true", "false"))
    args = parser.parse_args(argv)
    sock = socket.create_connection((args.host, args.port), timeout=10.0)
    try:
        params = {}
        if args.command == "set_simulation_scenario":
            if args.scenario is None:
                parser.error("--scenario is required for set_simulation_scenario")
            params["name"] = args.scenario
        if args.command == "advance_simulation":
            if args.seconds is None:
                parser.error("--seconds is required for advance_simulation")
            params["seconds"] = args.seconds
        if args.command == "set_simulated_digital_output":
            if args.task is None or args.index is None or args.value not in ("true", "false"):
                parser.error("--task, --index, and --value true|false are required")
            params.update({"task": args.task, "index": args.index, "value": args.value == "true"})
        if args.command == "set_simulated_analog_output":
            if args.task is None or args.index is None or args.volts is None:
                parser.error("--task, --index, and --volts are required")
            params.update({"task": args.task, "index": args.index, "value_volts": args.volts})
        if args.command == "set_simulated_counter_output":
            if None in (args.counter, args.delay, args.width) or args.enabled is None:
                parser.error("--counter, --delay, --width, and --enabled true|false are required")
            params.update(
                {
                    "counter": args.counter,
                    "delay_seconds": args.delay,
                    "width_seconds": args.width,
                    "enabled": args.enabled == "true",
                }
            )
        send_message(
            sock,
            {"id": str(uuid.uuid4()), "command": args.command, "params": params},
        )
        response = recv_message(sock, 1048576)
    finally:
        sock.close()
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
