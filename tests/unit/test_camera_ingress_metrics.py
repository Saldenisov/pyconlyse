import unittest

from legacy.xp_acq_control.elyse_agent.camera_ingress_metrics import CameraIngressMetrics


class CameraIngressMetricsTests(unittest.TestCase):
    def test_bounded_samples_preserve_totals_and_phase_scale(self):
        metrics = CameraIngressMetrics(3)
        for index in range(10):
            metrics.connection()
            metrics.record(index * .04, .001, .002, .003, True, .010, .001)
        result = metrics.snapshot()
        self.assertEqual(result['completed'], 10)
        self.assertEqual(result['connections'], 10)
        self.assertEqual(result['retained_samples'], 3)
        self.assertAlmostEqual(result['completed_window_hz'], 25.)
        self.assertEqual(result['phases']['ingest_seconds']['p95'], .002)
        self.assertEqual(result['phases']['source_copy_seconds']['maximum'], .001)
        self.assertFalse(result['pixels_retained'])

    def test_busy_diagnostics_do_not_wait_or_change_admission(self):
        metrics = CameraIngressMetrics()
        metrics.lock.acquire()
        try:
            metrics.record(1, 0, 0, 0, True)
            metrics.connection()
            self.assertFalse(metrics.snapshot()['available'])
        finally:
            metrics.lock.release()
        self.assertEqual(metrics.completed, 0)
        self.assertEqual(metrics.skipped_busy, 2)

    def test_rejections_have_bounded_categories_and_no_negative_reply_inference(self):
        metrics = CameraIngressMetrics()
        for index in range(100):
            metrics.record(index, 0, 0, 0, False, error='future clock value %d' % index)
        result = metrics.snapshot()
        self.assertEqual(result['rejected'], 100)
        self.assertEqual(result['errors'], {'source_clock': 100})
        self.assertIsNone(result['phases']['source_age_at_receive_seconds'])


if __name__ == '__main__':
    unittest.main()
