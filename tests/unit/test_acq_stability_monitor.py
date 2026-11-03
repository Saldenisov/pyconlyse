"""Monitor qualification must fail visibly without changing live services."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from tools.monitor_acq_stability import (BANKS, Collector, RunSummary, atomic_json,
    compact_banks, sample_issues, xp_metadata)


def healthy(sequence=1, monotonic=100):
    banks = {name: dict(sequence=sequence, session_id='source-a', age_seconds=.3,
                        stale=False, error_status=False, error_code=0) for name in BANKS}
    return dict(utc='2026-11-03T10:00:00+00:00', monotonic=monotonic, read_seconds=.2,
        errors={}, tango=dict(banks=copy.deepcopy(banks)),
        web=dict(banks=copy.deepcopy(banks), quality='FRESH'),
        archive=dict(state='RUNNING', enabled=True, last_error='',
                     committed_this_process=sequence, pending=3),
        xp=dict(session_id='xp-a', delivery=dict(connected=True, worker_alive=True,
            connections_opened=1, disconnects=0, failed_attempts=0,
            everest_acknowledged=sequence, last_ack_age_seconds=.2,
            last_error='', publisher_error='', vi_ingress_error='')),
        receiver_processes=[dict(pid=20, created_epoch=1234, rss_bytes=1000,
            private_bytes=2000, handles=90, threads=8, cpu_seconds=5)])


class StabilityIssues(unittest.TestCase):
    def test_healthy_advancing_samples(self):
        self.assertEqual(sample_issues(healthy()), [])
        self.assertEqual(sample_issues(healthy(2, 110), healthy()), [])

    def test_nonzero_historical_reconnect_count_is_baseline(self):
        before, after = healthy(), healthy(2, 110)
        for row in (before, after):
            row['xp']['delivery'].update(connections_opened=8, disconnects=7, failed_attempts=12)
        self.assertEqual(sample_issues(after, before), [])
        after['xp']['delivery']['disconnects'] += 1
        self.assertIn('xp:increased:disconnects', sample_issues(after, before))

    def test_missing_stale_and_error_banks_visible(self):
        row = healthy()
        row['tango']['banks'].pop(BANKS[0])
        row['web']['banks'][BANKS[1]]['stale'] = True
        row['web']['banks'][BANKS[2]]['error_status'] = True
        issues = sample_issues(row)
        self.assertIn('tango:bank_set_incomplete', issues)
        self.assertIn('web:stale:' + BANKS[1], issues)
        self.assertIn('web:bank_error:' + BANKS[2], issues)

    def test_fresh_labels_do_not_hide_frozen_sequences_and_archive(self):
        row = healthy(1, 110)
        issues = sample_issues(row, healthy())
        self.assertIn('tango:not_advancing:' + BANKS[0], issues)
        self.assertIn('web:not_advancing:' + BANKS[0], issues)
        self.assertIn('archive:commits_not_advancing', issues)
        self.assertIn('xp:ack_not_advancing', issues)

    def test_restarts_are_not_mistaken_for_advancement(self):
        row = healthy(2, 110)
        row['xp']['session_id'] = 'xp-b'
        row['receiver_processes'][0]['created_epoch'] += 1  # PID reuse
        row['tango']['banks'][BANKS[0]]['session_id'] = 'source-b'
        issues = sample_issues(row, healthy())
        self.assertIn('xp:server_restarted', issues)
        self.assertIn('receiver:process_restarted', issues)
        self.assertIn('tango:source_session_changed:' + BANKS[0], issues)

    def test_source_failures_and_monitor_gaps_are_not_silent(self):
        row = healthy(2, 131)
        row.pop('tango')
        row['errors']['tango'] = 'DevFailed'
        row['read_seconds'] = 11
        issues = sample_issues(row, healthy())
        self.assertIn('read_failed:tango', issues)
        self.assertIn('monitor:sampling_gap', issues)
        self.assertIn('monitor:poll_overrun', issues)

    def test_null_counters_and_invalid_ages_do_not_crash_observer(self):
        row = healthy(2, 110)
        row['xp']['delivery']['disconnects'] = None
        row['xp']['delivery']['last_ack_age_seconds'] = float('nan')
        row['tango']['banks'][BANKS[0]]['age_seconds'] = -1
        self.assertIn('xp:invalid_counter:disconnects', sample_issues(row, healthy()))
        self.assertIn('xp:ack_old', sample_issues(row, healthy()))
        self.assertIn('tango:invalid_age:' + BANKS[0], sample_issues(row, healthy()))


class StabilityReporting(unittest.TestCase):
    def summary(self, duration=100):
        return RunSummary(datetime(2026, 11, 3, 10, tzinfo=timezone.utc), duration, 10)

    def test_smoke_or_early_stop_cannot_qualify_24_hours(self):
        summary = self.summary(86400)
        summary.add(healthy())
        summary.add(healthy(2, 110))
        self.assertEqual(summary.snapshot('SMOKE_CHECK_ONLY')['verdict'], 'INCOMPLETE')
        self.assertNotEqual(summary.snapshot('COMPLETED')['verdict'], 'NO_SAMPLED_FAILURES')
        self.assertFalse(summary.snapshot()['automatic_restart'])

    def test_completed_clean_window_is_bounded_sampled_claim(self):
        summary = self.summary(10)
        summary.add(healthy())
        summary.add(healthy(2, 110))
        report = summary.snapshot('COMPLETED')
        self.assertEqual(report['verdict'], 'NO_SAMPLED_FAILURES')
        self.assertEqual(report['healthy_samples'], 2)
        self.assertEqual(report['hourly']['0']['rss_max_bytes'], 1000)
        self.assertEqual(report['restart_recommendation'], 'UNDETERMINED_PENDING_DURATION_AND_INCIDENT_REVIEW')

    def test_incident_recovery_keeps_failure_and_records_transition(self):
        summary = self.summary(30)
        self.assertEqual(summary.add(healthy()), [])
        bad = healthy(2, 110)
        bad['xp']['delivery']['connected'] = False
        entry = summary.add(bad)
        self.assertIn('xp:connected_false', entry[0]['entered'])
        recovery = summary.add(healthy(3, 120))
        self.assertIn('xp:connected_false', recovery[0]['cleared'])
        summary.add(healthy(4, 130))
        report = summary.snapshot('COMPLETED')
        self.assertEqual(report['verdict'], 'INCIDENTS_REQUIRE_REVIEW')
        self.assertEqual(report['issue_sample_counts']['xp:connected_false'], 1)

    def test_logs_exclude_pixels_keys_and_unknown_runtime_fields(self):
        banks = compact_banks({'x': dict(data=[1, 2], secret='not-for-logs', lv_type={},
                                         error=dict(status=False, code=0))})
        xp = xp_metadata(dict(secret='not-for-logs', latest={'pixels': 'no'},
                              telemetry_delivery=dict(key='not-for-logs', connected=True)))
        encoded = json.dumps(dict(banks=banks, xp=xp))
        self.assertNotIn('not-for-logs', encoded)
        self.assertNotIn('pixels', encoded)
        self.assertNotIn('lv_type', encoded)

    def test_atomic_report_replaces_complete_document(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'summary.json'
            atomic_json(path, dict(samples=1))
            atomic_json(path, dict(samples=2))
            self.assertEqual(json.loads(path.read_text())['samples'], 2)
            self.assertFalse(path.with_suffix('.tmp').exists())

    def test_one_failed_source_does_not_suppress_other_sources(self):
        collector = Collector.__new__(Collector)
        collector.device = Mock(side_effect=RuntimeError('receiver offline'))
        collector.http = Mock(side_effect=[dict(telemetry_delivery={}),
            dict(quality='FRESH', snapshot=dict(publications={}))])
        collector.processes = Mock(return_value=[])
        row = collector.sample()
        self.assertEqual(row['errors'], {'tango': 'RuntimeError'})
        self.assertIn('xp', row)
        self.assertIn('web', row)


if __name__ == '__main__':
    unittest.main()
