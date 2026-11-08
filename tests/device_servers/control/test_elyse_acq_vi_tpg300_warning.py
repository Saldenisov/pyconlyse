"""Warning-code gate is independent of status and clears code/source too."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    ErrorCluster,
)
from DeviceServers.control.elyse_acq.vi_simulation.tpg300_retry import retry_postprocess
from DeviceServers.control.elyse_acq.vi_simulation.tpg300_warning import (
    SUPPRESSED_CODE,
    suppress_warning,
)


class WarningProjectionTests(unittest.TestCase):
    def test_matching_code_clears_whole_cluster_for_both_statuses(self):
        for status in (False, True):
            self.assertEqual(
                suppress_warning(ErrorCluster(status, SUPPRESSED_CODE, "fixture")),
                NO_ERROR,
            )

    def test_other_codes_preserve_whole_cluster(self):
        for code in (0, -1, SUPPRESSED_CODE - 1, SUPPRESSED_CODE + 1):
            for status in (False, True):
                cluster = ErrorCluster(status, code, "fixture")
                self.assertIs(suppress_warning(cluster), cluster)

    def test_retry_decision_precedes_warning_clear(self):
        intermediate = retry_postprocess(
            iteration=0,
            retry=3,
            flag_a=True,
            flag_b=False,
            sequence_error=ErrorCluster(False, SUPPRESSED_CODE, "fixture"),
        )
        self.assertTrue(intermediate.keep_running)
        self.assertEqual(suppress_warning(intermediate.intermediate_error), NO_ERROR)

    def test_python_snapshot_type_guard(self):
        with self.assertRaises(TypeError):
            suppress_warning(None)


if __name__ == "__main__":
    unittest.main()
