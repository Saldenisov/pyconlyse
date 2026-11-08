"""Only Consigne changes; command intent is not readback or permission."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.timeout_setpoint_display import (
    deviated_display,
    direct_display,
)


class SetpointDisplayProjectionTests(unittest.TestCase):
    def cells(self, size):
        return tuple(
            (False, True, False, True, False, -1.0, float(i), True, False, True, False)
            for i in range(size)
        )

    def test_all_direct_copies_and_other_fields_preserved(self):
        before = self.cells(11)
        after = direct_display(
            before,
            bank9=tuple(float(900 + i) for i in range(10)),
            bank10=tuple(float(1000 + i) for i in range(10)),
            bank11=tuple(float(1100 + i) for i in range(10)),
        )
        self.assertEqual(
            tuple(cell[5] for cell in after),
            (
                1008.0,
                1005.0,
                1105.0,
                900.0,
                901.0,
                902.0,
                903.0,
                1000.0,
                1001.0,
                904.0,
                905.0,
            ),
        )
        for old, new in zip(before, after):
            self.assertEqual(old[:5] + old[6:], new[:5] + new[6:])

    def test_all_deviated_copies_and_c6_index8_not_inferred_reserve(self):
        before = self.cells(9)
        after = deviated_display(
            before,
            bank9=tuple(float(900 + i) for i in range(10)),
            bank10=tuple(float(1000 + i) for i in range(10)),
        )
        self.assertEqual(
            tuple(cell[5] for cell in after),
            (1006.0, 1007.0, 1003.0, 1004.0, 906.0, 907.0, 1009.0, 908.0, 909.0),
        )
        for old, new in zip(before, after):
            self.assertEqual(old[:5] + old[6:], new[:5] + new[6:])

    def test_short_command_bank_not_silently_padded(self):
        with self.assertRaises(TypeError):
            deviated_display(self.cells(9), bank9=(1.0,), bank10=(0.0,) * 10)


if __name__ == "__main__":
    unittest.main()
