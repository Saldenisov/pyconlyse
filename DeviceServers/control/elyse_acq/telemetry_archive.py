"""Everest-only durable ingress spool and PostgreSQL history; no device I/O.

The spool commits before RAM acceptance. PostgreSQL delivery is idempotent and
separate from reader/store locks. Existing XP ACK remains conservatively RAM-only
for wire compatibility. This does not recover publications replaced upstream.
"""
from __future__ import annotations

import copy
import datetime as dt
from decimal import Decimal
import hashlib
import json
import re
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import time
import zlib

from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS, SNAPSHOT_PUBLICATION, expand_snapshot
from legacy.xp_acq_control.elyse_agent.shared_state import expand_snapshot as expand_python_snapshot


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":")).encode("utf-8")


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def timestamp(value):
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timezone-qualified timestamp required")
    return result


def telemetry_only_record(record):
    """Copy camera metadata, never pixels, into the Acquisition archive.

    Live authenticated input remains untouched. Keep its original identity
    digest so a legacy spool retry still matches an already committed UID.
    Applying this again at the database boundary also covers old spool rows.
    Counter control memory and its quality/source fields are retained verbatim.
    """
    body = record.get('wire_body')
    packet = body.get('packet') if isinstance(body, dict) else None
    video = packet.get('video_frame') if isinstance(packet, dict) else None
    if not isinstance(video, dict):
        return record
    result = copy.deepcopy(record)
    # An allowlist excludes future encodings/payload fields as well as `data`.
    names = ('source', 'source_session_id', 'simulated', 'sequence',
             'sequence_interpretation', 'capture_session_id', 'observed_utc',
             'sample_elapsed_seconds', 'source_age_seconds', 'width', 'height',
             'pixel_type', 'encoding', 'channel', 'processing',
             'hardware_acknowledged')
    result['wire_body']['packet']['video_frame'] = {
        name: video[name] for name in names if name in video}
    result['archive_image_policy'] = 'metadata_only_no_pixels'
    return result


def ingress_record(body, receiver_session, receiver_count, observed_utc):
    packet = body['packet']
    federated = packet['publication'] == 'ELYSE_OWNER_SNAPSHOT'
    if federated:
        from legacy.xp_acq_control.elyse_agent.federation_wire import expand_owner_frame
        banks = expand_owner_frame(packet)
    elif packet['publication'] == SNAPSHOT_PUBLICATION:
        expand = expand_python_snapshot if packet['producer_kind'] == 'python_acquisition' else expand_snapshot
        banks = expand(packet)
    else:
        banks = {packet['publication']: copy.deepcopy(packet)}
    for bank in banks.values():
        age = body['age_seconds_on_xp'] + (bank.get('source_age_seconds', 0.) if federated else 0.)
        bank.update(age_seconds=age,
                    stale=age >= 2,
                    received_utc_on_everest=observed_utc,
                    relay_id=body['relay_id'], message_id=body['message_id'])
    identity = (f"live:{packet['owner']}:{body['relay_id']}:{body['message_id']}" if federated
                else f"live:{body['relay_id']}:{body['message_id']}")
    source = ('federated_orchestrators' if federated else
              'python_daqmx_acquisition' if packet['producer_kind'] == 'python_acquisition'
              else 'copied_labview_telemetry')
    return telemetry_only_record(dict(uid=identity, kind='snapshot', observed_utc=observed_utc,
                provenance='live_ingress', receiver_session=receiver_session,
                receiver_count=receiver_count, wire_body=body,
                snapshot=dict(source=source, publications=banks,
                              receiver_session=receiver_session,
                              received_this_process=receiver_count)))


class PostgresStore:
    def __init__(self, config_path, *, read_timeout_ms=2000):
        if type(read_timeout_ms) is not int or not 100 <= read_timeout_ms <= 15000:
            raise ValueError('Read timeout must be 100..15000 ms')
        self.read_timeout_ms = read_timeout_ms
        self.config = json.loads(Path(config_path).read_text(encoding='utf-8'))
        if self.config['host'] not in ('127.0.0.1', 'localhost', '::1'):
            raise ValueError('Archive database must be local to Everest')
        schema = self.config.get('schema')
        if schema is not None and not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', schema):
            raise ValueError('Invalid explicit database schema')
        driver = self.config.get('driver_path')
        if driver and driver not in sys.path:
            sys.path.insert(0, driver)
        import psycopg
        from psycopg.types.json import Jsonb
        self.driver, self.Jsonb = psycopg, Jsonb
        self._known_types = set()

    def connect(self, *, writer=False):
        c = self.config
        options = ('-c statement_timeout=10000 -c lock_timeout=1000' if writer
                   else f'-c statement_timeout={self.read_timeout_ms} -c lock_timeout=100 -c default_transaction_read_only=on')
        if c.get('schema'):
            options += ' -c search_path=' + c['schema']
        return self.driver.connect(host=c['host'], port=c['port'], dbname=c['dbname'],
                                   user=c['user'], password=c['password'], connect_timeout=2,
                                   application_name='elyse_archive_writer' if writer else 'elyse_archive_reader',
                                   options=options)

    def initialize(self):
        with self.connect() as conn:
            present = conn.execute("SELECT to_regclass('acq_archive_frames'),to_regclass('acq_archive_types'),"
                                   "to_regclass('acq_archive_banks'),to_regclass('acq_archive_imports')").fetchone()
            if all(present):
                return  # Do not take CREATE INDEX/DDL locks on a running archive.
        with self.connect(writer=True) as conn:
            conn.execute(Path(__file__).with_suffix('.sql').read_text(encoding='utf-8'))

    def write_records(self, records):
        records = list(records)
        for attempt in range(4):
            try:
                return self._write_records_once(records)
            except (self.driver.errors.LockNotAvailable, self.driver.errors.DeadlockDetected,
                    self.driver.errors.SerializationFailure, self.driver.OperationalError):
                if attempt == 3:
                    raise
                time.sleep(min(2, .25 * 2**attempt))

    def _write_records_once(self, records):
        if not records:
            return
        with self.connect() as conn:
            existing = dict(conn.execute('SELECT uid,digest FROM acq_archive_frames WHERE uid=ANY(%s)',
                                         ([record['uid'] for record in records],)).fetchall())
        frames, banks, definitions, expected = [], [], {}, {}
        for record in records:
            # Compute legacy fallback identity before stripping old spool pixels.
            digest = record.get('identity_digest') or hashlib.sha256(encoded(record)).hexdigest()
            record = telemetry_only_record(record)
            raw = encoded(record)
            if record['uid'] in existing:
                if existing[record['uid']] != digest:
                    raise ValueError('Archived identity reused with different content')
                continue
            if record['uid'] in expected and expected[record['uid']] != digest:
                raise ValueError('Archived identity reused with different content')
            expected[record['uid']] = digest
            frames.append((record['uid'], record['observed_utc'], record['kind'], record['provenance'],
                           digest, zlib.compress(raw, 6), record.get('receiver_session'), record.get('receiver_count')))
            for name, bank in record.get('snapshot', {}).get('publications', {}).items():
                if name not in BANKS:
                    raise ValueError('Unknown archive bank')
                definition = bank.get('lv_type')
                type_id = hashlib.sha256(encoded(definition)).hexdigest() if definition else None
                if definition and type_id not in self._known_types:
                    definitions[type_id] = definition
                banks.append((record['uid'], name, record['observed_utc'], self.Jsonb(bank.get('data')),
                              self.Jsonb(bank.get('error', {})), bank.get('stale') is not False,
                              bank.get('age_seconds'), bank.get('session_id'), bank.get('sequence'),
                              Decimal(str(bank['source_seconds_1904'])) if bank.get('source_seconds_1904') is not None else None,
                              bank.get('producer_kind'), type_id))
        if not frames:
            return
        if definitions:
            with self.connect(writer=True) as conn:
                with conn.cursor() as cur:
                    cur.executemany('INSERT INTO acq_archive_types VALUES (%s,%s) ON CONFLICT DO NOTHING',
                                    [(key, self.Jsonb(definitions[key])) for key in sorted(definitions)])
            self._known_types.update(definitions)
        with self.connect(writer=True) as conn:
            with conn.cursor() as cur:
                cur.executemany('INSERT INTO acq_archive_frames '
                                '(uid,observed_utc,kind,provenance,digest,payload_zlib,receiver_session,receiver_count) '
                                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING', frames)
                actual = dict(cur.execute('SELECT uid,digest FROM acq_archive_frames WHERE uid=ANY(%s)',
                                          (list(expected),)).fetchall())
                if actual != expected:
                    raise ValueError('Archived identity reused with different content')
                if banks:
                    if len(banks) > 1024:
                        cur.execute('CREATE TEMP TABLE acq_bank_stage (LIKE acq_archive_banks) ON COMMIT DROP')
                        with cur.copy('COPY acq_bank_stage FROM STDIN') as pipe:
                            for row in banks:
                                pipe.write_row(row)
                        cur.execute('INSERT INTO acq_archive_banks SELECT * FROM acq_bank_stage ON CONFLICT DO NOTHING')
                    else:
                        cur.executemany('INSERT INTO acq_archive_banks VALUES '
                                        '(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING', banks)

    def read_history(self, request):
        if type(request) is not dict or set(request) - {'bank', 'index', 'start', 'end', 'limit', 'cursor_time', 'cursor_uid'}:
            raise ValueError('Invalid history request')
        bank, index = request.get('bank'), request.get('index')
        limit = request.get('limit', 1000)
        if bank not in BANKS or type(index) is not int or not 0 <= index <= 8191:
            raise ValueError('Known bank and integer index 0..8191 required')
        if type(limit) is not int or not 1 <= limit <= 5000:
            raise ValueError('History limit must be 1..5000')
        start, end = timestamp(request['start']), timestamp(request['end'])
        if end <= start:
            raise ValueError('History end must follow start')
        cursor_time = timestamp(request.get('cursor_time', request['start']))
        cursor_uid = request.get('cursor_uid', '')
        if not isinstance(cursor_uid, str) or len(cursor_uid) > 200:
            raise ValueError('Invalid cursor')
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT observed_utc,frame_uid,CASE WHEN jsonb_typeof(data->%s) IN ('number','boolean','null') "
                'THEN data->%s ELSE NULL END,error,stale,age_seconds,source_session,source_sequence, '
                'jsonb_typeof(data->%s) '
                'FROM acq_archive_banks WHERE bank=%s AND observed_utc >= %s AND observed_utc < %s '
                'AND (observed_utc,frame_uid)>(%s,%s) ORDER BY observed_utc,frame_uid LIMIT %s',
                (index, index, index, bank, start, end, cursor_time, cursor_uid, limit + 1)).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        values = [dict(observed_utc=r[0].isoformat(), uid=r[1], value=r[2], error=r[3],
                       stale=r[4], age_seconds=r[5], source_session=r[6],
                       source_sequence=str(r[7]) if r[7] is not None else None,
                       value_type=r[8], scalar_available=r[8] in ('number','boolean','null')) for r in rows]
        cursor = dict(cursor_time=values[-1]['observed_utc'], cursor_uid=values[-1]['uid']) if more else None
        return dict(schema_version=1, source='postgresql_archive', bank=bank, index=index,
                    points=values, next_cursor=cursor, complete=not more,
                    timestamps='Everest observation time; not qualified card sample time',
                    hardware_commands_sent=False)

    def summary(self):
        with self.connect() as conn:
            count, first, last = conn.execute('SELECT count(*),min(observed_utc),max(observed_utc) FROM acq_archive_frames').fetchone()
            imports = conn.execute('SELECT archive_id,source_path,committed_rows,imported_rows,state FROM acq_archive_imports').fetchall()
        return dict(frames=count, first_utc=first.isoformat() if first else None,
                    last_utc=last.isoformat() if last else None,
                    imports=[dict(zip(('archive_id','path','committed_rows','imported_rows','state'), row)) for row in imports])


class DurableArchive:
    """Bounded disk queue. No DB access under telemetry RAM/command-view locks."""
    def __init__(self, config_path, *, store=None, max_pending=100000, min_free_bytes=5 * 1024**3):
        self.store = store or PostgresStore(config_path)
        config = json.loads(Path(config_path).read_text(encoding='utf-8'))
        self.spool_path = Path(config['spool_path']).resolve()
        self.spool_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.max_pending, self.min_free_bytes = max_pending, min_free_bytes
        self.db = sqlite3.connect(self.spool_path, timeout=1, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS pending (ordinal INTEGER PRIMARY KEY, uid TEXT UNIQUE NOT NULL, digest TEXT NOT NULL, payload BLOB NOT NULL)')
        self.db.commit()
        pending = self.db.execute('SELECT count(*) FROM pending').fetchone()[0]
        self.cached = dict(enabled=True, backend='postgresql', spool=str(self.spool_path),
                           pending=pending, committed_this_process=0, last_commit_utc=None,
                           last_error='', state='STARTING', durable_ingress=True,
                           image_policy='metadata_only_no_pixels')
        self.closed = False
        self.stop_event, self.wake = threading.Event(), threading.Event()
        self.thread = None

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Archive already started')
        self.thread = threading.Thread(target=self._run, name='acq-postgres-writer', daemon=False)
        self.thread.start()

    def append_ingress(self, body, digest, receiver_session, receiver_count, observed_utc):
        record = ingress_record(body, receiver_session, receiver_count, observed_utc)
        record['identity_digest'] = digest
        self.append(record)

    def append(self, record):
        digest = record.get('identity_digest') or hashlib.sha256(encoded(record)).hexdigest()
        record = telemetry_only_record(record)
        if record.get('identity_digest') is None:
            record = dict(record, identity_digest=digest)
        raw = encoded(record)
        with self.lock:
            if self.closed:
                raise RuntimeError('Archive spool closed')
            prior = self.db.execute('SELECT digest FROM pending WHERE uid=?', (record['uid'],)).fetchone()
            if prior:
                if prior[0] != digest:
                    raise ValueError('Pending identity reused with different content')
                return
            if self.cached['pending'] >= self.max_pending or shutil.disk_usage(self.spool_path.parent).free < self.min_free_bytes:
                self.cached = dict(self.cached, state='SPOOL_FULL', last_error='Durable archive capacity reached; ingress not acknowledged')
                raise RuntimeError(self.cached['last_error'])
            try:
                self.db.execute('INSERT INTO pending(uid,digest,payload) VALUES (?,?,?)',
                                (record['uid'], digest, zlib.compress(raw, 3)))
                self.db.commit()
            except Exception:
                self.db.rollback()
                self.cached = dict(self.cached, state='SPOOL_ERROR', last_error='Durable spool commit failed; ingress not acknowledged')
                raise
            self.cached = dict(self.cached, pending=self.cached['pending'] + 1)
        self.wake.set()

    def status(self):
        # Copy-on-write reference: status readers never acquire the disk lock.
        return copy.deepcopy(self.cached)

    def drain_once(self):
        with self.lock:
            rows = self.db.execute('SELECT ordinal,payload FROM pending ORDER BY ordinal LIMIT 16').fetchall()
        if not rows:
            return 0
        records = [json.loads(zlib.decompress(row[1])) for row in rows]
        self.store.write_records(records)
        with self.lock:
            self.db.executemany('DELETE FROM pending WHERE ordinal=?', [(row[0],) for row in rows])
            self.db.commit()
            self.cached = dict(self.cached, pending=self.cached['pending'] - len(rows),
                               committed_this_process=self.cached['committed_this_process'] + len(rows),
                               last_commit_utc=utc(), last_error='', state='RUNNING')
        return len(rows)

    def _run(self):
        initialized = False
        while not self.stop_event.is_set():
            try:
                if not initialized:
                    self.store.initialize()
                    initialized = True
                if self.drain_once():
                    continue
                with self.lock:
                    self.cached = dict(self.cached, state='RUNNING', last_error='')
                self.wake.wait(0.2)
                self.wake.clear()
            except Exception as error:
                with self.lock:
                    self.cached = dict(self.cached, state='DEGRADED_RETRY', last_error=type(error).__name__)
                self.stop_event.wait(1)

    def close(self, timeout=5):
        if self.closed:
            return True
        self.stop_event.set()
        self.wake.set()
        if self.thread is not None:
            self.thread.join(timeout)
            if self.thread.is_alive():
                return False
        with self.lock:
            self.closed = True
            self.cached = dict(self.cached, state='STOPPED_WITH_PENDING' if self.cached['pending'] else 'STOPPED')
            self.db.close()
        return True
