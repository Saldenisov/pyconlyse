import unittest
from unittest.mock import Mock, patch

import numpy as np

from avantes_parallel import parallel_full_measurement, parallel_poll_and_get_data


def detector():
    spec = Mock()
    spec.poll_scan.return_value = True
    spec.get_data.return_value = (12, np.array([3.0, 8.0]))
    spec.get_saturated_pixels.return_value = [False, True]
    return spec


class ParallelReadoutTests(unittest.TestCase):
    def test_partial_start_stops_both_devices_before_retry(self):
        left, right = detector(), detector()
        right.measure.side_effect = [RuntimeError("trigger rejected"), None]
        diagnostics = {}
        with self.assertLogs("avantes_parallel", level="WARNING"):
            results = parallel_full_measurement([left, right], [object(), object()], diagnostics=diagnostics)
        self.assertEqual(results, {0: (False, None), 1: (False, None)})
        self.assertEqual(diagnostics[1], {"stage": "start", "error": "trigger rejected"})
        left.stop_measure.assert_called_once()
        right.stop_measure.assert_called_once()

        results = parallel_full_measurement([left, right], [object(), object()])
        self.assertTrue(all(success for success, _ in results.values()))
        left.stop_measure.assert_called_once()
        right.stop_measure.assert_called_once()

    def test_readout_timeout_preserves_the_successful_channel(self):
        left, right = detector(), detector()
        right.poll_scan.return_value = False
        diagnostics = {}
        with self.assertLogs("avantes_parallel", level="WARNING"):
            results = parallel_full_measurement([left, right], [None, None], timeout=0.03, diagnostics=diagnostics)
        self.assertTrue(results[0][0])
        np.testing.assert_array_equal(results[0][1], [3.0, 8.0])
        self.assertEqual(diagnostics[0]["saturated_pixels"], [1])
        self.assertEqual(results[1], (False, None))
        self.assertEqual(diagnostics[1]["error"], "readout timeout")
        left.stop_measure.assert_not_called()
        right.stop_measure.assert_called_once()

    def test_retry_does_not_delay_other_channels(self):
        left, right = detector(), detector()
        left.get_data.side_effect = [RuntimeError("ERR_INVALID_MEAS_DATA"), (12, np.ones(2))]
        now = 1.0
        peer_readout = []

        def sleep(seconds):
            nonlocal now
            now += seconds

        def read_right():
            peer_readout.append(now)
            return 8, np.zeros(2)

        right.get_data.side_effect = read_right
        with patch("avantes_parallel.time.monotonic", side_effect=lambda: now), patch(
            "avantes_parallel.time.sleep", side_effect=sleep
        ):
            results = parallel_poll_and_get_data([left, right])
        self.assertEqual(peer_readout, [1.0])
        self.assertTrue(all(success for success, _ in results.values()))

    def test_optional_metadata_error_keeps_valid_counts(self):
        spec = detector()
        spec.get_data.return_value = ("unavailable tick", np.array([1, 2]))
        spec.get_saturated_pixels.side_effect = RuntimeError("unsupported")
        diagnostics = {}
        result = parallel_full_measurement([spec], [None], diagnostics=diagnostics)
        self.assertTrue(result[0][0])
        np.testing.assert_array_equal(result[0][1], [1, 2])
        self.assertIn("device_tick_error", diagnostics[0])
        self.assertEqual(diagnostics[0]["saturation_error"], "unsupported")
        spec.stop_measure.assert_not_called()

    def test_mismatched_configuration_is_rejected_before_hardware_calls(self):
        left, right = detector(), detector()
        with self.assertRaisesRegex(ValueError, "Each spectrometer requires"):
            parallel_full_measurement([left, right], [None])
        left.prepare_measure.assert_not_called()
        right.prepare_measure.assert_not_called()
