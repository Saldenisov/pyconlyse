"""Read-only 24-hour Acquisition -> Everest soak observer, run on Everest.

Polls signed XP /status, Tango telemetry/archive attributes and web telemetry.
Writes compact metadata on F:, never pixels, keys, commands or NI operations.
SuperVision is outside this run's scope. No restart is performed or scheduled.
Ten-second sampling cannot exclude shorter outages between observations.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hmac
import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.request
import uuid
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy.xp_acq_control.elyse_agent.acquisition_http import request_signature, response_signature
from legacy.xp_acq_control.elyse_agent.shared_state import BANKS

DEVICE = 'tango://10.20.30.202:10000/elyse/acquisition/telemetry'
XP_URL = 'http://10.20.30.10:8772/status'
WEB_URL = 'http://127.0.0.1:5000/api/elyse/acquisition/telemetry'
MAX_BYTES = 2 * 1024 * 1024
PARIS = ZoneInfo('Europe/Paris')


def now_utc():
    return datetime.now(timezone.utc)


def compact_banks(publications):
    return {name: {key: bank.get(key) for key in
                  ('sequence', 'session_id', 'age_seconds', 'stale', 'producer_kind', 'message_id')}
            | {'error_status': bank.get('error', {}).get('status'),
               'error_code': bank.get('error', {}).get('code')}
            for name, bank in publications.items()}


def xp_metadata(data):
    result = {key: data.get(key) for key in ('session_id', 'state', 'resource_count', 'server_variant')}
    delivery = data.get('telemetry_delivery', {})
    result['delivery'] = {key: delivery.get(key) for key in (
        'source_mode', 'relay_id', 'connected', 'worker_alive', 'auto_reconnect',
        'connections_opened', 'disconnects', 'failed_attempts', 'connect_attempts',
        'everest_acknowledged', 'last_ack_age_seconds', 'last_error', 'publisher_error',
        'vi_accepted', 'vi_rejected', 'vi_seen_age_seconds', 'vi_ingress_error',
        'replaced_pending', 'pending', 'capacity', 'inflight', 'pending_latest',
        'ingress_handler_limit_rejections', 'vi_owner_contentions', 'vi_deferred',
        'vi_deferred_replaced', 'vi_deferred_rejected', 'vi_deferred_pending',
        'vi_admission_delay_seconds', 'vi_admission_delay_max_seconds')}
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Monitor redirects refused')


class Collector:
    def __init__(self):
        import tango
        import psutil
        self.tango, self.psutil = tango, psutil
        self.proxy = None
        self.key = None
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def device(self):
        if self.proxy is None:
            self.proxy = self.tango.DeviceProxy(DEVICE)
            self.proxy.set_timeout_millis(2000)
        return self.proxy

    def http(self, url, signed=False):
        headers = {}
        nonce = uuid.uuid4().hex
        if signed:
            if self.key is None:
                key_path = self.device().get_property('key_file')['key_file'][0]
                self.key = Path(key_path).read_bytes().strip()
                if len(self.key) < 32:
                    raise ValueError('Invalid read-key length')
            headers = {'X-ACQ-Nonce': nonce,
                       'X-ACQ-Signature': request_signature(self.key, '/status', nonce)}
        started = time.monotonic()
        with self.opener.open(urllib.request.Request(url, headers=headers), timeout=2) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES or time.monotonic() - started > 2.5:
                raise ValueError('Response exceeds monitor size/time acceptance bound')
            if signed and not hmac.compare_digest(response_signature(self.key, nonce, raw),
                    response.headers.get('X-ACQ-Response-Signature', '')):
                raise ValueError('XP response signature mismatch')
        return json.loads(raw)

    def processes(self):
        rows = []
        for process in self.psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if not any(Path(arg).name == 'DS_AcqTelemetry.py'
                           for arg in (process.info['cmdline'] or [])):
                    continue
                if Path(process.cwd()).resolve() != Path(
                        r'F:\ELYSE_Telemetry_Server\postgres_v3\DeviceServers\control\elyse_acq').resolve():
                    continue
                with process.oneshot():
                    memory, cpu = process.memory_info(), process.cpu_times()
                    rows.append(dict(pid=process.pid, created_epoch=process.create_time(),
                        rss_bytes=memory.rss, private_bytes=getattr(memory, 'private', None),
                        handles=process.num_handles(), threads=process.num_threads(),
                        cpu_seconds=cpu.user + cpu.system))
            except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                continue
        return rows

    def sample(self):
        started = time.monotonic()
        row = dict(utc=now_utc().isoformat(), monotonic=started, errors={})
        try:
            attributes = self.device().read_attributes(['telemetry_json', 'archive_status_json'])
            telemetry, archive = [json.loads(attr.value) for attr in attributes]
            row['tango'] = dict(receiver_session=telemetry.get('receiver_session'),
                received=telemetry.get('received_this_process'),
                producer_kind=telemetry.get('active_producer_kind'),
                banks=compact_banks(telemetry.get('publications', {})),
                transport=telemetry.get('telemetry_transport', {}))
            row['archive'] = {key: archive.get(key) for key in ('state', 'enabled', 'backend',
                'pending', 'committed_this_process', 'last_commit_utc', 'last_error')}
        except Exception as exc:
            row['errors']['tango'] = type(exc).__name__
        try:
            row['xp'] = xp_metadata(self.http(XP_URL, signed=True))
        except Exception as exc:
            row['errors']['xp'] = type(exc).__name__
        try:
            web = self.http(WEB_URL)
            row['web'] = {key: web.get(key) for key in ('quality', 'server_state', 'observed_utc',
                'source', 'missing_banks', 'stale_banks', 'error_banks', 'unavailable_banks')}
            row['web']['banks'] = compact_banks(web.get('snapshot', {}).get('publications', {}))
        except Exception as exc:
            row['errors']['web'] = type(exc).__name__
        try:
            row['receiver_processes'] = self.processes()
        except Exception as exc:
            row['errors']['process_metrics'] = type(exc).__name__
        row['read_seconds'] = time.monotonic() - started
        return row


def sample_issues(row, previous=None, interval=10):
    issues = ['read_failed:' + source for source in sorted(row.get('errors', {}))]
    for source in ('tango', 'web'):
        data = row.get(source)
        if data is None:
            continue
        banks = data.get('banks', {})
        if set(banks) != set(BANKS):
            issues.append(source + ':bank_set_incomplete')
        old_banks = (previous or {}).get(source, {}).get('banks', {})
        for name, bank in banks.items():
            if bank.get('stale') is not False:
                issues.append(source + ':stale:' + name)
            age = bank.get('age_seconds')
            if type(age) not in (float, int) or not math.isfinite(age) or age < 0:
                issues.append(source + ':invalid_age:' + name)
            if bank.get('error_status') is not False:
                issues.append(source + ':bank_error:' + name)
            old = old_banks.get(name)
            if old:
                if bank.get('session_id') != old.get('session_id'):
                    issues.append(source + ':source_session_changed:' + name)
                elif (type(bank.get('sequence')) is not int or type(old.get('sequence')) is not int
                      or bank['sequence'] <= old['sequence']):
                    issues.append(source + ':not_advancing:' + name)
        if source == 'web' and data.get('quality') != 'FRESH':
            issues.append('web:not_fresh')
    xp = row.get('xp')
    old_xp = (previous or {}).get('xp', {})
    if xp is not None:
        delivery = xp.get('delivery', {})
        for key in ('connected', 'worker_alive'):
            if delivery.get(key) is not True:
                issues.append('xp:' + key + '_false')
        for key in ('last_error', 'publisher_error', 'vi_ingress_error'):
            if delivery.get(key):
                issues.append('xp:' + key)
        if old_xp:
            if xp.get('session_id') != old_xp.get('session_id'):
                issues.append('xp:server_restarted')
            else:
                old_delivery = old_xp.get('delivery', {})
                for key in ('disconnects', 'failed_attempts', 'connections_opened'):
                    if type(delivery.get(key)) is not int or type(old_delivery.get(key)) is not int:
                        issues.append('xp:invalid_counter:' + key)
                    elif delivery[key] > old_delivery[key]:
                        issues.append('xp:increased:' + key)
                if (type(delivery.get('everest_acknowledged')) is not int or
                    type(old_delivery.get('everest_acknowledged')) is not int or
                    delivery['everest_acknowledged'] <= old_delivery['everest_acknowledged']):
                    issues.append('xp:ack_not_advancing')
        ack_age = delivery.get('last_ack_age_seconds')
        if type(ack_age) not in (int, float) or not math.isfinite(ack_age) or not 0 <= ack_age <= 6:
            issues.append('xp:ack_old')
    archive = row.get('archive')
    if archive is not None:
        if archive.get('state') != 'RUNNING' or archive.get('last_error') or archive.get('enabled') is not True:
            issues.append('archive:not_healthy')
        old_archive = (previous or {}).get('archive')
        if old_archive and (type(archive.get('committed_this_process')) is not int or
                type(old_archive.get('committed_this_process')) is not int or
                archive['committed_this_process'] <= old_archive['committed_this_process']):
            issues.append('archive:commits_not_advancing')
    processes = row.get('receiver_processes', [])
    if len(processes) != 1:
        issues.append('receiver:process_count_not_one')
    old_processes = (previous or {}).get('receiver_processes', [])
    if len(processes) == len(old_processes) == 1:
        if (processes[0]['pid'], processes[0]['created_epoch']) != (
                old_processes[0]['pid'], old_processes[0]['created_epoch']):
            issues.append('receiver:process_restarted')
    if previous and row['monotonic'] - previous['monotonic'] > interval * 2:
        issues.append('monitor:sampling_gap')
    if row.get('read_seconds', 0) > interval:
        issues.append('monitor:poll_overrun')
    return sorted(set(issues))


class RunSummary:
    def __init__(self, started, duration, interval):
        self.started, self.duration, self.interval = started, duration, interval
        self.first = self.last = None
        self.samples = self.healthy = 0
        self.counts = Counter()
        self.active = set()
        self.hourly = {}
        self.max_gap = 0

    def add(self, row):
        issues = sample_issues(row, self.last, self.interval)
        new = set(issues)
        events = []
        if new != self.active:
            events.append(dict(utc=row['utc'], entered=sorted(new - self.active),
                cleared=sorted(self.active - new), interval_seconds=None if self.last is None else
                row['monotonic'] - self.last['monotonic'],
                interpretation='Observed change; transition time lies between polls'))
        self.samples += 1
        self.healthy += not issues
        self.counts.update(issues)
        self.active = new
        if self.first is None:
            self.first = row
        if self.last:
            self.max_gap = max(self.max_gap, row['monotonic'] - self.last['monotonic'])
        hour = str(int((row['monotonic'] - self.first['monotonic']) // 3600))
        bucket = self.hourly.setdefault(hour, dict(samples=0, healthy_samples=0, memory_samples=0,
            rss_sum_bytes=0, rss_max_bytes=0, private_sum_bytes=0, private_samples=0,
            handles_max=0, archive_pending_max=0))
        bucket['samples'] += 1
        bucket['healthy_samples'] += not issues
        processes = row.get('receiver_processes', [])
        if len(processes) == 1:
            process = processes[0]
            bucket['memory_samples'] += 1
            bucket['rss_sum_bytes'] += process['rss_bytes']
            bucket['rss_max_bytes'] = max(bucket['rss_max_bytes'], process['rss_bytes'])
            if process.get('private_bytes') is not None:
                bucket['private_sum_bytes'] += process['private_bytes']
                bucket['private_samples'] += 1
            bucket['handles_max'] = max(bucket['handles_max'], process['handles'])
        bucket['archive_pending_max'] = max(bucket['archive_pending_max'],
            row.get('archive', {}).get('pending', 0))
        self.last = row
        row['issues'] = issues
        return events

    def snapshot(self, state='RUNNING'):
        first, last = self.first or {}, self.last or {}
        elapsed = max(0, last.get('monotonic', 0) - first.get('monotonic', 0))
        completed = state == 'COMPLETED' and elapsed >= self.duration
        verdict = ('NO_SAMPLED_FAILURES' if not self.counts else 'INCIDENTS_REQUIRE_REVIEW') if completed else 'IN_PROGRESS'
        if state not in ('RUNNING', 'COMPLETED'):
            verdict = 'INCOMPLETE'
        return dict(schema_version=1, state=state, verdict=verdict,
            started_utc=self.started.isoformat(), started_paris=self.started.astimezone(PARIS).isoformat(),
            planned_end_paris=(self.started + timedelta(seconds=self.duration)).astimezone(PARIS).isoformat(),
            updated_utc=now_utc().isoformat(), elapsed_observed_seconds=elapsed,
            requested_seconds=self.duration, interval_seconds=self.interval, samples=self.samples,
            healthy_samples=self.healthy, issue_sample_counts=dict(self.counts), active_issues=sorted(self.active),
            max_sample_gap_seconds=self.max_gap, hourly=self.hourly, latest=last,
            first_runtime=first.get('xp'), first_receiver_processes=first.get('receiver_processes'),
            first_archive=first.get('archive'),
            scope='Acquisition current VI bridge -> Python -> Everest Tango/PostgreSQL/web; excludes SuperVision and Python NI ownership',
            limitations=['Polling can miss outages shorter than the sample interval',
                         'XP process memory/handles are not exposed by its API and are not measured',
                         'No receiver/network failure was deliberately injected in this passive run',
                         'Source sequence advancement does not prove physical measurement correctness'],
            automatic_restart=False, hardware_commands_sent=False, initialize_invoked=False,
            restart_recommendation='UNDETERMINED_PENDING_DURATION_AND_INCIDENT_REVIEW')


def atomic_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    for attempt in range(6):
        try:
            os.replace(temporary, path)
            return
        except PermissionError:
            if attempt == 5:
                raise
            # A concurrent Windows reader/AV can briefly deny replacement.
            time.sleep(.02 * (attempt + 1))


def resume_summary(output, duration, interval):
    saved = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
    if saved['requested_seconds'] != duration or saved['interval_seconds'] != interval:
        raise ValueError('Resume must retain the original duration and sample interval')
    summary = RunSummary(datetime.fromisoformat(saved['started_utc']), duration, interval)
    with (output / 'samples.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            summary.add(json.loads(line))
    if summary.last and time.monotonic() < summary.last['monotonic']:
        raise ValueError('Monotonic clock reset; use a new observation folder')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--hours', type=float, default=24)
    parser.add_argument('--interval', type=float, default=10)
    parser.add_argument('--max-samples', type=int, help='Bounded smoke check; never qualifies a full-duration run')
    parser.add_argument('--resume', action='store_true', help='Append to existing samples; retain and report the monitoring gap')
    args = parser.parse_args()
    if (not math.isfinite(args.hours) or not 0 < args.hours <= 168 or
            not math.isfinite(args.interval) or not 2 <= args.interval <= 60 or
            (args.max_samples is not None and args.max_samples < 1)):
        parser.error('Require 0 < hours <= 168, 2 <= interval <= 60 and positive max-samples')
    if args.resume:
        summary = resume_summary(args.output, args.hours * 3600, args.interval)
    else:
        args.output.mkdir(parents=True, exist_ok=False)
        summary = RunSummary(now_utc(), args.hours * 3600, args.interval)
    atomic_json(args.output / 'summary.json', summary.snapshot())
    state = 'INTERRUPTED'
    try:
        collector = Collector()
        with (args.output / 'samples.jsonl').open('a', encoding='utf-8', buffering=1) as samples, (
                args.output / 'events.jsonl').open('a', encoding='utf-8', buffering=1) as events:
            while True:
                row = collector.sample()
                changes = summary.add(row)
                samples.write(json.dumps(row, allow_nan=False) + '\n')
                for change in changes:
                    events.write(json.dumps(change, allow_nan=False) + '\n')
                try:
                    atomic_json(args.output / 'summary.json', summary.snapshot())
                except OSError as exc:
                    # Preserve the flushed sample/event journal and keep
                    # observing; a status-file sharing error is not NI failure.
                    events.write(json.dumps(dict(utc=now_utc().isoformat(),
                        entered=['monitor:summary_write_failed'], error=type(exc).__name__)) + '\n')
                    print('Summary write failed: ' + type(exc).__name__, file=sys.stderr, flush=True)
                print(json.dumps(dict(utc=row['utc'], sample=summary.samples, issues=row['issues'])), flush=True)
                if row['monotonic'] - summary.first['monotonic'] >= summary.duration:
                    state = 'COMPLETED'
                    break
                if args.max_samples and summary.samples >= args.max_samples:
                    state = 'SMOKE_CHECK_ONLY'
                    break
                time.sleep(max(0, row['monotonic'] + args.interval - time.monotonic()))
    except Exception:
        state = 'FAILED'
        raise
    finally:
        atomic_json(args.output / 'summary.json', summary.snapshot(state))


if __name__ == '__main__':
    main()
