"""Supplied phase flags are distinct from the intermediate VISA error status."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import ErrorCluster
from DeviceServers.control.elyse_acq.vi_simulation.tpg300_retry import retry_postprocess


class RetryProjectionTests(unittest.TestCase):
    def result(self, **overrides):
        values = dict(
            iteration=0,
            retry=3,
            flag_a=True,
            flag_b=False,
            sequence_error=ErrorCluster(True, -7, "fixture"),
        )
        values.update(overrides)
        return retry_postprocess(**values)

    def test_all_flag_combinations_replace_status_not_or_original_status(self):
        for a in (False, True):
            for b in (False, True):
                result = self.result(flag_a=a, flag_b=b)
                self.assertEqual(
                    result.intermediate_error, ErrorCluster(a or b, -7, "fixture")
                )
                self.assertEqual(result.keep_running, a or b)

    def test_default_all_failures_permit_four_attempts_not_three(self):
        self.assertEqual(
            [self.result(iteration=i).keep_running for i in range(4)],
            [True, True, True, False],
        )

    def test_zero_negative_retry_and_success_exit_after_first_sequence(self):
        for retry in (-3, 0):
            self.assertFalse(self.result(retry=retry).keep_running)
        self.assertFalse(self.result(flag_a=False, flag_b=False).keep_running)

    def test_python_only_representation_guards(self):
        with self.assertRaises(ValueError):
            self.result(iteration=-1)
        with self.assertRaises(TypeError):
            self.result(flag_a=1)


if __name__ == "__main__":
    unittest.main()
