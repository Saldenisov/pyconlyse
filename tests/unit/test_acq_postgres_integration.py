"""Explicit local database fixture only; no Tango/XP/NI calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import uuid

import pytest

from DeviceServers.control.elyse_acq.telemetry_archive import PostgresStore

CONFIG = os.environ.get('ELYSE_TEST_POSTGRES_CONFIG')
pytestmark = pytest.mark.skipif(not CONFIG, reason='Explicit PostgreSQL fixture configuration required')


@pytest.fixture
def store():
    root = PostgresStore(CONFIG)
    from psycopg import sql
    schema = 'acq_fixture_' + uuid.uuid4().hex
    with root.connect(writer=True) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    # Credentials inherit the private configuration directory ACL, not /tmp.
    fixture = Path(CONFIG).with_name(schema + '.json')
    fixture.write_text(json.dumps(dict(root.config, schema=schema)))
    try:
        value = PostgresStore(fixture)
        value.initialize()
        yield value
    finally:
        assert schema.startswith('acq_fixture_') and len(schema) == len('acq_fixture_') + 32
        with root.connect(writer=True) as conn:
            conn.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        fixture.unlink()


def record():
    return dict(uid='test:' + uuid.uuid4().hex, observed_utc='2026-10-22T10:00:00+00:00',
                kind='snapshot', provenance='test_fixture', receiver_session='test', receiver_count=1,
                snapshot=dict(publications={'C1NI6071E': dict(
                    data=[2**63 + 17, False, None, 1.2345678901234567],
                    error=dict(status=False, code=0, source=''), stale=False, age_seconds=0.1,
                    session_id='test-source', sequence=42, source_seconds_1904=3875510000.25,
                    lv_type=dict(type='LvVariant'))}))


def query(index=0, **kw):
    return dict(bank='C1NI6071E', index=index, start='2026-10-22T09:59:59+00:00',
                end='2026-10-22T10:00:02+00:00', **kw)


def test_actual_postgres_exact_roundtrip_and_idempotency(store):
    row = record()
    store.write_records([row])
    store.write_records([row])
    assert [store.read_history(query(i))['points'][0]['value'] for i in range(4)] == row['snapshot']['publications']['C1NI6071E']['data']
    assert len(store.read_history(query())['points']) == 1
    changed = copy.deepcopy(row)
    changed['snapshot']['publications']['C1NI6071E']['data'][0] = 123
    with pytest.raises(ValueError, match='identity reused'):
        store.write_records([changed])


def test_actual_postgres_pagination_and_input_rejection(store):
    rows = [record() for _ in range(3)]
    store.write_records(rows)
    first = store.read_history(query(limit=2))
    assert len(first['points']) == 2 and not first['complete']
    second = store.read_history(dict(query(limit=2), **first['next_cursor']))
    assert len(second['points']) == 1 and second['complete']
    assert not set(p['uid'] for p in first['points']) & set(p['uid'] for p in second['points'])
    for change in (dict(bank="C1NI6071E'; DROP TABLE x"), dict(index=True), dict(limit=5001), dict(start='2026-10-22T09:00:00')):
        with pytest.raises(ValueError):
            store.read_history(dict(query(), **change))


def test_history_connection_is_read_only(store):
    with store.connect() as conn:
        assert conn.execute('SHOW transaction_read_only').fetchone()[0] == 'on'


def test_bulk_copy_preserves_all_27_banks_and_is_idempotent(store):
    from legacy.xp_acq_agent.elyse_agent.shared_state import BANKS
    records = [record() for _ in range(48)]
    for item in records:
        bank = item['snapshot']['publications']['C1NI6071E']
        item['snapshot']['publications'] = {name: copy.deepcopy(bank) for name in BANKS}
    store.write_records(records)
    store.write_records(records)
    with store.connect() as conn:
        count = conn.execute('SELECT count(*) FROM acq_archive_banks WHERE frame_uid=ANY(%s)',
                             ([item['uid'] for item in records],)).fetchone()[0]
    assert count == 48 * 27


def test_live_archive_is_refused_before_hdf5_open():
    path = Path(__file__).resolve().parents[2] / 'tools' / 'import_acq_hdf5_postgres.py'
    spec = importlib.util.spec_from_file_location('acq_import_fixture', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as folder:
        Path(folder, 'status.json').write_text(json.dumps(dict(state='RUNNING')))
        with pytest.raises(RuntimeError, match='refusing to open'):
            module.require_closed(Path(folder))


def test_closed_archive_imports_only_committed_rows_and_resumes(store):
    import h5py
    base = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('acq_import_fixture', base / 'tools/import_acq_hdf5_postgres.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    recorder_spec = importlib.util.spec_from_file_location('h5_fixture', base / 'tools/record_acq_telemetry_hdf5.py')
    recorder = importlib.util.module_from_spec(recorder_spec)
    recorder_spec.loader.exec_module(recorder)
    archive_id = 'test-' + uuid.uuid4().hex
    try:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            writer = recorder.Archive(path / 'telemetry.h5')
            value = record()
            writer.append('snapshot', dict(observed_utc=value['observed_utc'], snapshot=value['snapshot']))
            writer.append('quality', dict(utc=value['observed_utc'], after='FRESH'))
            writer.close()
            with h5py.File(path / 'telemetry.h5', 'r+') as archive:
                archive['committed_rows'][()] = 1  # Explicit uncommitted tail fixture.
            (path / 'status.json').write_text(json.dumps(dict(state='STOPPED', recorder_id=archive_id)))
            result = module.import_folder(store, path)
            assert result['committed_rows'] == 1
            module.import_folder(store, path)
            with store.connect() as conn:
                assert conn.execute('SELECT count(*) FROM acq_archive_frames WHERE provenance=%s',
                                    ('hdf5:' + archive_id,)).fetchone()[0] == 1
                assert conn.execute('SELECT state FROM acq_archive_imports WHERE archive_id=%s',
                                    (archive_id,)).fetchone()[0] == 'COMPLETE'
    finally:
        uid = f'hdf5:{archive_id}:0'
        with store.connect(writer=True) as conn:
            conn.execute('DELETE FROM acq_archive_banks WHERE frame_uid=%s', (uid,))
            conn.execute('DELETE FROM acq_archive_frames WHERE uid=%s', (uid,))
            conn.execute('DELETE FROM acq_archive_frames WHERE uid=%s', ('hdf5meta:' + archive_id,))
            conn.execute('DELETE FROM acq_archive_imports WHERE archive_id=%s', (archive_id,))
