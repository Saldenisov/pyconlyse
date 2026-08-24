#!/usr/bin/env python3
"""
PYCONLYSE Web Server - Production Startup Script

This script starts the PYCONLYSE web server in production mode.
It uses eventlet for proper Socket.IO WebSocket support.

Requirements:
    pip install eventlet

Usage:
    python start_production.py
"""

import errno
import os
import socket
import sys
from pathlib import Path


MINIMUM_JWT_SECRET_BYTES = 32


def _validate_production_jwt_secret(jwt_secret):
    """Reject short signing secrets before production startup imports the app."""
    if len(jwt_secret.encode("utf-8")) < MINIMUM_JWT_SECRET_BYTES:
        raise RuntimeError(
            "JWT_SECRET_KEY must be at least 32 bytes in production"
        )


def configure_production_environment(environ=None):
    """Apply production-safe defaults before importing the Flask application."""
    environ = os.environ if environ is None else environ
    environ["PYCONLYSE_PRODUCTION"] = "true"
    for name in ("JWT_SECRET_KEY", "PYCONLYSE_AUTH_USERS"):
        if not environ.get(name, "").strip():
            raise RuntimeError(f"{name} must be set before starting production")
    _validate_production_jwt_secret(environ["JWT_SECRET_KEY"].strip())
    environ.setdefault("PYCONLYSE_ENFORCE_DEVICE_AUTH", "true")
    if str(environ["PYCONLYSE_ENFORCE_DEVICE_AUTH"]).strip().lower() not in (
        "1", "true", "yes", "y", "on"
    ):
        raise RuntimeError("PYCONLYSE_ENFORCE_DEVICE_AUTH must be true in production")
    environ.setdefault("PYCONLYSE_JWT_COOKIE_SECURE", "true")
    environ.setdefault("PYCONLYSE_JWT_COOKIE_CSRF_PROTECT", "true")
    if str(environ["PYCONLYSE_JWT_COOKIE_CSRF_PROTECT"]).strip().lower() not in (
        "1", "true", "yes", "y", "on"
    ):
        raise RuntimeError(
            "PYCONLYSE_JWT_COOKIE_CSRF_PROTECT must be true in production"
        )


def parse_web_port(value):
    """Return a valid TCP port from an environment value."""
    text = str(value).strip()
    if not text or not text.isascii() or not text.isdecimal():
        raise RuntimeError("PYCONLYSE_WEB_PORT must be an integer from 1 to 65535")
    port = int(text)
    if not 1 <= port <= 65535:
        raise RuntimeError("PYCONLYSE_WEB_PORT must be an integer from 1 to 65535")
    return port


def preflight_web_port(host, port):
    """Verify that the configured local TCP bind address is currently available."""
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RuntimeError(
            f"PYCONLYSE_WEB_HOST {host!r} cannot be resolved for local binding"
        ) from exc

    for family, socktype, protocol, _, address in addresses:
        probe = socket.socket(family, socktype, protocol)
        try:
            probe.bind(address)
        except OSError as exc:
            if exc.errno == errno.EADDRINUSE:
                raise RuntimeError(
                    f"PYCONLYSE_WEB_PORT {port} is already in use for host {host!r}"
                ) from exc
            raise RuntimeError(
                f"PYCONLYSE_WEB_PORT {port} cannot be bound on host {host!r}: {exc}"
            ) from exc
        finally:
            probe.close()


def run_production_server(socketio, app, web_host, web_port):
    """Run Socket.IO and propagate any startup failure to the caller."""
    try:
        socketio.run(
            app,
            debug=False,
            port=web_port,
            host=web_host,
            use_reloader=False,
        )
    except KeyboardInterrupt:
        print("\n\nServer stopped by user.")
        raise
    except ImportError as exc:
        if "eventlet" in str(exc):
            print("\n\nERROR: eventlet is not installed!")
            print("Please install it with: pip install eventlet")
            print("\neventlet is required for Socket.IO WebSocket support in production.")
        raise
    except Exception as exc:
        print(f"\nError starting server: {exc}")
        print("\nTroubleshooting:")
        print("1. Check if port 5000 is available")
        print("2. Verify IP address 10.20.30.202 is correct")
        print("3. Ensure Tango database is accessible")
        print("4. Check devices are registered and running")
        print("5. Ensure eventlet is installed: pip install eventlet")
        raise


def main():
    configure_production_environment()
    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root))
    backend_dir = Path(__file__).parent / 'backend'
    sys.path.insert(0, str(backend_dir))

    original_cwd = os.getcwd()
    try:
        os.chdir(str(backend_dir))
        from auth import configured_users
        configured_users(required=True)
        from app import app, socketio
        from device_api import start_device_snapshot_monitor
    finally:
        os.chdir(original_cwd)

    web_host = os.environ.get('PYCONLYSE_WEB_HOST', '0.0.0.0').strip()
    if not web_host:
        raise RuntimeError("PYCONLYSE_WEB_HOST must be non-empty")
    web_port = parse_web_port(os.environ.get('PYCONLYSE_WEB_PORT', '5000'))
    print("=" * 60)
    print("PYCONLYSE Web Server - PRODUCTION MODE")
    print("=" * 60)
    print(f"Server starting on: http://{web_host}:{web_port}")
    print(f"Main page:        http://{web_host}:{web_port}/")
    print(f"iTest PSU page:   http://{web_host}:{web_port}/test_ds_itest_psu.html")
    print(f"API devices:      http://{web_host}:{web_port}/api/devices")
    print(f"TANGO_HOST:       {os.environ.get('TANGO_HOST', os.environ.get('PYCONLYSE_TANGO_HOST', '10.20.30.202:10000'))}")
    print("=" * 60)
    print("Production settings:")
    print("  - Debug mode: OFF")
    print("  - WebSocket: eventlet")
    print("  - Auto-reload: OFF")
    print(f"  - Device auth enforced: {os.environ.get('PYCONLYSE_ENFORCE_DEVICE_AUTH')}")
    print("=" * 60)

    preflight_web_port(web_host, web_port)
    start_device_snapshot_monitor()
    run_production_server(socketio, app, web_host, web_port)


if __name__ == '__main__':
    main()
