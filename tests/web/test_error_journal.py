"""Temporary SQLite and synthetic observations only; no hardware or services."""
from copy import deepcopy
import pytest
from tests.web import test_supervision_workspace as workspace_tests
from supervision_workspace_api import WorkspaceStore

sample = workspace_tests.sample
workspace = workspace_tests.workspace

ROOT = '/api/elyse/supervision/workspace/errors'


def safety(*events):
    return dict(journal=list(events), quality='FRESH', journal_error='', journal_durable=True,
                active=False, stop_state='NONE', automatic_stop_available=False)


def event(stamp='2026-10-25T23:10:00Z', kind='CIRCULATION_LOST', **extra):
    return dict(observed_utc=stamp, kind=kind, circuit='CANON',
                causes=[dict(bank='C3_IN_DIO96', index=0, raw=True, signal='220V')], **extra)


def read(workspace, **query):
    response = workspace.client.get(ROOT, query_string=query)
    assert response.status_code == 200, response.json
    return response.json


def test_source_history_deduplicated_across_polling_sessions_and_db_restart(workspace):
    original = event(incident_id='prior-incident')
    observed = safety(original)
    for _ in range(3):
        workspace.store.journal.observe_cooling('labview', observed)
    restarted = WorkspaceStore(workspace.store.path, clock=lambda: workspace.clock[0])
    restarted.journal.observe_cooling('copied_labview_telemetry', observed)
    rows = restarted.journal.query()['events']
    assert len(rows) == 1
    assert rows[0]['details'] == original
    assert rows[0]['source'] == 'labview'
    assert rows[0]['day'] == '2026-10-26'  # Paris midnight, not UTC day
    assert read(workspace)['archive_complete'] is False


def test_latest_first_and_complete_pagination_including_same_timestamp(workspace):
    values = [event(kind='EVENT_' + str(i)) for i in range(5)]
    workspace.store.journal.observe_cooling('labview', safety(*values))
    first = read(workspace, limit=2)
    second = read(workspace, limit=2, cursor=first['next_cursor'])
    third = read(workspace, limit=2, cursor=second['next_cursor'])
    rows = first['events'] + second['events'] + third['events']
    assert [row['kind'] for row in rows] == ['EVENT_4', 'EVENT_3', 'EVENT_2', 'EVENT_1', 'EVENT_0']
    assert third['next_cursor'] is None
    assert first['days'] == [dict(day='2026-10-26', count=5)]


def test_dst_repeated_hour_ordered_by_utc_and_no_day_leak(workspace):
    workspace.store.journal.observe_cooling('labview', safety(
        event('2026-10-25T00:30:00Z', 'SUMMER'),  # Paris 02:30 UTC+2
        event('2026-10-25T01:30:00Z', 'WINTER'),  # Paris 02:30 UTC+1
        event('2026-10-24T21:59:59Z', 'PREVIOUS_DAY')))
    rows = read(workspace, day='2026-10-25')['events']
    assert [row['kind'] for row in rows] == ['WINTER', 'SUMMER']
    assert len(read(workspace, day='2026-10-24')['events']) == 1


def test_errors_retained_beyond_live_window_and_display_six_hour_purge(workspace):
    for i in range(130):
        workspace.store.journal.observe_cooling('labview', safety(event(kind='E_' + str(i))))
    workspace.clock[0] += 7 * 3600
    workspace.store.gap('offline')
    rows = read(workspace, limit=200)['events']
    assert len([row for row in rows if row['category'] == 'source_alarm']) == 130
    assert rows[0]['kind'] == 'TELEMETRY_UNAVAILABLE'


def test_bank_errors_staleness_and_recovery_are_transitions_not_poll_noise(workspace):
    payload = sample()
    payload['quality'] = 'FRESH'
    payload['snapshot']['source'] = 'copied_labview_telemetry'
    workspace.store.ingest(payload)
    assert read(workspace)['events'] == []
    broken = deepcopy(payload)
    bank = broken['snapshot']['publications']['C1NI6071E']
    bank['error'] = dict(status=True, code=-200, source='NI read failed')
    workspace.store.ingest(broken)
    bank['sequence'] = 999
    workspace.store.ingest(broken)
    bank['error'] = dict(status=False, code=0, source='')
    bank['stale'] = True
    workspace.store.ingest(broken)
    workspace.store.ingest(payload)
    rows = read(workspace)['events']
    assert [r['kind'] for r in rows] == ['BANK_CURRENT', 'BANK_STALE', 'BANK_READ_ERROR']
    assert rows[-1]['details']['error']['code'] == -200


def test_telemetry_outage_repeats_once_then_restores_without_fake_hardware_recovery(workspace):
    workspace.store.gap('timeout')
    workspace.store.gap('timeout')
    payload = sample()
    payload['quality'] = 'STALE'
    workspace.store.ingest(payload)
    kinds = [r['kind'] for r in read(workspace)['events']]
    assert kinds.count('TELEMETRY_UNAVAILABLE') == 1
    assert kinds.count('TELEMETRY_RESTORED') == 1
    assert 'TELEMETRY_QUALITY_CHANGED' in kinds
    assert 'CIRCULATION_RESTORED' not in kinds


def test_source_journal_errors_remain_explicit_and_sources_separate(workspace):
    workspace.store.journal.observe_cooling('labview', safety(event()))
    python = safety(event())
    python['journal_error'] = 'Prior writer did not close cleanly'
    python['journal_durable'] = False
    workspace.store.journal.observe_cooling('xp_runtime', python)
    data = read(workspace)
    assert len([r for r in data['events'] if r['category'] == 'source_alarm']) == 2
    assert any(s.get('journal_error') == python['journal_error'] for s in data['sources'])
    assert any(r['kind'] == 'SOURCE_JOURNAL_ERROR' for r in data['events'])


def test_failed_write_is_visible_and_does_not_discard_live_display(workspace, monkeypatch):
    def broken(*args):
        raise OSError('disk full')
    monkeypatch.setattr(workspace.store.journal, 'observe', broken)
    workspace.store.ingest(sample())
    assert read(workspace)['journal_error'] == 'disk full'
    assert workspace.store.query(30)['samples'][0]['canon'] == 20.5


def test_another_source_success_cannot_hide_pending_archive_write_error(workspace, monkeypatch):
    def observe_cooling(*args):
        raise OSError('Python archive full')
    workspace.store.record_journal(observe_cooling, 'xp_runtime', safety())
    workspace.store.ingest(sample())
    assert 'Python archive full' in read(workspace)['journal_error']


@pytest.mark.parametrize('query', [dict(day='2026-02-30'), dict(day='20261026'), dict(limit='0'),
    dict(limit='201'), dict(limit='no'), dict(cursor='bad'), dict(cursor='1:0'),
    dict(cursor='9999999999999999999999:1'), dict(path='C:/other.db'), [('day', ''), ('day', '')]])
def test_invalid_queries_rejected(workspace, query):
    assert workspace.client.get(ROOT, query_string=query).status_code == 400


def test_endpoint_reads_db_only_and_retains_auth_guard(workspace, monkeypatch):
    from flask_jwt_extended import JWTManager
    workspace.app.config['JWT_SECRET_KEY'] = 'unit-test-only'
    JWTManager(workspace.app)
    def forbidden():
        pytest.fail('Journal query attempted receiver access')
    monkeypatch.setattr('supervision_workspace_api._read_receiver', forbidden)
    assert read(workspace)['storage'] == 'server_sqlite'
    assert workspace.client.get(ROOT).headers['Cache-Control'] == 'no-store'
    monkeypatch.setenv('PYCONLYSE_PRODUCTION', 'true')
    assert workspace.client.get(ROOT).status_code == 401
    assert workspace.client.post(ROOT, json={}).status_code == 405


def test_no_timestamp_invention_for_invalid_source_events(workspace):
    invalid = event('2026-10-26T12:00:00')  # no timezone
    workspace.store.record_journal(workspace.store.journal.observe_cooling, 'labview', safety(invalid))
    assert 'timezone' in read(workspace)['journal_error']
    assert read(workspace)['events'] == []


def test_concurrent_source_polls_deduplicate_in_one_transaction(workspace):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as workers:
        results = [workers.submit(workspace.store.journal.observe_cooling, 'labview', safety(event()))
                   for _ in range(12)]
        for result in results:
            result.result(timeout=5)
    assert len(read(workspace)['events']) == 1


def test_display_cache_writer_lock_is_bounded_and_visible_to_alarm_observation(workspace):
    with workspace.store.connect() as writer:
        writer.execute('BEGIN IMMEDIATE')
        workspace.store.record_journal(workspace.store.journal.observe_cooling, 'labview', safety(event()))
    assert 'locked' in read(workspace)['journal_error']
    workspace.store.record_journal(workspace.store.journal.observe_cooling, 'labview', safety(event()))
    assert read(workspace)['journal_error'] == ''
    assert len(read(workspace)['events']) == 1


def test_missing_bank_and_return_keep_bank_identity(workspace):
    payload = sample()
    payload['expected_banks'] = ['C1NI6071E', 'VAM-A']
    workspace.store.ingest(payload)
    missing = deepcopy(payload)
    del missing['snapshot']['publications']['VAM-A']
    workspace.store.ingest(missing)
    workspace.store.ingest(payload)
    rows = [row for row in read(workspace)['events'] if row['kind'].startswith('BANK_')]
    assert [row['kind'] for row in rows] == ['BANK_CURRENT', 'BANK_MISSING']
    assert all(row['details']['bank'] == 'VAM-A' for row in rows)


def test_selected_cooling_source_outage_does_not_fabricate_recovery(workspace):
    workspace.store.journal.cooling_unavailable('xp_runtime', 'bridge stale')
    workspace.store.journal.cooling_unavailable('xp_runtime', 'bridge stale')
    workspace.store.journal.observe_cooling('xp_runtime', safety())
    rows = read(workspace)['events']
    assert [row['kind'] for row in rows] == ['COOLING_SOURCE_RESTORED', 'COOLING_SOURCE_UNAVAILABLE']


def test_successful_same_source_write_clears_its_pending_storage_error(workspace):
    def cooling_unavailable(*args):
        raise OSError('disk locked')
    workspace.store.record_journal(cooling_unavailable, 'xp_runtime', 'bridge stale')
    assert read(workspace)['journal_error']
    workspace.store.record_journal(workspace.store.journal.observe_cooling, 'xp_runtime', safety())
    assert read(workspace)['journal_error'] == ''
