#!/usr/bin/env python
from __future__ import print_function

import argparse
import os
import sys

from elyse_agent.audit import AuditLog
from elyse_agent.channel_registry import ChannelRegistry
from elyse_agent.commands import CommandRouter
from elyse_agent.config import load_config
from elyse_agent.daqmx_backend import DaqmxBackend
from elyse_agent.service import AgentServer
from elyse_agent.simulator import SimulatedBackend
from elyse_agent.state import AgentState


def build_agent(config, supervision_options=None, telemetry_options=None):
    if telemetry_options is not None and supervision_options:
        raise ValueError("LabVIEW telemetry cannot enable Supervision commands")
    if telemetry_options is not None and config["bind_host"] not in ("127.0.0.1", "0.0.0.0"):
        raise ValueError("LabVIEW telemetry listener must accept loopback: bind 127.0.0.1 or explicit 0.0.0.0")
    if supervision_options and (config["mode"] != "simulation" or config["bind_host"] not in ("127.0.0.1", "10.20.30.10")):
        raise ValueError("Supervision requires simulation mode and an explicit permitted bind address")
    audit = AuditLog(config["audit_path"])
    registry = ChannelRegistry(config["data_path"]).load()
    if telemetry_options is not None:
        # No backend exists in this mode: even a routing regression cannot
        # discover NI devices or create a second hardware owner.
        backend = None
        config = dict(config, mode="labview_telemetry", allow_input_task_creation=False)
    elif config["mode"] == "simulation":
        backend = SimulatedBackend()
    else:
        backend = DaqmxBackend(allow_hardware_writes=False)
    state = AgentState(config)
    router = CommandRouter(backend, state, registry, audit)
    if telemetry_options is not None:
        from elyse_agent.labview_telemetry import LabviewTelemetryStore
        router.labview_telemetry = LabviewTelemetryStore(**telemetry_options)
    server = AgentServer(
        (config["bind_host"], config["command_port"]),
        router,
        config["max_frame_bytes"],
        config["socket_timeout_seconds"],
    )
    if supervision_options:
        # Extend the existing agent/listener; do not create another server.
        from elyse_agent.supervision_rpc import SupervisionEndpoint
        from elyse_agent.supervision_runtime import SupervisionRuntime
        runtime = None
        try:
            def procedure_step(index, step):
                backend.assert_procedure_ready()
                hook = supervision_options.get("step_hook")
                if hook:
                    hook(index, step)

            runtime = SupervisionRuntime(supervision_options["state_db"],
                                         time_scale=supervision_options["time_scale"],
                                         step_hook=procedure_step, simulate_all_plans=True, simulate_setpoints=True,
                                         simulate_lifecycle=True)
            router.supervision = SupervisionEndpoint(runtime, supervision_options["key"])
            backend.supervision = runtime
        except Exception:
            server.server_close()
            if runtime:
                runtime.close()
            raise
    return server, audit


def parse_args(argv):
    parser = argparse.ArgumentParser(description="ELYSE acquisition XP agent")
    parser.add_argument(
        "--config",
        default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.xp.json"),
        help="path to JSON configuration",
    )
    parser.add_argument(
        "--discover-once",
        action="store_true",
        help="enumerate NI-DAQmx devices without creating tasks, print JSON, and exit",
    )
    parser.add_argument(
        "--initialize-simulation",
        action="store_true",
        help="initialize the non-hardware simulation before serving",
    )
    parser.add_argument("--supervision", action="store_true", help="enable signed supervision in this simulation agent")
    parser.add_argument("--labview-telemetry", action="store_true",
                        help="receive copied LabVIEW telemetry only; disable all backend commands")
    parser.add_argument("--telemetry-session", default="acq-copy-20261012",
                        help="expected producer session; change and restart receiver after producer restart")
    parser.add_argument("--bind", choices=("127.0.0.1", "10.20.30.10", "0.0.0.0"),
                        help="explicit bind override; wildcard requires telemetry-only mode")
    parser.add_argument("--port", type=int, help="port override; 0 only for loopback tests")
    parser.add_argument("--state-db", default=os.path.join(os.path.dirname(__file__), "runtime", "supervision.sqlite3"))
    parser.add_argument("--audit-path", help="optional local audit journal path")
    parser.add_argument("--key-file", default=os.environ.get("ELYSE_ACQ_SHARED_KEY_FILE"))
    parser.add_argument("--time-scale", type=float, default=1.0, help="simulation wait scale, 0..1")
    parser.add_argument("--simulate-failure-step", type=int, help="local software-only fault injection")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config = load_config(args.config)
    if args.audit_path:
        config["audit_path"] = os.path.abspath(args.audit_path)
    if args.bind:
        config["bind_host"] = args.bind
    if args.port is not None:
        if not 0 <= args.port <= 65535 or (args.port == 0 and config["bind_host"] != "127.0.0.1"):
            raise ValueError("port must be in 1..65535; 0 permitted only on loopback")
        config["command_port"] = args.port
    options = None
    telemetry_options = None
    if args.bind == "0.0.0.0" and not args.labview_telemetry:
        raise ValueError("Wildcard bind override requires telemetry-only mode")
    if args.labview_telemetry:
        if args.supervision or args.discover_once or args.initialize_simulation:
            raise ValueError("LabVIEW telemetry mode cannot initialize/discover hardware or run simulation")
        telemetry_options = dict(session_id=args.telemetry_session)
    if args.supervision:
        if args.key_file:
            with open(args.key_file, "rb") as stream:
                key = stream.read().strip()
        else:
            key = os.environ.get("ELYSE_ACQ_SHARED_KEY", "").encode("utf-8")
        from elyse_agent.supervision_wire import validate_key
        validate_key(key)
        if args.simulate_failure_step is not None and not 0 <= args.simulate_failure_step < 100:
            raise ValueError("simulate-failure-step must be in 0..99")

        def step_hook(index, step):
            if index == args.simulate_failure_step:
                raise RuntimeError("Injected simulation failure at step {0}".format(index))

        options = dict(state_db=args.state_db, key=key, time_scale=args.time_scale, step_hook=step_hook)
    elif args.simulate_failure_step is not None or args.time_scale != 1.0:
        raise ValueError("Supervision simulation options require --supervision")
    server, audit = build_agent(config, options, telemetry_options)
    try:
        audit.write(
            "agent_initialized", mode=server.router.state.snapshot()["mode"], bind_host=config["bind_host"],
            command_port=config["command_port"], hardware_writes_allowed=False,
        )
        if args.initialize_simulation or args.supervision:
            if config["mode"] != "simulation":
                raise RuntimeError("--initialize-simulation requires simulation mode")
            initialization = server.router.backend.initialize()
            audit.write("simulation_initialized", detail=initialization)
        if args.discover_once:
            import json

            result = server.router.backend.discover()
            print(json.dumps(result, indent=2, sort_keys=True))
            audit.write("discover_once_completed", device_count=len(result["devices"]))
            return 0
        print("ELYSE acquisition agent listening on {0}:{1}; supervision={2}".format(
            server.server_address[0], server.server_address[1], bool(server.router.supervision)))
        print("mode={0}; hardware writes are blocked".format(server.router.state.snapshot()["mode"]))
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            audit.write("agent_stopped")
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
