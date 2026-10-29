"""Run the development Flask/Socket.IO backend; React runs on port 3000."""

import os
import sys
from pathlib import Path


def configure_development_environment(environ=None):
    environ = os.environ if environ is None else environ
    environ["PYCONLYSE_PRODUCTION"] = "false"
    environ.setdefault("PYCONLYSE_ENFORCE_DEVICE_AUTH", "false")
    environ.setdefault("PYCONLYSE_JWT_COOKIE_SECURE", "false")
    environ.setdefault("PYCONLYSE_WEB_HOST", "127.0.0.1")
    environ.setdefault("PYCONLYSE_WEB_PORT", "5000")
    environ.setdefault("PYCONLYSE_WEB_DEBUG", "true")
    environ.setdefault(
        "PYCONLYSE_TREATMENT_STATE_DB",
        str(Path.home() / ".pyconlyse" / "treatment_state.sqlite3"),
    )
    if (
        not environ.get("PYCONLYSE_TREATMENT_ROOT")
        and not environ.get("PYCONLYSE_ALLOWED_ROOT")
        and Path("E:/DATA_VD2").is_dir()
    ):
        environ["PYCONLYSE_TREATMENT_ROOT"] = "E:/DATA_VD2"


def main():
    configure_development_environment()
    project_root = Path(__file__).resolve().parents[1]
    backend_dir = project_root / "web" / "backend"
    sys.path[:0] = [str(project_root), str(backend_dir)]
    original_cwd = os.getcwd()
    try:
        os.chdir(backend_dir)
        from app import app, socketio
        from device_api import start_device_snapshot_monitor
        from folder_api import get_allowed_root
    finally:
        os.chdir(original_cwd)

    web_host = os.environ["PYCONLYSE_WEB_HOST"]
    web_port = int(os.environ["PYCONLYSE_WEB_PORT"])
    debug_enabled = os.environ["PYCONLYSE_WEB_DEBUG"].lower() in (
        "1", "true", "yes", "on"
    )
    print("PYCONLYSE Web Server - DEVELOPMENT MODE")
    print(f"Backend: http://{web_host}:{web_port}")
    print("React hot reload: http://127.0.0.1:3000")
    print(f"Data Root: {get_allowed_root()}")
    start_device_snapshot_monitor()
    start_camera_monitor = app.extensions.get('start_supervision_monitor')
    if start_camera_monitor:
        start_camera_monitor()
    socketio.run(
        app,
        debug=debug_enabled,
        host=web_host,
        port=web_port,
        use_reloader=debug_enabled,
        use_debugger=False,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
