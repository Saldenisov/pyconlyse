"""Everest-only harness: existing Python 3.4 agent + isolated web Supervision.

No live hardware/device routes, no remote deployment, no existing-server restart.
"""
import argparse
import os
import queue
import re
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / "legacy/xp_acq_agent"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python34", type=Path, default=ROOT / "tools/xp_python34_extracted/python.exe")
    parser.add_argument("--frontend-build", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, default=AGENT / "runtime/everest-supervision")
    parser.add_argument("--acq-port", type=int, default=8765)
    parser.add_argument("--web-port", type=int, default=5059)
    parser.add_argument("--time-scale", type=float, default=1)
    args = parser.parse_args()
    if not args.python34.is_file() or not (args.frontend_build / "index.html").is_file():
        parser.error("Actual Python 3.4 and compiled frontend are required")
    if not 1 <= args.web_port <= 65535 or not 0 <= args.acq_port <= 65535:
        parser.error("Invalid local port")
    if not 0 <= args.time_scale <= 1:
        parser.error("Simulation time-scale must be in 0..1")
    version = subprocess.check_output([str(args.python34), "-c", "import sys;print('%d.%d' % sys.version_info[:2])"], text=True).strip()
    if version != "3.4":
        parser.error("Server must be tested on actual Python 3.4, not a modern substitute")
    state_dir = args.state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    key_path = state_dir / "acq.key"
    if not key_path.exists():
        subprocess.run([str(args.python34), str(AGENT / "generate_supervision_key.py"), str(key_path)], check=True)
    command = [str(args.python34), "-u", str(AGENT / "main.py"), "--config", str(AGENT / "config.simulation.everest.json"),
               "--supervision", "--port", str(args.acq_port), "--key-file", str(key_path),
               "--state-db", str(state_dir / "acq.sqlite3"), "--audit-path", str(state_dir / "audit.jsonl"),
               "--time-scale", str(args.time_scale)]
    # Hidden child; never terminate or reconfigure an unrelated lab process.
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    ready = queue.Queue()

    def capture():
        with (state_dir / "agent-console.log").open("a", encoding="utf-8") as journal:
            for line in child.stdout:
                journal.write(line)
                journal.flush()
                if "listening on" in line:
                    ready.put(line)
            ready.put(None)

    reader = threading.Thread(target=capture, daemon=True)
    reader.start()
    try:
        banner = ready.get(timeout=15)
        match = re.search(r"listening on 127\.0\.0\.1:(\d+); supervision=True", banner or "")
        if not match:
            raise RuntimeError("Original agent did not start; inspect " + str(state_dir / "agent-console.log"))
        endpoint = "tcp://127.0.0.1:" + match.group(1)
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / "web/backend"))
        os.environ["PYCONLYSE_PRODUCTION"] = "false"
        os.environ["PYCONLYSE_ENFORCE_DEVICE_AUTH"] = "false"
        from flask import Flask, jsonify, send_from_directory
        from flask_jwt_extended import JWTManager
        from elyse_supervision_api import elyse_supervision_api
        from elyse_acq_transport import configured_acq

        app = Flask(__name__, static_folder=None)
        app.config.update(JWT_SECRET_KEY="isolated-loopback-preview-only", ELYSE_ACQ_URL=endpoint,
                          ELYSE_ACQ_LOCAL_SIMULATION=True, ELYSE_ACQ_SHARED_KEY_FILE=str(key_path),
                          ELYSE_SUPERVISION_STATE_DB=str(state_dir / "supervision.sqlite3"))
        configured_acq(app.config).read_state()  # Verify actual signed round trip before exposing the UI.
        JWTManager(app)
        app.register_blueprint(elyse_supervision_api)
        build = args.frontend_build.resolve()

        @app.get("/api/local-simulation")
        def identity():
            return jsonify(simulation=True, hardware_routes=False, acq_endpoint=endpoint, acq_pid=child.pid,
                           python_version="3.4", entrypoint="legacy/xp_acq_agent/main.py")

        @app.get("/")
        @app.get("/<path:path>")
        def frontend(path=""):
            if path.startswith("api/"):
                return jsonify(error="No live device routes in local simulation"), 404
            if path and (build / path).is_file():
                return send_from_directory(build, path)
            return send_from_directory(build, "index.html")

        print("Original agent: " + endpoint + "; local stubs only", flush=True)
        print("Supervision: http://127.0.0.1:{0}/elyse; no live hardware routes".format(args.web_port), flush=True)
        app.run(host="127.0.0.1", port=args.web_port, threaded=True, use_reloader=False)
    finally:
        if child.poll() is None:
            child.terminate()  # Unfinished software intents remain UNKNOWN on next startup.
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)
        reader.join(2)
        child.stdout.close()


if __name__ == "__main__":
    main()
