import unittest

from elyse_agent.hardware_plan import (
    analog_startup_voltage_image,
    card_initialization_plan,
    digital_startup_image,
    load_counter_timing,
    logical_ao_to_volts,
)


class HardwarePlanTests(unittest.TestCase):
    def test_all_eleven_cards_are_described_without_driver_import(self):
        plan = card_initialization_plan()
        self.assertEqual(plan["device_numbers"], tuple(range(1, 12)))
        self.assertEqual(plan["hardware_tasks_created"], 0)
        self.assertFalse(plan["hardware_writes"])
        self.assertEqual(len(plan["counter_output"]), 8)

    def test_counter_low_ticks_are_not_initial_delay(self):
        counters = load_counter_timing()
        self.assertEqual(counters[2]["low_ticks"], 43558)
        self.assertEqual(counters[2]["initial_delay_ticks"], 0)
        self.assertEqual(counters[7]["high_ticks"], 100000)
        self.assertEqual(counters[7]["trigger_edge"], "falling")
        self.assertEqual(
            [item["output"] for item in counters if item["started_on_init"]],
            [0, 1, 2, 5, 6, 7],
        )

    def test_startup_digital_image_uses_raw_llb_bits(self):
        image = digital_startup_image()
        self.assertEqual([len(image[name]) for name in sorted(image)], [40, 32, 40])
        self.assertEqual([i for i, value in enumerate(image["C3_DIO96_DO"]) if value], [1, 4])
        self.assertEqual(
            [i for i, value in enumerate(image["C4_DIO96_DO"]) if value],
            [1, 4, 6, 8, 17, 19],
        )
        self.assertEqual([i for i, value in enumerate(image["C5_DIO96_DO"]) if value], [33])

    def test_startup_analog_values_are_converted_to_volts(self):
        image = analog_startup_voltage_image()
        self.assertAlmostEqual(image["C8NI6703"][1], 2.2)
        self.assertAlmostEqual(image["C8NI6703"][2], 3.58)
        self.assertAlmostEqual(image["C8NI6703"][3], 2.1775)
        self.assertAlmostEqual(image["C8NI6703"][4], 3.8587)
        self.assertAlmostEqual(image["C8NI6703"][6], 9.0)
        self.assertAlmostEqual(image["C9NI6703"][0], 3.25)
        self.assertAlmostEqual(image["C9NI6703"][2], 4.755)

    def test_ao_bounds_are_checked_before_hardware_write(self):
        with self.assertRaises(ValueError):
            logical_ao_to_volts("C6NI6703", 0, 11.0)
        with self.assertRaises(ValueError):
            logical_ao_to_volts("C8NI6703", 4, -1.0)


if __name__ == "__main__":
    unittest.main()
