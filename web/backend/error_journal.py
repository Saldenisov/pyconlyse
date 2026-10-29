"""Append-only web observations in the SuperVision DB; no device access."""

import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo('Europe/Paris')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))


def source_name(value):
    return {'copied_labview_telemetry': 'labview',
            'python_daqmx_acquisition': 'xp_control'}.get(value, value or 'receiver')


class ErrorJournal:
    def __init__(self, connect, clock):
        self.connect, self.clock = connect, clock
        with connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS error_journal_events (
                    id INTEGER PRIMARY KEY, identity TEXT NOT NULL UNIQUE,
                    observed_us INTEGER NOT NULL, observed_utc TEXT NOT NULL,
                    paris_day TEXT NOT NULL, recorded_utc TEXT NOT NULL,
                    source TEXT NOT NULL, category TEXT NOT NULL,
                    circuit TEXT, kind TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS error_journal_time
                    ON error_journal_events(observed_us DESC, id DESC);
                CREATE INDEX IF NOT EXISTS error_journal_day
                    ON error_journal_events(paris_day, observed_us DESC, id DESC);
                CREATE TABLE IF NOT EXISTS error_journal_state (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS error_journal_sources (
                    source TEXT PRIMARY KEY, observed_utc TEXT NOT NULL, payload TEXT NOT NULL);
            ''')

    def now(self):
        return datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()

    def append(self, db, source, category, event, identity=None):
        raw = canonical(event)
        if not isinstance(event.get('observed_utc'), str):
            raise ValueError('Journal event requires original timestamp')
        stamp = datetime.fromisoformat(event['observed_utc'].replace('Z', '+00:00'))
        if stamp.utcoffset() is None or not isinstance(event.get('kind'), str) or not event['kind']:
            raise ValueError('Journal event requires kind and timezone-qualified timestamp')
        if len(raw.encode('utf-8')) > 65536:
            raise ValueError('Journal event exceeds 64 KiB')
        utc = stamp.astimezone(timezone.utc)
        delta = utc - datetime(1970, 1, 1, tzinfo=timezone.utc)
        micros = (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds
        db.execute('INSERT OR IGNORE INTO error_journal_events '
                   '(identity, observed_us, observed_utc, paris_day, recorded_utc, source, category, circuit, kind, payload) '
                   'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   (identity or uuid.uuid4().hex, micros, utc.isoformat(), stamp.astimezone(PARIS).date().isoformat(),
                    self.now(), source, category, event.get('circuit'), event['kind'], raw))

    def transition(self, db, key, value, source, kind, details, initially_bad=False):
        encoded = canonical(value)
        old = db.execute('SELECT value FROM error_journal_state WHERE name=?', (key,)).fetchone()
        if old and old[0] == encoded:
            return
        if old or initially_bad:
            self.append(db, source, 'web_observation', dict(
                kind=kind, observed_utc=self.now(), **details))
        db.execute('INSERT OR REPLACE INTO error_journal_state VALUES (?, ?)', (key, encoded))

    def cooling(self, db, source, safety):
        self.transition(db, source + ':cooling_available', True, source, 'COOLING_SOURCE_RESTORED', {})
        events = safety.get('journal', [])
        if not isinstance(events, list) or len(events) > 1000:
            raise ValueError('Invalid source alarm journal')
        for event in events:
            if not isinstance(event, dict):
                raise ValueError('Invalid source alarm event')
            # Receiver session is deliberately excluded: old events can be
            # republished by a new session. Preserve original event fields.
            identity = hashlib.sha256(canonical([source, event]).encode('utf-8')).hexdigest()
            self.append(db, source, 'source_alarm', event, identity)
        quality = safety.get('quality', 'UNKNOWN')
        self.transition(db, source + ':cooling_quality', quality, source, 'COOLING_QUALITY_CHANGED',
                        dict(quality=quality), quality != 'FRESH')
        for field, kind in (('journal_error', 'SOURCE_JOURNAL_ERROR'), ('stop_error', 'SHUTDOWN_ERROR')):
            error = safety.get(field) or ''
            self.transition(db, source + ':' + field, error, source,
                            kind if error else kind + '_CLEARED', dict(error=error), bool(error))
        status = {key: safety.get(key) for key in ('quality', 'active', 'stop_state', 'journal_error',
                  'journal_durable', 'automatic_stop_available', 'observed_utc')}
        self.status(db, source, status)

    def status(self, db, source, status):
        db.execute('INSERT OR REPLACE INTO error_journal_sources VALUES (?, ?, ?)',
                   (source, self.now(), canonical(status)))

    def observe_cooling(self, source, safety):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.cooling(db, source_name(source), safety)

    def cooling_unavailable(self, source, error):
        source = source_name(source)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.transition(db, source + ':cooling_available', False, source, 'COOLING_SOURCE_UNAVAILABLE',
                            dict(error=str(error)), initially_bad=True)
            self.status(db, source, dict(quality='UNAVAILABLE', error=str(error)))

    def observe(self, payload):
        snapshot = payload.get('snapshot', {})
        source = source_name(snapshot.get('source'))
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.transition(db, 'receiver_available', True, source, 'TELEMETRY_RESTORED',
                            dict(receiver_session=snapshot.get('receiver_session')))
            self.transition(db, 'receiver_source', source, source, 'TELEMETRY_SOURCE_CHANGED', dict(source=source))
            quality = payload.get('quality', 'UNKNOWN')
            self.transition(db, source + ':quality', quality, source, 'TELEMETRY_QUALITY_CHANGED',
                            dict(quality=quality, missing_banks=payload.get('missing_banks', []),
                                 stale_banks=payload.get('stale_banks', []), error_banks=payload.get('error_banks', [])),
                            quality != 'FRESH')
            records = snapshot.get('publications', {})
            for bank in payload.get('expected_banks', records):
                if bank not in records:
                    self.transition(db, source + ':bank:' + bank, dict(missing=True), source, 'BANK_MISSING',
                                    dict(bank=bank, missing=True), initially_bad=True)
                    continue
                record = records[bank]
                error = record.get('error', {})
                failed = error.get('status') is not False or error.get('code') != 0
                # Age and sequence change every poll, so are evidence, not the
                # transition identity. Stale data never becomes bank recovery.
                age = record.get('age_seconds')
                stale = record.get('stale') is not False or type(age) not in (int, float) or not 0 <= age < 2
                state = dict(error=error, stale=stale)
                kind = 'BANK_READ_ERROR' if failed else 'BANK_STALE' if stale else 'BANK_CURRENT'
                self.transition(db, source + ':bank:' + bank, state, source, kind,
                                dict(bank=bank, **state, age_seconds=age, sequence=record.get('sequence')),
                                failed or stale)
            safety = payload.get('cooling_safety') or snapshot.get('cooling_safety')
            if isinstance(safety, dict):
                self.cooling(db, source, safety)
            self.status(db, 'receiver', dict(quality=quality, source=source,
                        receiver_session=snapshot.get('receiver_session'), error=''))

    def unavailable(self, error):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.transition(db, 'receiver_available', False, 'receiver', 'TELEMETRY_UNAVAILABLE',
                            dict(error=str(error)), initially_bad=True)
            self.status(db, 'receiver', dict(quality='UNAVAILABLE', error=str(error)))

    def query(self, day='', limit=100, cursor=''):
        if day and date.fromisoformat(day).isoformat() != day:
            raise ValueError('Expected day YYYY-MM-DD')
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Journal limit must be 1..200')
        clauses, args = [], []
        if day:
            clauses.append('paris_day=?')
            args.append(day)
        if cursor:
            stamp, row_id = (int(part) for part in cursor.split(':'))
            if not 0 < row_id < 2**63 or not -(2**63) <= stamp < 2**63:
                raise ValueError('Invalid journal cursor')
            clauses.append('(observed_us, id) < (?, ?)')
            args.extend((stamp, row_id))
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        with self.connect() as db:
            rows = db.execute('SELECT id, observed_us, observed_utc, paris_day, recorded_utc, source, '
                              'category, circuit, kind, payload FROM error_journal_events' + where +
                              ' ORDER BY observed_us DESC, id DESC LIMIT ?', (*args, limit + 1)).fetchall()
            days = db.execute('SELECT paris_day, COUNT(*) FROM error_journal_events GROUP BY paris_day '
                              'ORDER BY paris_day DESC LIMIT 366').fetchall()
            sources = db.execute('SELECT source, observed_utc, payload FROM error_journal_sources ORDER BY source').fetchall()
            first = db.execute('SELECT MIN(recorded_utc) FROM error_journal_events').fetchone()[0]
        page = rows[:limit]
        return dict(schema_version=1, execution_allowed=False, hardware_writes=False, storage='server_sqlite',
                    timezone='Europe/Paris', day=day or None, observed_utc=self.now(),
                    events=[dict(id=row[0], observed_utc=row[2], day=row[3], recorded_utc=row[4], source=row[5],
                                 category=row[6], circuit=row[7], kind=row[8], details=json.loads(row[9])) for row in page],
                    days=[dict(day=d, count=n) for d, n in days],
                    next_cursor=f'{page[-1][1]}:{page[-1][0]}' if len(rows) > limit else None,
                    sources=[dict(source=s, last_observed_utc=t, **json.loads(p))
                             for s, t, p in sources if s != 'receiver'] +
                            [dict(stream=s, last_observed_utc=t, **json.loads(p))
                             for s, t, p in sources if s == 'receiver'],
                    archive_complete=False, first_recorded_utc=first,
                    note='Événements observés par le serveur Web, conservés sans purge. '
                         'Le journal source ne publie que ses événements récents ; les événements antérieurs non reçus '
                         'ne peuvent pas être reconstitués. Une indication de défaut ne prouve pas une perte physique d’eau.')
