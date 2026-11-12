"""Serve Pyconlyse on the ELYSE laboratory network without a login flow."""

import os


def configure_local_environment(environ=None):
    environ = os.environ if environ is None else environ
    environ.setdefault("PYCONLYSE_VD2_CAMERA_ONLY", "1")
    # Explicit values prevent an inherited production configuration from changing
    # laboratory startup after a reboot. Access is limited by the host firewall
    # and the ELYSE laboratory network.
    environ.update({
        "PYCONLYSE_PRODUCTION": "false",
        "PYCONLYSE_ENFORCE_DEVICE_AUTH": "false",
        "PYCONLYSE_JWT_COOKIE_SECURE": "false",
        "PYCONLYSE_JWT_COOKIE_CSRF_PROTECT": "false",
        "PYCONLYSE_JWT_COOKIE_SAMESITE": "Lax",
        "PYCONLYSE_WEB_HOST": "0.0.0.0",
        "PYCONLYSE_WEB_PORT": "5000",
        "PYCONLYSE_WEB_DEBUG": "false",
        "PYCONLYSE_TREATMENT_CACHE_DIR": "D:/Pyconlyse/treatment_cache",
        "ACQ_LOCAL_CONSOLE_ENABLED": "true",
        "ACQ_LOCAL_CONSOLE_ORIGIN": "http://127.0.0.1:5000",
        "ACQ_LOCAL_CONSOLE_KEY_FILE": r"F:\ELYSE_Telemetry_Server\postgres_v3\web-control\local-console.key",
        "ACQ_LOCAL_CONSOLE_DB_FILE": r"F:\ELYSE_Telemetry_Server\postgres_v3\web-control\local-approvals.sqlite3",
        "PYCONLYSE_CORS_ORIGINS": (
            "http://127.0.0.1:5000,http://localhost:5000,"
            "http://10.20.30.202:5000,http://129.175.100.128:5000,"
            "http://127.0.0.1:3000,http://localhost:3000"
        ),
    })


if __name__ == "__main__":
    configure_local_environment()
    from start_pyconlyse_server import main
    main()
