from __future__ import division

import math
import unittest

from elyse_agent.transforms import (
    attenuator_voltage,
    channel_means,
    dephaser_voltage,
    linear_calibration,
    microseconds_to_20mhz_ticks,
)


class TransformTests(unittest.TestCase):
    def test_channel_means_validate_shape(self):
        self.assertEqual(channel_means([[1, 3], [2, 4]], 2, 2), [2.0, 3.0])
        with self.assertRaises(ValueError):
            channel_means([[1]], 2, 1)

    def test_linear_calibration(self):
        self.assertEqual(linear_calibration(2.0, 3.0, -1.0), 5.0)

    def test_recovered_ao_formulae_return_finite_values(self):
        self.assertTrue(math.isfinite(dephaser_voltage(0.0)))
        self.assertTrue(math.isfinite(attenuator_voltage(20.0)))

    def test_microseconds_to_ticks(self):
        self.assertEqual(microseconds_to_20mhz_ticks(2.8), 56)
        with self.assertRaises(ValueError):
            microseconds_to_20mhz_ticks(-1)


if __name__ == "__main__":
    unittest.main()
