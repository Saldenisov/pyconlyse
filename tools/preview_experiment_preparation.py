"""Loopback-only UI verification with simulated hardware; never imports Tango."""

import argparse
import sys
import time
from pathlib import Path
from threading import Lock

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web" / "backend"))
from experiment_lifecycle import ExperimentLifecycle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--state-db", type=Path, required=True)
    parser.add_argument("--port", type=int, default=5101)
    args = parser.parse_args()
    lifecycle = ExperimentLifecycle(args.state_db)
    mutation_lock = Lock()
    counts = {"prepare": 0, "shutdown": 0}
    app = Flask(__name__, static_folder=None)

    def prepare(steps):
        counts["prepare"] += 1
        steps.append({"step": "SIMULATED SD2 supply", "status": "verified ON; no real hardware"})
        steps.power_intent()
        deadline = steps.power_deadline(True)
        steps.phase("SIMULATED: waiting for streak / Kymera power before initialization", wait_until=deadline)
        time.sleep(max(0, deadline - time.time()))
        steps.power_ready()
        steps.append({"step": "SIMULATED Kymera initialization", "status": "ready after 30 s"})
        return {"steps": list(steps), "message": "SIMULATED preparation complete; physical equipment was not operated"}

    def shutdown(steps):
        counts["shutdown"] += 1
        steps.append({"step": "SIMULATED shutdown", "status": "no real hardware"})
        return {"steps": list(steps), "warnings": [], "message": "SIMULATED shutdown complete"}

    @app.get("/api/pump-probe-vd2/lifecycle")
    def state():
        return jsonify(success=True, job=lifecycle.snapshot())

    @app.get("/api/pump-probe-vd2/lifecycle/log")
    def event_log():
        return jsonify(success=True, events=lifecycle.events(before=request.args.get("before", type=int)))

    @app.get("/preview-proof")
    def proof():
        return jsonify(counts=counts, job=lifecycle.snapshot())

    @app.post("/api/pump-probe-vd2/<action>")
    def start(action):
        if action not in {"initialize", "deinitialize"} or request.args.get("background") != "1":
            return jsonify(success=False, error="Only simulated background lifecycle actions are supported"), 400
        operation = "prepare" if action == "initialize" else "shutdown"
        if not mutation_lock.acquire(False):
            return jsonify(success=True, job=lifecycle.snapshot(), attached=True), 202
        try:
            job = lifecycle.start(operation, prepare if operation == "prepare" else shutdown, mutation_lock.release)
        except Exception:
            mutation_lock.release()
            raise
        return jsonify(success=True, job=job), 202

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def frontend(path):
        if path and (args.build / path).is_file():
            return send_from_directory(args.build, path)
        return send_from_directory(args.build, "index.html")

    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
