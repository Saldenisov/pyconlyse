"""Pure Page Fluides one-button temperature adjustment checks."""

import math
import unittest

from DeviceServers.control.elyse_acq.legacy_supervision_setpoints import (
    adjust_fluides_temperature_setpoint,
)


class FluidesTemperatureSetpointTests(unittest.TestCase):
    def test_four_one_hot_actions_select_c8_channel_and_sign(self):
        for action, channel, result in (
            (1, 1, 19.9),
            (2, 1, 20.1),
            (4, 2, 19.9),
            (8, 2, 20.1),
        ):
            with self.subTest(action=action):
                got_channel, got_result = adjust_fluides_temperature_setpoint(
                    20.0, action
                )
                self.assertEqual(got_channel, channel)
                self.assertAlmostEqual(got_result, result)

    def test_no_unobserved_clamp_is_introduced(self):
        self.assertAlmostEqual(
            adjust_fluides_temperature_setpoint(0.0, 1)[1], -0.1
        )

    def test_unlisted_masks_and_nonfinite_values_fail_closed(self):
        for action in (0, 3, 5, 6, 7, 9, True, 1.0, "1"):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    adjust_fluides_temperature_setpoint(20.0, action)
        for current in (math.nan, math.inf, -math.inf, True, "bad"):
            with self.subTest(current=current):
                with self.assertRaises(ValueError):
                    adjust_fluides_temperature_setpoint(current, 1)


if __name__ == "__main__":
    unittest.main()
