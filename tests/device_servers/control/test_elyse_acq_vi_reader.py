"""AI sample fixtures, mean bounds, card calibration and I/O error traces."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation import (
    NO_ERROR,
    UNSUPPLIED,
    CallKey,
    DigitalOutputBanks,
    ErrorCluster,
    LogicalAoBanks,
    SampleMatrix,
    ScriptedBoundary,
    TaskReference,
    merge_card_errors,
    project_card_samples,
    record_dio96_exchange,
    record_ni6071e_reads,
    record_ni6703_writes,
)
from DeviceServers.control.elyse_acq.vi_simulation.read_ni6071e import (
    C1_OFFSETS,
    C1_SLOPES,
    C2_OFFSETS,
    C2_SLOPES,
    READ_UIDS_BY_CARD,
    SOURCE,
)

TASKS = (TaskReference("supplied-C1"), TaskReference("supplied-C2"))
C1_FAULT = ErrorCluster(True, -901, "supplied C1 fault")
C2_FAULT = ErrorCluster(True, -902, "supplied C2 fault")
C1_WARNING = ErrorCluster(False, 901, "supplied C1 warning")
C2_WARNING = ErrorCluster(False, 902, "supplied C2 warning")


def data(c1, c2):
    return {
        CallKey(SOURCE.name, READ_UIDS_BY_CARD[0]): c1,
        CallKey(SOURCE.name, READ_UIDS_BY_CARD[1]): c2,
    }


def run(boundary, error=NO_ERROR):
    return record_ni6071e_reads(
        boundary, tasks=TASKS, samples_per_channel=1000, error_in=error
    )


class AnalogReadGoldenTests(unittest.TestCase):
    def test_both_reads_receive_original_error_and_independent_tasks(self):
        boundary = ScriptedBoundary(
            data=data(SampleMatrix(((1.0, 3.0),)), SampleMatrix(((2.0, 4.0),))),
            errors={CallKey(SOURCE.name, "1269"): C1_FAULT},
        )
        result = run(boundary)
        boundary.assert_all_fixtures_used()
        self.assertEqual(result.banks, ((20.0,), (4.11,)))
        self.assertEqual(result.error_out, C1_FAULT)
        self.assertEqual(tuple(c.task_in for c in result.calls), TASKS)
        self.assertEqual(tuple(c.error_in for c in result.calls), (NO_ERROR, NO_ERROR))
        self.assertEqual(
            tuple(c.args["samples_per_channel"] for c in result.calls), (1000, 1000)
        )
        self.assertEqual(
            tuple(c.args["timeout_seconds"] for c in result.calls), (1.0, 1.0)
        )
        self.assertTrue(
            all(c.args["polymorphic_selector"] == "08" for c in result.calls)
        )

    def test_all_256_connected_calibration_elements(self):
        matrix = SampleMatrix(((1.0, 3.0),) * 64)
        for card, slopes, offsets in (
            (1, C1_SLOPES, C1_OFFSETS),
            (2, C2_SLOPES, C2_OFFSETS),
        ):
            projected = project_card_samples(matrix, card=card)
            self.assertEqual(len(projected), 64)
            self.assertEqual(
                projected, tuple(2 * a + b for a, b in zip(slopes, offsets))
            )
        self.assertEqual(project_card_samples(matrix, card=1)[0], 20.0)
        self.assertEqual(project_card_samples(matrix, card=2)[7], 4.88)
        self.assertEqual(project_card_samples(matrix, card=2)[34], 30.639)

    def test_constant_channel_bound_is_not_requested_sample_count(self):
        for rows, expected in (((), 0), (((2.0,),) * 3, 3), (((2.0,),) * 65, 64)):
            self.assertEqual(
                len(project_card_samples(SampleMatrix(rows), card=1)), expected
            )
        result = record_ni6071e_reads(
            ScriptedBoundary(data=data(SampleMatrix(((2.0,),) * 3), SampleMatrix(()))),
            tasks=TASKS,
            samples_per_channel=1,
            error_in=NO_ERROR,
        )
        self.assertEqual(tuple(map(len, result.banks)), (3, 0))

    def test_saved_false_arm_is_raw_projection_not_a_public_control(self):
        self.assertEqual(
            project_card_samples(SampleMatrix(((1.0, 3.0),)), card=1, calibrated=False),
            (2.0,),
        )
        result = run(
            ScriptedBoundary(data=data(SampleMatrix(((1.0, 3.0),)), SampleMatrix(())))
        )
        self.assertEqual(result.banks[0], (20.0,))

    def test_missing_reads_do_not_become_zero_measurements(self):
        result = run(ScriptedBoundary())
        self.assertEqual(result.banks, (UNSUPPLIED, UNSUPPLIED))
        self.assertEqual(
            result.error_out, NO_ERROR
        )  # Supplied default, not data-validity proof.

    def test_data_is_projected_despite_returned_error(self):
        result = run(
            ScriptedBoundary(
                data=data(SampleMatrix(((0.0,),)), SampleMatrix(((0.0,),))),
                errors={
                    CallKey(SOURCE.name, "1269"): C1_FAULT,
                    CallKey(SOURCE.name, "269"): C2_FAULT,
                },
            )
        )
        self.assertEqual(result.banks, ((10.0,), (0.0,)))
        self.assertEqual(result.read_errors, (C1_FAULT, C2_FAULT))
        self.assertEqual(result.error_out, C1_FAULT)

    def test_error_merge_prioritizes_errors_over_warnings_then_c1_over_c2(self):
        for first, second, expected in (
            (C1_FAULT, C2_FAULT, C1_FAULT),
            (C1_WARNING, C2_FAULT, C2_FAULT),
            (C1_FAULT, C2_WARNING, C1_FAULT),
            (C1_WARNING, C2_WARNING, C1_WARNING),
            (NO_ERROR, C2_WARNING, C2_WARNING),
            (NO_ERROR, NO_ERROR, NO_ERROR),
        ):
            self.assertEqual(merge_card_errors(first, second), expected)

    def test_i32_count_domain_preserves_minus_one_and_zero(self):
        for count in (-1, 0):
            result = record_ni6071e_reads(
                ScriptedBoundary(),
                tasks=TASKS,
                samples_per_channel=count,
                error_in=NO_ERROR,
            )
            self.assertEqual(result.calls[0].args["samples_per_channel"], count)
        for count in (True, 1.5, 2**31, -(2**31) - 1):
            with self.assertRaises(ValueError):
                record_ni6071e_reads(
                    ScriptedBoundary(),
                    tasks=TASKS,
                    samples_per_channel=count,
                    error_in=NO_ERROR,
                )

    def test_python_only_mean_domain_guards_do_not_invent_measurements(self):
        for matrix in (
            SampleMatrix(((),)),
            SampleMatrix(((float("nan"),),)),
            SampleMatrix(((float("inf"),),)),
            SampleMatrix(((1e308, 1e308),)),
        ):
            with self.assertRaises(ValueError):
                project_card_samples(matrix, card=1)

    def test_matrix_fixtures_are_immutable_rectangular_and_non_executable(self):
        for rows in ([[]], ((1.0,), ()), ((True,),), ((object(),),), ((lambda: 1,),)):
            with self.assertRaises(TypeError):
                SampleMatrix(rows)
        with self.assertRaises(TypeError):
            run(object())

    def test_complete_bounded_ai_dio_ao_error_chain_uses_supplied_data(self):
        boundary = ScriptedBoundary(
            data=data(SampleMatrix(((0.0,),)), SampleMatrix(((0.0,),))),
            errors={CallKey(SOURCE.name, "1269"): C1_FAULT},
        )
        ai = run(boundary)
        dio = record_dio96_exchange(
            boundary,
            DigitalOutputBanks(((False,),) * 3),
            tasks=tuple(TaskReference(f"supplied-DIO-{i}") for i in range(6)),
            error_in=ai.error_out,
        )
        ao = record_ni6703_writes(
            boundary,
            LogicalAoBanks(((0.0,) * 10,) * 4),
            tasks=tuple(TaskReference(f"supplied-AO-{i}") for i in range(4)),
            error_in=dio.error_out,
        )
        self.assertEqual(len(boundary.calls), 12)
        self.assertEqual(ao.error_out, C1_FAULT)
        self.assertTrue(all(c.error_in == C1_FAULT for c in boundary.calls[2:]))
        self.assertEqual(ai.banks, ((10.0,), (0.0,)))


if __name__ == "__main__":
    unittest.main()
