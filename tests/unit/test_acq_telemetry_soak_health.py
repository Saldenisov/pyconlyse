import json
from pathlib import Path
import tempfile
import unittest

from tools.watch_acq_telemetry_soak import HealthSummary


def status(count=1, session='receiver-1', healthy=True, silence=1.01, errors=0):
    return dict(test='synthetic_acq_transport_soak', hardware_writes=False,
                sqlite_used=False, uptime_seconds=20, received_packets=count,
                first_receipt_utc='2026-10-12T17:57:17Z',
                seconds_since_observed_new_receipt=0.1,
                max_observed_silence_seconds=silence,
                current_flow_healthy=healthy, tango_read_errors=errors,
                last_error='', telemetry=dict(receiver_session=session,
                    publications=dict(C1NI6071E=dict(data=[12345, 1.5, -0.2]))))


class HealthTests(unittest.TestCase):
    def test_no_packet_values_persisted_and_atomic_latest_replacement(self):
        summary = HealthSummary('start', 'end')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'health.json'
            summary.observe(status(), 'first')
            summary.save(output)
            summary.observe(status(count=2), 'second')
            summary.save(output)
            result = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(result['latest']['received_packets'], 2)
            self.assertEqual(result['endpoint_read_samples'], 2)
            self.assertNotIn('12345', output.read_text(encoding='utf-8'))
            self.assertNotIn('publications', output.read_text(encoding='utf-8'))
            self.assertFalse(result['telemetry_persisted'])
            self.assertEqual(list(Path(folder).iterdir()), [output])

    def test_outage_recovery_and_receiver_restart_evidence_retained(self):
        summary = HealthSummary('start', 'end')
        summary.observe(status(count=10), 'one')
        summary.error(OSError('endpoint unavailable'), 'two')
        self.assertEqual(summary.result['last_error'], 'endpoint unavailable')
        summary.observe(status(count=11, healthy=False, silence=6, errors=1), 'three')
        summary.observe(status(count=1, session='receiver-2'), 'four')
        self.assertEqual(summary.result['endpoint_read_errors'], 1)
        self.assertEqual(summary.result['unhealthy_samples'], 1)
        self.assertEqual(summary.result['max_receiver_silence_seconds'], 6)
        self.assertEqual(summary.result['max_tango_read_errors'], 1)
        self.assertEqual(summary.result['receiver_restarts_or_counter_regressions'], 1)
        self.assertEqual(summary.result['last_error'], '')

    def test_non_synthetic_endpoint_rejected(self):
        summary = HealthSummary('start', 'end')
        payload = status()
        payload['hardware_writes'] = True
        with self.assertRaises(ValueError):
            summary.observe(payload, 'now')
        self.assertIsNone(summary.result['latest'])


if __name__ == '__main__':
    unittest.main()
