"""Non-actuating NI6703 request projection and supplied-error golden traces."""

import csv
import unittest
from math import acos
from pathlib import Path

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    CallKey,
    ErrorCluster,
    LogicalAoBanks,
    ScriptedBoundary,
    TaskReference,
    project_requested_voltages,
    record_ni6703_writes,
)
from DeviceServers.control.elyse_acq.vi_simulation.write_ni6703 import (
    SOURCE,
    WRITE_UIDS,
)

REPOSITORY = Path(__file__).resolve().parents[3]
TASKS = tuple(TaskReference(f"supplied-C{card}") for card in range(6, 10))
ZERO = LogicalAoBanks(tuple((0.0,) * 10 for _ in range(4)))
FAULT = ErrorCluster(True, -321, "supplied write fault")
WARNING = ErrorCluster(False, 123, "supplied write warning")


class Ni6703WriterTests(unittest.TestCase):
    def test_zero_logical_is_not_zero_requested_voltage(self):
        result = project_requested_voltages(ZERO)
        self.assertEqual(result[0], (0.0,) * 10)
        self.assertEqual(result[1], (0.0,) * 10)
        self.assertEqual(
            result[2], (0.0, -2.0, -2.0, 2.1775, 3.8587, 0.0, 0.0, 0.0, 0.0, 0.0)
        )
        self.assertEqual(result[3], (0.0,) * 10)

    def test_all_forty_startup_values_match_retained_prediction(self):
        with (REPOSITORY / "docs/ELYSE_ACQ_STARTUP_REQUESTED_AO_2026-09-29.csv").open(
            encoding="utf-8-sig", newline=""
        ) as stream:
            rows = list(csv.DictReader(stream))
        logical, expected = (
            [[0.0] * 10 for _ in range(4)],
            [[0.0] * 10 for _ in range(4)],
        )
        self.assertEqual(len(rows), 40)
        for row in rows:
            card = int(row["bank"][1]) - 6
            index = int(row["field_idx"])
            logical[card][index] = float(row["logical_value"])
            expected[card][index] = float(row["requested_volts"])
        result = project_requested_voltages(
            LogicalAoBanks(tuple(tuple(bank) for bank in logical))
        )
        for card in range(4):
            for channel in range(10):
                with self.subTest(card=card + 6, channel=channel):
                    self.assertAlmostEqual(
                        result[card][channel], expected[card][channel], places=9
                    )

    def test_nonlinear_formulas_receive_correct_inputs(self):
        banks = [list(b) for b in ZERO.values]
        banks[2][3:5] = [123.0, 20.0]
        result = project_requested_voltages(
            LogicalAoBanks(tuple(tuple(b) for b in banks))
        )
        x = 123.0
        expected_phase = 8e-9 * x**4 - 7e-7 * x**3 - 3e-5 * x**2 - 0.0181 * x + 2.1775
        angle = 57.3 * acos(0.1)
        expected_attenuation = (
            -4e-6 * angle**3 + 0.0006 * angle**2 - 0.0624 * angle + 3.8587
        )
        self.assertAlmostEqual(result[2][3], expected_phase)
        self.assertAlmostEqual(result[2][4], expected_attenuation)

    def test_exact_saved_truncated_slopes_are_not_replaced_by_fractions(self):
        banks = [list(b) for b in ZERO.values]
        banks[1][5] = 240.0
        banks[2][5], banks[2][7], banks[2][8] = 360.0, 90.0, 90.0
        result = project_requested_voltages(
            LogicalAoBanks(tuple(tuple(b) for b in banks))
        )
        self.assertEqual(result[1][5], 240 * 0.0416666)
        self.assertNotEqual(result[1][5], 10.0)
        self.assertEqual(result[2][5], 360 * 0.0277777777)
        self.assertNotEqual(result[2][5], 10.0)
        self.assertEqual(result[2][7:9], (90 * 0.1111111111,) * 2)

    def test_no_voltage_clamp_or_ht_permission_is_invented(self):
        banks = [list(b) for b in ZERO.values]
        banks[0][0], banks[3][0] = 40.0, 12.7
        result = project_requested_voltages(
            LogicalAoBanks(tuple(tuple(b) for b in banks))
        )
        self.assertEqual(result[0][0], 40.0)
        self.assertEqual(result[3][0], 6.35)  # Request math, not permission/readback.

    def test_four_call_order_task_selection_and_arguments(self):
        boundary = ScriptedBoundary()
        result = record_ni6703_writes(boundary, ZERO, tasks=TASKS, error_in=NO_ERROR)
        self.assertEqual([c.key.node_uid for c in result.calls], list(WRITE_UIDS))
        for index, call in enumerate(result.calls):
            self.assertEqual(call.diagram_uid, "3")
            self.assertEqual(call.task_in, TASKS[index])
            self.assertEqual(call.error_in, NO_ERROR)
            self.assertEqual(
                call.args,
                {
                    "card": index + 6,
                    "data": result.requested_voltages[index],
                    "auto_start": True,
                    "timeout_s": 20.0,
                },
            )
        self.assertEqual(result.error_out, NO_ERROR)

    def test_every_returned_fault_propagates_without_removing_call_sites(self):
        for index, uid in enumerate(WRITE_UIDS):
            with self.subTest(uid=uid):
                boundary = ScriptedBoundary(errors={CallKey(SOURCE.name, uid): FAULT})
                result = record_ni6703_writes(
                    boundary, ZERO, tasks=TASKS, error_in=NO_ERROR
                )
                boundary.assert_all_fixtures_used()
                self.assertEqual(len(result.calls), 4)
                self.assertEqual(result.error_out, FAULT)
                for previous in result.calls[: index + 1]:
                    self.assertEqual(previous.error_in, NO_ERROR)
                for downstream in result.calls[index + 1 :]:
                    self.assertEqual(downstream.error_in, FAULT)

    def test_incoming_fault_and_warning_are_preserved_by_pass_through_fixture(self):
        for error in (FAULT, WARNING):
            result = record_ni6703_writes(
                ScriptedBoundary(), ZERO, tasks=TASKS, error_in=error
            )
            self.assertEqual([c.error_in for c in result.calls], [error] * 4)
            self.assertEqual(result.error_out, error)

    def test_later_supplied_return_can_clear_error_no_latch_is_added(self):
        result = record_ni6703_writes(
            ScriptedBoundary(
                errors={
                    CallKey(SOURCE.name, WRITE_UIDS[0]): FAULT,
                    CallKey(SOURCE.name, WRITE_UIDS[1]): NO_ERROR,
                }
            ),
            ZERO,
            tasks=TASKS,
            error_in=NO_ERROR,
        )
        self.assertEqual(
            [c.error_in for c in result.calls], [NO_ERROR, FAULT, NO_ERROR, NO_ERROR]
        )
        self.assertEqual(result.error_out, NO_ERROR)

    def test_returned_task_does_not_replace_other_input_task_or_escape_helper(self):
        boundary = ScriptedBoundary(
            tasks={
                CallKey(SOURCE.name, uid): TaskReference(f"unused-return-{uid}")
                for uid in WRITE_UIDS
            }
        )
        result = record_ni6703_writes(boundary, ZERO, tasks=TASKS, error_in=NO_ERROR)
        boundary.assert_all_fixtures_used()
        self.assertEqual(tuple(c.task_in for c in result.calls), TASKS)
        self.assertFalse(hasattr(result, "tasks"))

    def test_representation_guards_run_before_any_recorded_write(self):
        boundary = ScriptedBoundary()
        banks = [list(b) for b in ZERO.values]
        banks[2][4] = -1.0
        logical = LogicalAoBanks(tuple(tuple(b) for b in banks))
        with self.assertRaisesRegex(ValueError, "Python-only guard"):
            record_ni6703_writes(boundary, logical, tasks=TASKS, error_in=NO_ERROR)
        self.assertEqual(boundary.calls, ())

    def test_wrong_shape_and_nonfinite_input_are_explicit_python_guards(self):
        for banks in (
            [ZERO.values],
            ((0.0,) * 9,) * 4,
            ((float("nan"),) * 10,) * 4,
            ((float("inf"),) * 10,) * 4,
            ((True,) * 10,) * 4,
        ):
            with self.subTest(banks=banks), self.assertRaises(ValueError):
                LogicalAoBanks(banks)

    def test_bad_tasks_and_adapters_are_rejected(self):
        for tasks in (TASKS[:3], list(TASKS), ("live",) * 4):
            with self.assertRaises(TypeError):
                record_ni6703_writes(
                    ScriptedBoundary(), ZERO, tasks=tasks, error_in=NO_ERROR
                )
        with self.assertRaises(TypeError):
            record_ni6703_writes(object(), ZERO, tasks=TASKS, error_in=NO_ERROR)

    def test_boundary_accepts_immutable_data_only(self):
        for data in ([1.0], (object(),), ((1.0,),), lambda: None):
            boundary = ScriptedBoundary()
            with self.assertRaises(TypeError):
                boundary.invoke(SOURCE, "592", "3", "record-only", data=data)
            self.assertEqual(boundary.calls, ())


if __name__ == "__main__":
    unittest.main()
