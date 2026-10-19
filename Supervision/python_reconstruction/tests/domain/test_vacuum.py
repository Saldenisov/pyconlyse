import unittest

from supervision_reconstruction.domain.vacuum import (
    VacuumPairedState,
    evaluate_vacuum_status,
)


class VacuumTests(unittest.TestCase):
    def test_paired_vacuum_truth_table_matches_evidenced_and_not_running_logic(self) -> None:
        states = {
            "both_false": VacuumPairedState(running=False, fault=False),
            "fault_only": VacuumPairedState(running=False, fault=True),
            "running_only": VacuumPairedState(running=True, fault=False),
            "both_true": VacuumPairedState(running=True, fault=True),
            "another_false": VacuumPairedState(running=False, fault=False),
            "another_true": VacuumPairedState(running=True, fault=True),
        }

        result = evaluate_vacuum_status(True, states)

        self.assertTrue(result.chamber_preparation)
        self.assertEqual(
            result.paired_channels,
            {
                "both_false": False,
                "fault_only": True,
                "running_only": False,
                "both_true": False,
                "another_false": False,
                "another_true": False,
            },
        )

    def test_vacuum_result_does_not_alias_caller_mapping(self) -> None:
        states = {
            f"channel_{index}": VacuumPairedState(running=False, fault=index == 0)
            for index in range(6)
        }
        result = evaluate_vacuum_status(False, states)
        states["channel_0"] = VacuumPairedState(running=True, fault=False)

        self.assertTrue(result.paired_channels["channel_0"])

    def test_vacuum_requires_exactly_six_non_preparation_channels(self) -> None:
        for count in (5, 7):
            states = {
                f"channel_{index}": VacuumPairedState(running=False, fault=False)
                for index in range(count)
            }
            with self.assertRaisesRegex(ValueError, "exactly the six"):
                evaluate_vacuum_status(False, states)
