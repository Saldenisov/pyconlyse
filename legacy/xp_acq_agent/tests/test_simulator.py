import unittest

from elyse_agent.errors import CommandError, HardwareWriteBlocked
from elyse_agent.simulator import SimulatedBackend


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.backend = SimulatedBackend()

    def test_snapshot_requires_initialization(self):
        with self.assertRaises(CommandError):
            self.backend.get_snapshot()

    def test_initialize_and_snapshot_have_recovered_channel_counts(self):
        result = self.backend.initialize()
        self.assertEqual(result["hardware_tasks_created"], 0)
        snapshot = self.backend.get_snapshot()
        self.assertEqual(len(snapshot["analog_inputs"]["C1_NI6071E_AI"]), 64)
        self.assertEqual(len(snapshot["analog_inputs"]["C2_NI6071E_AI"]), 64)
        self.assertEqual(len(snapshot["analog_inputs"]["C11_NI6220_AI"]), 16)
        self.assertEqual(len(snapshot["digital_inputs"]["C3_DIO96_DI"]), 56)
        self.assertEqual(len(snapshot["digital_inputs"]["C4_DIO96_DI"]), 64)
        self.assertEqual(len(snapshot["digital_inputs"]["C5_DIO96_DI"]), 56)
        self.assertEqual(len(snapshot["digital_outputs"]["C3_DIO96_DO"]), 40)
        self.assertEqual(len(snapshot["digital_outputs"]["C4_DIO96_DO"]), 32)
        self.assertEqual(len(snapshot["digital_outputs"]["C5_DIO96_DO"]), 40)
        self.assertEqual(len(snapshot["analog_outputs_volts"]["C6_NI6703_AO"]), 10)
        self.assertEqual(len(snapshot["counter_outputs"]), 8)
        self.assertIs(snapshot["hardware_writes"], False)

    def test_simulated_outputs_are_stateful_without_hardware_writes(self):
        self.backend.initialize()
        digital = self.backend.set_simulated_digital_output("C5_DIO96_DO", 7, True)
        analog = self.backend.set_simulated_analog_output("C6_NI6703_AO", 0, 1.25)
        counter = self.backend.set_simulated_counter_output(2, 0.01, 0.002, True)
        snapshot = self.backend.get_snapshot()
        self.assertTrue(digital["simulated"])
        self.assertFalse(digital["hardware_writes"])
        self.assertEqual(analog["value"], 1.25)
        self.assertTrue(counter["value"]["enabled"])
        self.assertTrue(snapshot["digital_outputs"]["C5_DIO96_DO"][7])
        self.assertEqual(snapshot["analog_outputs_volts"]["C6_NI6703_AO"][0], 1.25)
        self.assertTrue(snapshot["counter_outputs"][2]["enabled"])
        self.assertFalse(snapshot["hardware_writes"])

    def test_simulated_output_validation_and_reset(self):
        self.backend.initialize()
        with self.assertRaises(CommandError):
            self.backend.set_simulated_digital_output("C5_DIO96_DO", 40, True)
        with self.assertRaises(CommandError):
            self.backend.set_simulated_digital_output("C5_DIO96_DO", 0, 1)
        with self.assertRaises(CommandError):
            self.backend.set_simulated_analog_output("C6_NI6703_AO", 0, 10.1)
        self.backend.set_simulated_digital_output("C3_DIO96_DO", 0, True)
        self.backend.reset_simulated_outputs()
        self.assertFalse(self.backend.get_snapshot()["digital_outputs"]["C3_DIO96_DO"][0])

    def test_fault_scenario_is_visible_in_telemetry(self):
        self.backend.initialize()
        self.backend.set_scenario("fault")
        snapshot = self.backend.advance(1.0)
        self.assertEqual(snapshot["acquisition_state"], "FAULT")
        self.assertTrue(snapshot["alarms"])
        self.assertGreater(snapshot["environment"]["TPG300_1_mbar"], 1e-5)

    def test_psp_catalog_matches_confirmed_card_fields(self):
        catalog = self.backend.get_psp_catalog()
        names = [channel["raw_name"] for channel in catalog["channels"]]
        self.assertEqual(catalog["format"], "psp_supervision_scalar_v1")
        self.assertEqual(catalog["channel_count"], 472)
        self.assertIn("00 ACH00 b03 Mes température Canon", names)
        self.assertIn("07 CPB7 b67 M/A Eclairage Ecran 1", names)
        self.assertFalse(any("C11 Délais" in name for name in names))

    def test_psp_snapshot_uses_real_scalar_names_and_wire_shape(self):
        self.backend.initialize()
        self.backend.set_simulated_digital_output("C5_DIO96_DO", 7, True)
        self.backend.set_simulated_analog_output("C6_NI6703_AO", 0, 1.25)
        self.backend.set_simulated_counter_output(0, 0.01, 0.002, True)
        snapshot = self.backend.get_psp_snapshot()
        self.assertEqual(snapshot["channel_count"], 472)
        self.assertEqual(snapshot["messages_in_batch"], 472)
        self.assertEqual(snapshot["messages_received"], 472)
        self.assertEqual(snapshot["data"]["07 CPB7 b67 M/A Eclairage Ecran 1"], 1.0)
        self.assertEqual(snapshot["data"]["00 OUT00 b01 Cmd Guidage H1"], 1.25)
        self.assertEqual(snapshot["data"]["00 OUT00 b05 C10 Délais"], 10000.0)
        self.assertEqual(snapshot["data"]["01 OUT00 b05 C10 Largeur"], 2000.0)
        self.assertTrue(
            any(
                payload.startswith("07 CPB7 b67 M/A Eclairage Ecran 1:1:")
                for payload in snapshot["payloads"]
            )
        )
        self.assertFalse(snapshot["hardware_writes"])

    def test_unknown_scenario_and_hardware_write_are_blocked(self):
        with self.assertRaises(CommandError):
            self.backend.set_scenario("unknown")
        with self.assertRaises(HardwareWriteBlocked):
            self.backend.write("anything")


if __name__ == "__main__":
    unittest.main()
