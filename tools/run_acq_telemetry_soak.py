"""Run synthetic-only, RAM-only Tango telemetry receiver and loopback status API.

No Tango database registration, hardware tasks, PSP calls, telemetry history or
SQLite writes. The native XP VI and Python 3.4 relay must be started separately.
Use the synthetic fixture key only for this isolated commissioning test.
"""
from __future__ import annotations

import argparse
import copy
import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class SoakMonitor:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.lock = threading.RLock()
        self.counter = 0
        self.samples = self.errors = 0
        self.first_receipt_utc = None
        self.last_change = None
        self.max_observed_silence = 0.0
        self.telemetry = None
        self.last_observation = None
        self.last_error = ''

    def observe(self, snapshot):
        now = self.clock()
        with self.lock:
            self.samples += 1
            count = snapshot['received_this_process']
            if self.last_change is not None:
                self.max_observed_silence = max(self.max_observed_silence, now - self.last_change)
            if count != self.counter:
                if self.first_receipt_utc is None:
                    self.first_receipt_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
                self.last_change = now
            self.counter = count
            self.telemetry = copy.deepcopy(snapshot)
            self.last_observation = now
            self.last_error = ''

    def error(self, error):
        with self.lock:
            self.errors += 1
            self.last_error = str(error)

    def snapshot(self):
        with self.lock:
            now = self.clock()
            silence = None if self.last_change is None else max(0, now - self.last_change)
            telemetry = copy.deepcopy(self.telemetry)
            # Cached packet age must keep increasing between successful Tango reads.
            if telemetry is not None:
                elapsed = max(0, now - self.last_observation)
                for packet in telemetry['publications'].values():
                    packet['age_seconds'] += elapsed
                    packet['stale'] = packet['age_seconds'] >= 2
            stale = telemetry is None or not telemetry['publications'] or any(
                p['stale'] for p in telemetry['publications'].values())
            return dict(test='synthetic_acq_transport_soak', hardware_writes=False,
                        history_available=False, sqlite_used=False,
                        uptime_seconds=now - self.started, tango_read_samples=self.samples,
                        tango_read_errors=self.errors, received_packets=self.counter,
                        first_receipt_utc=self.first_receipt_utc,
                        seconds_since_observed_new_receipt=silence,
                        max_observed_silence_seconds=max(self.max_observed_silence, silence or 0),
                        current_flow_healthy=not self.last_error and not stale and silence is not None and silence < 3,
                        last_error=self.last_error, telemetry=telemetry,
                        limitation='Transport soak only; not 73-site integration or hardware verification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--until', required=True, help='ISO-8601 stop time with explicit UTC offset')
    args = parser.parse_args()
    end = datetime.datetime.fromisoformat(args.until)
    now = datetime.datetime.now(datetime.timezone.utc)
    if end.tzinfo is None or not 0 < (end - now).total_seconds() <= 86400:
        parser.error('--until must be timezone-aware and between now and 24 hours from now')
    if not args.key_file.is_file():
        parser.error('fixture key file does not exist')
    from tango.test_context import DeviceTestContext
    from DeviceServers.control.elyse_acq.DS_AcqTelemetry import DS_AcqTelemetry
    monitor = SoakMonitor()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != '/status':
                self.send_error(404)
                return
            body = json.dumps(monitor.snapshot(), allow_nan=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *unused):
            pass

    properties = dict(listen_host='10.20.30.202', listen_port=8767,
                      permitted_xp_host='10.20.30.10', producer_kind_filter='fixture',
                      key_file=args.key_file.resolve().as_posix())
    http = ThreadingHTTPServer(('127.0.0.1', 8768), Handler)
    http.daemon_threads = True
    http_thread = threading.Thread(target=http.serve_forever, daemon=True)
    try:
        with DeviceTestContext(DS_AcqTelemetry, properties=properties, host='127.0.0.1',
                               process=True, timeout=20) as device:
            from tango import DevState
            if device.state() != DevState.ON:
                raise RuntimeError(device.status())
            http_thread.start()
            print(json.dumps(dict(started=True, tango_device=device.dev_name(),
                                  receiver='10.20.30.202:8767', status_url='http://127.0.0.1:8768/status',
                                  until=end.isoformat(), synthetic_only=True, storage_mode='ram_latest')), flush=True)
            while datetime.datetime.now(datetime.timezone.utc) < end:
                try:
                    monitor.observe(json.loads(device.telemetry_json))
                except Exception as error:
                    monitor.error(error)
                time.sleep(1)
            final = monitor.snapshot()
            final.pop('telemetry', None)  # Completion report is metrics, not archived telemetry.
            print(json.dumps(dict(completed=True, metrics=final), allow_nan=False), flush=True)
    finally:
        if http_thread.is_alive():
            http.shutdown()
            http_thread.join(3)
        http.server_close()


if __name__ == '__main__':
    main()
