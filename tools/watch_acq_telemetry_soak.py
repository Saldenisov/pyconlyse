"""Retain one health summary of the running synthetic soak, never telemetry.

Read-only loopback GETs. No Tango commands, PSP, NI access, restart or hardware
actions. One JSON file is replaced atomically; it contains aggregate diagnostics,
not packet data or telemetry history. The receiver is started separately.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import time
from urllib.request import urlopen


STATUS_URL = 'http://127.0.0.1:8768/status'
MAX_STATUS_BYTES = 262144


class HealthSummary:
    def __init__(self, started_utc, until):
        self.result = dict(
            test='synthetic_acq_transport_soak_health',
            started_utc=started_utc, until=until, completed=False,
            telemetry_persisted=False, sqlite_used=False, hardware_actions=False,
            endpoint_read_samples=0, endpoint_read_errors=0,
            unhealthy_samples=0, receiver_restarts_or_counter_regressions=0,
            max_receiver_silence_seconds=0.0, max_tango_read_errors=0,
            last_error='', last_success_utc=None, latest=None)
        self.receiver_session = None
        self.count = None

    def observe(self, payload, checked_utc):
        if (payload.get('test') != 'synthetic_acq_transport_soak'
                or payload.get('hardware_writes') is not False
                or payload.get('sqlite_used') is not False):
            raise ValueError('unexpected/non-synthetic status endpoint')
        telemetry = payload['telemetry']
        if not isinstance(telemetry, dict):
            raise ValueError('receiver has not supplied its first Tango snapshot')
        session = telemetry['receiver_session']
        count = payload['received_packets']
        if self.receiver_session is not None and (
                session != self.receiver_session or count < self.count):
            self.result['receiver_restarts_or_counter_regressions'] += 1
        self.receiver_session, self.count = session, count
        self.result['endpoint_read_samples'] += 1
        if payload['current_flow_healthy'] is not True:
            self.result['unhealthy_samples'] += 1
        self.result['max_receiver_silence_seconds'] = max(
            self.result['max_receiver_silence_seconds'],
            payload['max_observed_silence_seconds'])
        self.result['max_tango_read_errors'] = max(
            self.result['max_tango_read_errors'], payload['tango_read_errors'])
        # Explicit allowlist: neither publications nor data are persisted.
        self.result['latest'] = {key: payload[key] for key in (
            'uptime_seconds', 'received_packets', 'first_receipt_utc',
            'seconds_since_observed_new_receipt',
            'max_observed_silence_seconds', 'current_flow_healthy',
            'tango_read_errors', 'last_error')}
        self.result['last_success_utc'] = checked_utc
        self.result['last_error'] = ''

    def error(self, error, checked_utc):
        self.result['endpoint_read_errors'] += 1
        self.result['last_error'] = str(error)
        self.result['last_failure_utc'] = checked_utc

    def save(self, path):
        path = Path(path)
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(json.dumps(self.result, indent=2, allow_nan=False),
                             encoding='utf-8')
        temporary.replace(path)


def utc_now():
    return dt.datetime.now(dt.timezone.utc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--until', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    end = dt.datetime.fromisoformat(args.until)
    if end.tzinfo is None or not 0 < (end - utc_now()).total_seconds() <= 86400:
        parser.error('--until must be timezone-aware, within the next 24 hours')
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error('output parent must exist and output must be a new file')
    summary = HealthSummary(utc_now().isoformat(), end.isoformat())
    print(json.dumps(dict(started=True, status_url=STATUS_URL,
                          health_summary=str(args.output), until=end.isoformat())), flush=True)
    try:
        while utc_now() < end:
            try:
                with urlopen(STATUS_URL, timeout=5) as response:
                    body = response.read(MAX_STATUS_BYTES + 1)
                if len(body) > MAX_STATUS_BYTES:
                    raise ValueError('status response exceeds bounded size')
                summary.observe(json.loads(body), utc_now().isoformat())
            except Exception as error:
                summary.error(error, utc_now().isoformat())
            summary.save(args.output)
            time.sleep(max(0, min(10, (end - utc_now()).total_seconds())))
        summary.result['completed'] = True
        summary.result['completed_utc'] = utc_now().isoformat()
    finally:
        summary.save(args.output)
        print(json.dumps(summary.result, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
