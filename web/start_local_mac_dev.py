#!/usr/bin/env python3
"""
Local Mac development launcher.

Runs the Flask+Socket.IO backend on localhost while talking to the Tango
installation on the lab machine (default: 10.20.30.202:10000).
"""

import os
import sys
from pathlib import Path


project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Local dev defaults: backend runs on the Mac, Tango stays remote.
os.environ.setdefault("PYCONLYSE_TANGO_HOST", "10.20.30.202:10000")
os.environ.setdefault("TANGO_HOST", os.environ["PYCONLYSE_TANGO_HOST"])
os.environ.setdefault("PYCONLYSE_WEB_HOST", "127.0.0.1")
os.environ.setdefault("PYCONLYSE_WEB_PORT", "5000")
os.environ.setdefault("PYCONLYSE_WEB_DEBUG", "true")
os.environ.setdefault("PYCONLYSE_JWT_COOKIE_SECURE", "false")

original_cwd = os.getcwd()
try:
    os.chdir(backend_dir)
    from app import app, socketio
finally:
    os.chdir(original_cwd)


if __name__ == "__main__":
    web_host = os.environ["PYCONLYSE_WEB_HOST"]
    web_port = int(os.environ["PYCONLYSE_WEB_PORT"])
    tango_host = os.environ["TANGO_HOST"]

    print("=" * 60)
    print("PYCONLYSE Local Mac Web Server - DEVELOPMENT MODE")
    print("=" * 60)
    print(f"Backend:    http://{web_host}:{web_port}")
    print("Frontend:   http://localhost:3000  (run 'npm --prefix web/frontend start')")
    print(f"TANGO_HOST: {tango_host}")
    print("=" * 60)

    socketio.run(
        app,
        debug=True,
        host=web_host,
        port=web_port,
        allow_unsafe_werkzeug=True,
    )
