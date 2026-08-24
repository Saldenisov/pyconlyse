# PYCONLYSE Web Server - Controlled Single-Process Runner

## Runtime contract

`start_production.py` applies production security configuration and starts
Flask-SocketIO with `async_mode='threading'`. WebSocket support is provided by
the direct `simple-websocket` dependency.

Flask-SocketIO's threading mode runs through Flask/Werkzeug. Its documented
deployment guidance treats Werkzeug as a development server, not a production
deployment server. This launcher is therefore limited to controlled,
single-process lab use; it is not deployment-ready solely because production
security configuration is enabled. See [Flask-SocketIO deployment
guidance](https://flask-socketio.readthedocs.io/en/stable/deployment.html).

## Deployment blocker

Do not treat this launcher as a supported production service. A supported
Windows-compatible threaded Socket.IO server option, operational ownership,
and load validation have not been selected. Gunicorn with one worker and
threads plus `simple-websocket` is documented for the threaded path, but
Gunicorn is Unix-only and does not resolve the Windows target. Selecting and
validating a supported Windows server is required before changing this status.

## Controlled start

Install locked application dependencies:

```powershell
poetry install --only main
```

For development and test tooling, use `poetry install --with dev`.

Set required security values before starting:

```powershell
$env:JWT_SECRET_KEY = "at-least-32-bytes-of-random-secret-material"
$env:PYCONLYSE_AUTH_USERS = '{"operator":"password-hash"}'
$env:PYCONLYSE_ENFORCE_DEVICE_AUTH = "true"
$env:PYCONLYSE_JWT_COOKIE_CSRF_PROTECT = "true"
```

Run from the `web` directory:

```powershell
python start_production.py
```

Defaults are `PYCONLYSE_WEB_HOST=0.0.0.0` and `PYCONLYSE_WEB_PORT=5000`.
The launcher rejects an unavailable bind address, a non-TCP port, missing
authentication configuration, weak JWT secrets, or disabled device/CSRF
enforcement.

## Reverse proxy

TLS termination and Socket.IO upgrade headers may be required by a chosen
deployment architecture, but a reverse proxy does not remove the deployment
blocker above. Do not represent this configuration as a validated production
topology until the supported Windows server and load validation are complete.

## Troubleshooting

- `Address already in use`: release the configured port or select another
  `PYCONLYSE_WEB_PORT`.
- WebSocket connection failures: verify `flask-socketio` and
  `simple-websocket` match the lock, then inspect the selected server's
  Socket.IO/WebSocket configuration.
- Authentication startup failures: set required production values before
  launch; do not weaken cookie, CSRF, or device-auth enforcement.
- Tango connection errors: verify server configuration and `TANGO_HOST`.
