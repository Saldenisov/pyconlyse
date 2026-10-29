"""Persistent display cache and drafts; never opens HDF5 or sends device commands."""
import json
import math
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

from flask import Blueprint, current_app, jsonify, request
from mutation_auth import install_mutation_auth
from error_journal import ErrorJournal

workspace_api = Blueprint('supervision_workspace_api', __name__, url_prefix='/api/elyse/supervision/workspace')
install_mutation_auth(workspace_api, protected_get_endpoints=('history', 'get_synchronization', 'get_errors'))
WINDOWS = (5, 15, 30, 60, 120)
RETENTION_MS = 6 * 60 * 60 * 1000
DISPLAY_MAP = Path(__file__).resolve().parents[1] / 'frontend/src/elyseLiveDisplayMap.json'
_store_lock = Lock()


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _number(record, index):
    if not isinstance(record, dict) or record.get('stale') is not False:
        return None
    age = record.get('age_seconds')
    error = record.get('error', {})
    if (type(age) not in (int, float) or not math.isfinite(age) or not 0 <= age < 2
            or error.get('status') is not False or error.get('code') != 0):
        return None
    schema = record.get('lv_type', {})
    if schema.get('type') == 'LvVariant':
        schema = schema.get('contained_type', {})
    data, fields = record.get('data'), schema.get('fields')
    if (schema.get('type') != 'Cluster' or not isinstance(data, list) or len(data) != 64
            or not isinstance(fields, list) or len(fields) != 64 or fields[index].get('type') != 'DBL'):
        return None
    value = data[index]
    return value if type(value) in (int, float) and math.isfinite(value) else None


def project_sample(payload, rules, now_ms):
    snapshot = payload.get('snapshot', {})
    session, count = snapshot.get('receiver_session'), snapshot.get('received_this_process')
    if not isinstance(session, str) or not 1 <= len(session) <= 128 or type(count) is not int or not 0 <= count < 2**64:
        raise ValueError('Receiver identity unavailable')
    sample = {'time': now_ms, 'session': session, 'receipt': str(count), 'canon': None, 'section': None}
    banks = snapshot.get('publications', {})
    for rule in rules:
        record = banks.get(rule['bank'])
        if isinstance(record, dict):
            schema = record.get('lv_type', {})
            if schema.get('type') == 'LvVariant':
                schema = schema.get('contained_type', {})
            raw = _number(record, rule['index']) if schema.get('name') == rule['bank'] else None
        else:
            raw = None
        value = raw
        if raw is not None:
            if rule['transform'] == 'offset_gain':
                value = (raw - rule['offset']) * rule['scale']
            elif rule['transform'] == 'identity':
                value = raw * rule.get('scale', 1)
            else:
                value = None
        if value is not None and not math.isfinite(value):
            value = None
        key = 'canon' if rule['id'] == 'fluides:5' else 'section' if rule['id'] == 'fluides:22' else rule['id']
        sample[key] = value if payload.get('server_state') == 'ON' else None
    return session, str(count), sample


class WorkspaceStore:
    def __init__(self, path, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        mapping = json.loads(DISPLAY_MAP.read_text(encoding='utf-8'))
        self.rules = [r for r in mapping['rules'] if r['page'] == 'vide' and r['kind'] == 'number'
                      or r['id'] in ('fluides:5', 'fluides:22')]
        self.stop_event = Event()
        self.start_lock = Lock()
        self.thread = None
        self.last_error = ''
        self.last_update = None
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS display_samples (session TEXT, receipt TEXT, time_ms INTEGER, value TEXT, PRIMARY KEY(session, receipt))')
            db.execute('CREATE INDEX IF NOT EXISTS display_sample_time ON display_samples(time_ms)')
            db.execute('CREATE TABLE IF NOT EXISTS drafts (name TEXT PRIMARY KEY, revision INTEGER NOT NULL, value TEXT NOT NULL, updated_at TEXT NOT NULL)')
        # Alarm reads must not wait seconds behind a busy display-cache writer.
        self.journal = ErrorJournal(lambda: self.connect(timeout=0.25), self.clock)
        self.journal_error = ''
        self.journal_errors = {}
        self.journal_error_lock = Lock()

    @contextmanager
    def connect(self, timeout=5):
        connection = sqlite3.connect(str(self.path), timeout=timeout)
        try:
            connection.execute('PRAGMA synchronous=FULL')
            with connection:
                yield connection
        finally:
            connection.close()

    def gap(self, error, journal=True):
        self.last_error = str(error)[:300]
        if journal:
            self.record_journal(self.journal.unavailable, error)
        now_ms = int(self.clock() * 1000)
        sample = {'time': now_ms, 'session': 'gap', 'receipt': str(now_ms), 'canon': None, 'section': None}
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO display_samples VALUES (?, ?, ?, ?)',
                       ('gap', str(now_ms), now_ms, json.dumps(sample)))
            db.execute('DELETE FROM display_samples WHERE time_ms < ?', (now_ms - RETENTION_MS,))

    def ingest(self, payload):
        self.record_journal(self.journal.observe, payload)
        now_ms = int(self.clock() * 1000)
        session, receipt, sample = project_sample(payload, self.rules, now_ms)
        if not any(sample.get('canon' if r['id'] == 'fluides:5' else 'section' if r['id'] == 'fluides:22' else r['id']) is not None for r in self.rules):
            self.gap('No fresh display channels available', journal=False)
            return
        with self.connect() as db:
            db.execute('INSERT OR IGNORE INTO display_samples VALUES (?, ?, ?, ?)',
                       (session, receipt, now_ms, json.dumps(sample, allow_nan=False)))
            db.execute('DELETE FROM display_samples WHERE time_ms < ?', (now_ms - RETENTION_MS,))
        self.last_error, self.last_update = '', _utc()

    def record_journal(self, callback, *args):
        # Storage failure cannot remove or replace a live alarm response.
        key = ('cooling:' + args[0] if callback.__name__ in ('observe_cooling', 'cooling_unavailable') and args
               else 'receiver')
        error = ''
        try:
            callback(*args)
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, OverflowError) as exc:
            error = str(exc)[:300]
        with self.journal_error_lock:
            if error:
                self.journal_errors[key] = error
            else:
                self.journal_errors.pop(key, None)
            self.journal_error = '; '.join(sorted(set(self.journal_errors.values())))

    def query(self, minutes):
        if type(minutes) is not int or minutes not in WINDOWS:
            raise ValueError('History window must be 5, 15, 30, 60 or 120 minutes')
        cutoff = int(self.clock() * 1000) - minutes * 60000
        with self.connect() as db:
            # At most one display sample per second, not a full acquisition archive.
            rows = db.execute('SELECT value FROM display_samples WHERE time_ms >= ? ORDER BY time_ms DESC LIMIT ?',
                              (cutoff, minutes * 60)).fetchall()
        return dict(schema_version=1, execution_allowed=False, hardware_writes=False,
                    source='SQLITE_DISPLAY_CACHE', canonical_archive_read=False, minutes=minutes,
                    requested_native_source='Supervision VI', native_history_available=False,
                    samples=[json.loads(row[0]) for row in reversed(rows)],
                    storage='server_sqlite', retention_minutes=360, observed_interval_s=1,
                    receiver_latest_only=True, archive_complete=False,
                    last_update=self.last_update, error=self.last_error,
                    note='Web display cache only. Native Supervision VI history is not exported by the current telemetry contract. No active HDF5 file is opened. Earlier uncached history is unavailable.')

    def start(self, reader):
        with self.start_lock:
            if self.thread is not None and self.thread.is_alive():
                return
            self.stop_event.clear()

            def observe():
                while not self.stop_event.is_set():
                    try:
                        self.ingest(reader())
                    except Exception as exc:
                        try:
                            self.gap(type(exc).__name__ + ': ' + str(exc)[:300])
                        except Exception as storage_error:
                            self.last_error = 'Display cache storage unavailable: ' + str(storage_error)[:250]
                    self.stop_event.wait(1.0)
            self.thread = Thread(target=observe, name='supervision-display-cache', daemon=True)
            self.thread.start()

    def synchronization(self):
        with self.connect() as db:
            row = db.execute("SELECT revision, value, updated_at FROM drafts WHERE name='synchronization'").fetchone()
        return dict(revision=row[0] if row else 0, values=json.loads(row[1]) if row else None,
                    updated_at=row[2] if row else None, hardware_applied=False, draft_only=True)

    def save_synchronization(self, data):
        if type(data) is not dict or set(data) != {'expected_revision', 'values'}:
            raise ValueError('Expected values and expected_revision only')
        values, revision = data['values'], data['expected_revision']
        if (type(revision) is not int or not 0 <= revision < 2**53 - 1 or type(values) is not list or len(values) != 33
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in values)):
            raise ValueError('Synchronization requires 33 finite numeric values and an integer revision')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute("SELECT revision FROM drafts WHERE name='synchronization'").fetchone()
            if (row[0] if row else 0) != revision:
                raise RuntimeError('Draft changed in another session; reload before saving')
            db.execute("INSERT OR REPLACE INTO drafts VALUES ('synchronization', ?, ?, ?)",
                       (revision + 1, json.dumps(values, allow_nan=False), _utc()))
        return self.synchronization()


def _read_receiver():
    # Existing receive-only Tango facade; never constructs an XP/card/command owner.
    import tango_gateway
    from acq_telemetry_api import DEVICE, present_snapshot
    proxy = tango_gateway.create_device_proxy(DEVICE)
    proxy.set_timeout_millis(2000)
    state, raw = proxy.read_attributes(['State', 'telemetry_json'])
    if state.has_failed or raw.has_failed:
        raise ValueError('Telemetry receiver unavailable')
    return present_snapshot(raw.value, str(state.value))


def store():
    app = current_app._get_current_object()
    with _store_lock:
        if 'supervision_workspace_store' not in app.extensions:
            app.extensions['supervision_workspace_store'] = WorkspaceStore(app.config.get(
                'ELYSE_WORKSPACE_DB', str(Path.home() / '.pyconlyse' / 'supervision_workspace.sqlite3')))
        result = app.extensions['supervision_workspace_store']
    if not app.testing and app.config.get('ELYSE_DISPLAY_CACHE_ENABLED', True):
        result.start(_read_receiver)
    return result


@workspace_api.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@workspace_api.get('/history')
def history():
    try:
        return jsonify(store().query(int(request.args.get('minutes', '30'))))
    except (ValueError, OverflowError) as exc:
        return jsonify(schema_version=1, execution_allowed=False, error=str(exc)), 400
    except (OSError, sqlite3.Error) as exc:
        return jsonify(schema_version=1, execution_allowed=False, error=str(exc)), 503


@workspace_api.get('/errors')
def get_errors():
    try:
        if set(request.args) - {'day', 'limit', 'cursor'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
            raise ValueError('Expected day, limit and cursor only')
        journal_store = store()
        result = journal_store.journal.query(request.args.get('day', ''), int(request.args.get('limit', '100')),
                                             request.args.get('cursor', ''))
        return jsonify(**result, journal_error=journal_store.journal_error,
                       observer_running=bool(journal_store.thread and journal_store.thread.is_alive()))
    except (ValueError, OverflowError) as exc:
        return jsonify(schema_version=1, execution_allowed=False, error=str(exc)), 400
    except (OSError, sqlite3.Error) as exc:
        return jsonify(schema_version=1, execution_allowed=False, error='Journal SQLite indisponible: ' + str(exc)), 503


@workspace_api.get('/synchronization')
def get_synchronization():
    try:
        return jsonify(schema_version=1, execution_allowed=False, **store().synchronization())
    except (OSError, sqlite3.Error) as exc:
        return jsonify(schema_version=1, execution_allowed=False, error=str(exc)), 503


@workspace_api.post('/synchronization')
def save_synchronization():
    if request.content_length is not None and request.content_length > 8192:
        return jsonify(schema_version=1, execution_allowed=False, error='Draft too large'), 413
    if request.mimetype != 'application/json':
        return jsonify(schema_version=1, execution_allowed=False, error='application/json required'), 415
    try:
        from elyse_supervision_api import strict_json
        raw = request.stream.read(8193)
        if len(raw) > 8192:
            return jsonify(schema_version=1, execution_allowed=False, error='Draft too large'), 413
        return jsonify(schema_version=1, execution_allowed=False, **store().save_synchronization(strict_json(raw)))
    except (ValueError, OverflowError) as exc:
        return jsonify(schema_version=1, execution_allowed=False, error=str(exc)), 400
    except RuntimeError as exc:
        return jsonify(schema_version=1, execution_allowed=False, error=str(exc)), 409
    except (OSError, sqlite3.Error) as exc:
        return jsonify(schema_version=1, execution_allowed=False, error=str(exc)), 503
