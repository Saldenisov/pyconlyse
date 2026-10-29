"""Explicit web camera/diagnostics assembly. No XP or motion client."""
import atexit
import os
from pathlib import Path
import threading

from acq_camera_broker import CameraFrameBroker
from acq_telemetry_api import read_camera_source, read_camera_channels
from supervision_diagnostics import DiagnosticsService, PostgresDiagnosticsStore, UnavailableDiagnosticsStore
from supervision_diagnostics_api import create_diagnostics_api


def configure_supervision_camera(app):
    """Build inert services; launcher explicitly begins headless observation.

    Monitoring then belongs to the web process and continues when the browser
    closes. SQL is handled by its independent bounded numeric writer.
    """
    broker = CameraFrameBroker(read_camera_source, read_camera_channels, monitor_all=True)
    config = app.config.get('ELYSE_TELEMETRY_ARCHIVE_CONFIG') or os.environ.get('ELYSE_TELEMETRY_ARCHIVE_CONFIG')
    if not config:
        candidate = Path(r'F:\ELYSE_PostgreSQL\secrets\archive.json')
        config = str(candidate) if candidate.is_file() else None
    try:
        store = PostgresDiagnosticsStore(config) if config else UnavailableDiagnosticsStore()
    except Exception:
        store = UnavailableDiagnosticsStore('Configured PostgreSQL diagnostics unavailable')

    def read_video(camera_id):
        from supervision_diagnostics import camera_channel
        return broker.snapshot(camera_channel(camera_id))

    service = DiagnosticsService(read_video, store)
    broker.decorate = service.observe
    app.extensions['supervision_camera_broker'] = broker
    app.extensions['supervision_diagnostics'] = service
    app.register_blueprint(create_diagnostics_api(service))
    lock, started = threading.Lock(), False

    def start_services():
        nonlocal started
        with lock:
            if not started:
                service.start(poll=False)
                broker.start()
                started = True
    app.extensions['start_supervision_monitor'] = start_services

    @app.before_request
    def start_camera_observer():
        from flask import request
        if (request.path.startswith('/api/elyse/acquisition/telemetry/video')
                or request.path.startswith('/api/elyse/supervision/diagnostics')):
            start_services()

    def close():
        image_closed, diagnostics_closed = broker.close(), service.close()
        if not image_closed or not diagnostics_closed:
            app.logger.warning('SuperVision camera shutdown incomplete: image=%s diagnostics=%s',
                               image_closed, diagnostics_closed)
        return image_closed and diagnostics_closed
    atexit.register(close)
    return broker, service
