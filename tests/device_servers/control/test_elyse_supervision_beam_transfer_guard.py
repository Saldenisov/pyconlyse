"""Source-bit transfer guard checks; no PSP or NI access."""

import unittest

from DeviceServers.control.elyse_acq.legacy_supervision_setpoints import (
    beam_line_transfer_guard,
)


class BeamLineTransferGuardTests(unittest.TestCase):
    def test_only_arrow_bits_transfer_for_both_lines(self):
        for line, row_count in (("direct", 11), ("deviated", 9)):
            for changed in (0, 1, 16, 17, 2, 32, 64):
                masks = [0] * row_count
                masks[-1] = changed
                with self.subTest(line=line, changed=changed):
                    self.assertFalse(beam_line_transfer_guard(line, masks))
            for changed in (128, 256, 512, 1024, 128 | 1 | 16):
                masks = [0] * row_count
                masks[-1] = changed
                with self.subTest(line=line, changed=changed):
                    self.assertTrue(beam_line_transfer_guard(line, masks))
            self.assertTrue(
                beam_line_transfer_guard(line, [128] + [0] * (row_count - 1))
            )

    def test_malformed_rows_fail_closed(self):
        for line, masks in (
            ("unknown", [0] * 11),
            ("direct", [0] * 9),
            ("deviated", [0] * 11),
            ("direct", [0] * 10 + [2048]),
            ("direct", [0] * 10 + [-1]),
            ("direct", [0] * 10 + [True]),
        ):
            with self.subTest(line=line, masks=masks):
                with self.assertRaises(ValueError):
                    beam_line_transfer_guard(line, masks)


if __name__ == "__main__":
    unittest.main()
