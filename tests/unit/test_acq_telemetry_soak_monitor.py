import unittest
from tools.run_acq_telemetry_soak import SoakMonitor


class MonitorTests(unittest.TestCase):
    def test_waiting_receipts_freeze_and_read_failure_are_distinguished(self):
        now = [0.0]
        monitor = SoakMonitor(clock=lambda: now[0])
        self.assertFalse(monitor.snapshot()['current_flow_healthy'])
        self.assertIsNone(monitor.snapshot()['seconds_since_observed_new_receipt'])
        monitor.observe(dict(received_this_process=1, publications=dict(
            C1NI6071E=dict(age_seconds=0, stale=False))))
        self.assertTrue(monitor.snapshot()['current_flow_healthy'])
        now[0] = 2.5
        self.assertFalse(monitor.snapshot()['current_flow_healthy'])
        self.assertEqual(monitor.snapshot()['telemetry']['publications']['C1NI6071E']['age_seconds'], 2.5)
        monitor.error(ValueError('Tango unavailable'))
        self.assertEqual(monitor.snapshot()['tango_read_errors'], 1)
        self.assertEqual(monitor.snapshot()['last_error'], 'Tango unavailable')
        now[0] = 3
        monitor.observe(dict(received_this_process=2, publications=dict(
            C1NI6071E=dict(age_seconds=0, stale=False))))
        self.assertTrue(monitor.snapshot()['current_flow_healthy'])
        self.assertEqual(monitor.snapshot()['max_observed_silence_seconds'], 3)
        self.assertEqual(monitor.snapshot()['received_packets'], 2)


if __name__ == '__main__':
    unittest.main()
