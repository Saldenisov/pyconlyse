"""Pure cooling-frame fixtures preserve raw logic, snapshots and pulse gaps."""

import unittest
from itertools import product

from DeviceServers.control.elyse_acq.vi_simulation.boundary import UNSUPPLIED, UNWIRED
from DeviceServers.control.elyse_acq.vi_simulation.timeout_cooling import (
    cooling_guard,
    trip_frame,
)


class CoolingTimeoutProjectionTests(unittest.TestCase):
    def test_all_16_raw_guard_combinations(self):
        for a, b, c, d in product((False, True), repeat=4):
            c4, c3 = [False] * 64, [False] * 56
            c4[19], c4[38], c3[0], c3[6] = a, b, c, d
            self.assertEqual(
                cooling_guard(
                    enabled_arm=True, c4_snapshot=tuple(c4), c3_snapshot=tuple(c3)
                ),
                (a or b) and (not c or not d),
            )

    def test_missing_or_disabled_arm_has_no_invented_trip(self):
        self.assertIs(
            cooling_guard(enabled_arm=UNSUPPLIED, c4_snapshot=(), c3_snapshot=()),
            UNSUPPLIED,
        )
        self.assertIs(
            cooling_guard(enabled_arm=False, c4_snapshot=(), c3_snapshot=()), UNWIRED
        )

    def test_four_output_frames_preserve_every_other_bit(self):
        for index, uid, field, value in (
            (0, "10431", 1, False),
            (1, "13466", 1, True),
            (3, "22661", 4, False),
            (4, "30986", 4, True),
        ):
            before = tuple(i % 2 == 0 for i in range(40))
            frame = trip_frame(index, snapshots={uid: before})
            write = next(x for x in frame.writes if x.bank == 17)
            self.assertIs(write.data[field], value)
            self.assertEqual(
                write.data[:field] + write.data[field + 1 :],
                before[:field] + before[field + 1 :],
            )
            self.assertEqual(frame.requested_wait_ms, 150 if index in (0, 3) else None)
            if index == 0:
                self.assertTrue(
                    any(x.bank == 35 and x.data is True for x in frame.writes)
                )

    def test_seven_frames_have_ordered_wait_requests_not_physical_pulse_guarantees(
        self,
    ):
        reads = (
            {"10431": (True,) * 40},
            {"13466": (False,) * 40},
            {},
            {"22661": (True,) * 40},
            {"30986": (False,) * 40},
            {"39289": (True,) * 77, "39313": (True,) * 29},
            {"39444": (False,) * 29},
        )
        frames = tuple(trip_frame(i, snapshots=read) for i, read in enumerate(reads))
        self.assertEqual(
            tuple(f.diagram_uid for f in frames),
            ("10221", "13119", "14187", "20056", "30644", "31857", "39347"),
        )
        self.assertEqual(
            tuple(f.requested_wait_ms for f in frames),
            (150, None, 400, 150, None, None, 100),
        )

    def test_status_preserves_general_modulator_ok_and_unrelated_requests(self):
        eps = tuple(i % 2 == 0 for i in range(77))
        dps = (True,) * 29
        frame = trip_frame(5, snapshots={"39289": eps, "39313": dps})
        outputs = {x.bank: x.data for x in frame.writes}
        self.assertEqual(
            tuple(outputs[44][i] for i in (1, 2, 3, 5)), (True, False, False, True)
        )
        self.assertIs(outputs[44][8], eps[8])
        self.assertEqual(outputs[36], (True, False) + (True,) * 27)
        self.assertNotIn(30, outputs)

    def test_publication_uses_fresh_dps_not_assumed_reset_value(self):
        snapshot = (True,) * 29
        frame = trip_frame(6, snapshots={"39444": snapshot})
        self.assertEqual(frame.publication.data, snapshot)
        self.assertIs(frame.publication.error_in, UNWIRED)
        self.assertEqual(frame.publication.error_handler_node, "39603")
        self.assertEqual(frame.writes, ())

    def test_frames_require_only_their_own_full_size_snapshots(self):
        with self.assertRaises(ValueError):
            trip_frame(2, snapshots={"10431": (True,) * 40})
        with self.assertRaises(TypeError):
            trip_frame(0, snapshots={"10431": (True,) * 39})


if __name__ == "__main__":
    unittest.main()
