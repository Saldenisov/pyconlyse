import itertools
import unittest

from DeviceServers.control.elyse_acq.interlocks import cooling_flow_trip


class CoolingFlowGuardTests(unittest.TestCase):
    def test_all_16_raw_boolean_combinations(self):
        for flow_gun, flow_section, pump_gun, pump_section in itertools.product((False, True), repeat=4):
            c4 = [False] * 64
            c3 = [False] * 56
            c4[19], c4[38] = flow_gun, flow_section
            c3[0], c3[6] = pump_gun, pump_section
            expected = (flow_gun or flow_section) and (not pump_gun or not pump_section)
            with self.subTest(bits=(flow_gun, flow_section, pump_gun, pump_section)):
                self.assertEqual(cooling_flow_trip(c4, c3), expected)

    def test_malformed_banks_fail_instead_of_silently_defaulting(self):
        for c4, c3 in (
            ([False] * 63, [False] * 56),
            ([False] * 65, [False] * 56),
            ([False] * 63 + [1], [False] * 56),
            ([False] * 64, [False] * 55),
            ([False] * 64, [False] * 57),
            ([False] * 64, [False] * 55 + [1]),
        ):
            with self.subTest(c4=len(c4), c3=len(c3)):
                with self.assertRaises(ValueError):
                    cooling_flow_trip(c4, c3)


if __name__ == "__main__":
    unittest.main()
