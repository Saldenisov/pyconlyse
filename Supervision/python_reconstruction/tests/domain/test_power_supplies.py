import unittest

from supervision_reconstruction.domain.power_supplies import (
    H5CommandSource,
    evaluate_h5_fault,
    evaluate_power_supply_fault,
)


class PowerSupplyTests(unittest.TestCase):
    def test_confirmed_fault_topology_matches_all_boolean_combinations(self) -> None:
        expected = {
            (False, False, False): False,
            (False, False, True): False,
            (False, True, False): True,
            (False, True, True): True,
            (True, False, False): True,
            (True, False, True): True,
            (True, True, False): False,
            (True, True, True): True,
        }
        for inputs, fault_active in expected.items():
            result = evaluate_power_supply_fault(*inputs)
            self.assertEqual(result.fault_active, fault_active, inputs)

    def test_h5_uses_evidenced_h4_command_only_when_explicitly_selected(self) -> None:
        result = evaluate_h5_fault(
            h4_command=True,
            h5_running=False,
            h5_fault_feedback=False,
            command_source=H5CommandSource.LEGACY_H4,
        )

        self.assertTrue(result.command_used)
        self.assertTrue(result.fault_active)

    def test_h5_intended_mode_is_explicit_and_requires_a_separate_h5_command(self) -> None:
        result = evaluate_h5_fault(
            h4_command=True,
            h5_command=False,
            h5_running=False,
            h5_fault_feedback=False,
            command_source=H5CommandSource.INTENDED_H5,
        )
        self.assertFalse(result.command_used)
        self.assertFalse(result.fault_active)

        with self.assertRaisesRegex(ValueError, "requires an explicitly supplied"):
            evaluate_h5_fault(
                h4_command=True,
                h5_running=False,
                h5_fault_feedback=False,
                command_source=H5CommandSource.INTENDED_H5,
            )

    def test_legacy_h5_mode_rejects_an_extraneous_h5_command(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not accept"):
            evaluate_h5_fault(
                h4_command=True,
                h5_command=False,
                h5_running=False,
                h5_fault_feedback=False,
                command_source=H5CommandSource.LEGACY_H4,
            )
