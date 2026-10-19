"""No driver: dormant helper task/error wiring and supplied Mean returns."""

import math
import unittest

from DeviceServers.control.elyse_acq.vi_simulation.boundary import (
    NO_ERROR,
    UNASSIGNED,
    UNSUPPLIED,
    UNWIRED,
    CallKey,
    ErrorCluster,
    SampleClockInputs,
    SampleMatrix,
    ScriptedBoundary,
    TaskReference,
)
from DeviceServers.control.elyse_acq.vi_simulation.ni6259_dormant import (
    INIT_SOURCE,
    READ_SOURCE,
    initialize,
    project_means,
    read,
)

FAULT = ErrorCluster(True, -123, "supplied failure")
WARNING = ErrorCluster(False, 456, "supplied warning")
CLOCK = SampleClockInputs(8123.5, 17)
TASK = TaskReference("supplied task")


def reader(boundary, samples=17, error=NO_ERROR):
    return read(boundary, task=TASK, samples_per_channel=samples, error_in=error)


def fixtures(rows, means, *, errors=None):
    data = {CallKey(READ_SOURCE.name, "1269"): SampleMatrix(rows)}
    data.update(
        {CallKey(READ_SOURCE.name, "359", i): (m,) for i, m in enumerate(means)}
    )
    return ScriptedBoundary(data=data, errors=errors)


class DormantInitializerTests(unittest.TestCase):
    def test_exact_eight_channel_none_trigger_trace(self):
        result = initialize(ScriptedBoundary(), clock=CLOCK, error_in=FAULT)
        self.assertEqual(len(result.calls), 12)
        self.assertIs(result.calls[0].error_in, UNWIRED)
        self.assertEqual(
            result.calls[0].args, {"name": "C1_NI6220", "auto_cleanup": True}
        )
        self.assertEqual(
            [c.args["physical_channel"] for c in result.calls[1:9]],
            [f"11/ai{i}" for i in range(8)],
        )
        for call in result.calls[1:9]:
            self.assertEqual((call.args["minimum"], call.args["maximum"]), (-0.2, 0.2))
            self.assertEqual(call.args["terminal_configuration_code"], 0x277A)
            self.assertEqual(call.task_in, result.calls[0].returned.task)
            self.assertEqual(call.error_in, result.calls[0].returned.error)
        self.assertEqual(result.calls[9].args["samples_per_channel"], 17)
        self.assertEqual(result.calls[9].args["rate_hz"], 8123.5)
        self.assertEqual(result.calls[10].operation, "configure_start_trigger_none")
        self.assertEqual(result.calls[10].args, {"polymorphic_selector": "02"})
        self.assertTrue(result.calls[11].args["auto_start"])
        self.assertIs(result.error_out, UNASSIGNED)
        self.assertFalse(
            any(
                c.operation in ("start_task", "write", "stop_task", "clear_task")
                for c in result.calls
            )
        )

    def test_every_channel_fault_uses_shared_create_seed_not_accumulation(self):
        for i in range(8):
            with self.subTest(channel=i):
                boundary = ScriptedBoundary(
                    errors={CallKey(INIT_SOURCE.name, "2818", i): FAULT}
                )
                result = initialize(boundary, clock=CLOCK, error_in=WARNING)
                self.assertTrue(all(c.error_in == NO_ERROR for c in result.calls[1:9]))
                self.assertEqual(result.internal_error, FAULT if i == 7 else NO_ERROR)
                self.assertIs(result.error_out, UNASSIGNED)
                boundary.assert_all_fixtures_used()

    def test_create_and_post_loop_faults_reach_internal_but_not_public_output(self):
        for uid in ("2629", "2393", "2454", "2561"):
            with self.subTest(uid=uid):
                result = initialize(
                    ScriptedBoundary(errors={CallKey(INIT_SOURCE.name, uid): FAULT}),
                    clock=CLOCK,
                    error_in=NO_ERROR,
                    public_error_out_seed=WARNING,
                )
                self.assertEqual(result.internal_error, FAULT)
                self.assertEqual(result.error_out, WARNING)
                self.assertEqual(len(result.calls), 12)

    def test_last_channel_task_not_first_return_feeds_timing(self):
        first, last = TaskReference("first"), TaskReference("last")
        result = initialize(
            ScriptedBoundary(
                tasks={
                    CallKey(INIT_SOURCE.name, "2818", 0): first,
                    CallKey(INIT_SOURCE.name, "2818", 7): last,
                }
            ),
            clock=CLOCK,
            error_in=NO_ERROR,
        )
        self.assertNotEqual(result.calls[2].task_in, first)
        self.assertEqual(result.calls[9].task_in, last)
        self.assertEqual(result.tasks, (last,))

    def test_invalid_inputs_rejected_before_boundary_call(self):
        for kwargs in ({"clock": object()}, {"public_error_out_seed": NO_ERROR.status}):
            boundary = ScriptedBoundary()
            inputs = dict(clock=CLOCK, error_in=NO_ERROR)
            inputs.update(kwargs)
            with self.assertRaises(TypeError):
                initialize(boundary, **inputs)
            self.assertEqual(boundary.calls, ())
        with self.assertRaisesRegex(TypeError, "in-memory ScriptedBoundary"):
            initialize(object(), clock=CLOCK, error_in=NO_ERROR)


class DormantReaderTests(unittest.TestCase):
    def test_samples_do_not_bound_channels_or_truncate_rows(self):
        rows = tuple((float(i), float(i + 100)) for i in range(12))
        for samples in (-1, 0, 1, 7, 8, 17, 1000):
            with self.subTest(samples=samples):
                boundary = fixtures(rows, tuple(float(i + 1000) for i in range(8)))
                result = reader(boundary, samples=samples, error=WARNING)
                self.assertEqual(result.bank, tuple(float(i + 1000) for i in range(8)))
                self.assertEqual(len(result.calls), 9)
                self.assertEqual(result.calls[0].args["samples_per_channel"], samples)
                self.assertEqual(result.calls[0].args["timeout_seconds"], -1.0)
                self.assertEqual(
                    [c.args["samples"] for c in result.calls[1:]], list(rows[:8])
                )
                self.assertTrue(all(c.error_in is UNWIRED for c in result.calls[1:]))
                self.assertEqual(result.error_out, WARNING)
                boundary.assert_all_fixtures_used()

    def test_short_returned_matrices_produce_only_present_rows(self):
        for n in range(17):
            with self.subTest(rows=n):
                rows = tuple((float(i),) for i in range(n))
                values = tuple(float(100 + i) for i in range(min(n, 8)))
                result = reader(fixtures(rows, values))
                self.assertEqual(result.bank, values)
                self.assertEqual(len(result.calls), 1 + min(n, 8))

    def test_read_error_is_returned_but_does_not_gate_supplied_data(self):
        boundary = fixtures(
            ((123.0,),), (456.0,), errors={CallKey(READ_SOURCE.name, "1269"): FAULT}
        )
        result = reader(boundary)
        self.assertEqual(result.error_out, FAULT)
        self.assertEqual(result.bank, (456.0,))

    def test_mean_error_is_unused_and_does_not_gate_later_means(self):
        boundary = fixtures(
            ((1.0,), (2.0,)),
            (12.0, 34.0),
            errors={CallKey(READ_SOURCE.name, "359", 0): FAULT},
        )
        result = reader(boundary)
        self.assertEqual(result.bank, (12.0, 34.0))
        self.assertEqual(result.error_out, NO_ERROR)
        self.assertIs(result.calls[2].error_in, UNWIRED)
        self.assertEqual(result.calls[1].returned.error, FAULT)

    def test_empty_rows_are_mean_boundaries_not_guessed_zero_or_division(self):
        result = reader(fixtures(((), ()), (float("nan"), float("inf"))))
        self.assertTrue(math.isnan(result.bank[0]))
        self.assertEqual(result.bank[1], float("inf"))
        self.assertEqual([c.args["samples"] for c in result.calls[1:]], [(), ()])

    def test_missing_read_data_not_equated_to_empty_array(self):
        result = reader(ScriptedBoundary())
        self.assertIs(result.bank, UNSUPPLIED)
        self.assertIs(result.mean_returns, UNSUPPLIED)
        self.assertEqual(len(result.calls), 1)
        empty = reader(fixtures((), ()))
        self.assertEqual(empty.bank, ())
        self.assertEqual(empty.mean_returns, ())
        self.assertEqual(len(empty.calls), 1)

    def test_missing_mean_return_keeps_whole_bank_unknown_without_skipping_peers(self):
        result = reader(fixtures(((1.0,), (2.0,)), ()))
        self.assertIs(result.bank, UNSUPPLIED)
        self.assertEqual(result.mean_returns, (UNSUPPLIED, UNSUPPLIED))
        self.assertEqual(len(result.calls), 3)

    def test_invalid_read_and_mean_return_shapes_rejected(self):
        for data in (
            {CallKey(READ_SOURCE.name, "1269"): (1.0,)},
            {
                CallKey(READ_SOURCE.name, "1269"): SampleMatrix(((1.0,),)),
                CallKey(READ_SOURCE.name, "359", 0): (),
            },
            {
                CallKey(READ_SOURCE.name, "1269"): SampleMatrix(((1.0,),)),
                CallKey(READ_SOURCE.name, "359", 0): (True,),
            },
        ):
            with self.subTest(data=data), self.assertRaises(TypeError):
                reader(ScriptedBoundary(data=data))

    def test_caller_inputs_are_guarded_not_repaired(self):
        for samples in (True, 1.0, -(2**31) - 1, 2**31):
            with self.subTest(samples=samples), self.assertRaises(ValueError):
                reader(ScriptedBoundary(), samples=samples)
        with self.assertRaises(TypeError):
            read(
                ScriptedBoundary(),
                task=object(),
                samples_per_channel=1,
                error_in=NO_ERROR,
            )

    def test_raw_and_inactive_calibration_projection_are_distinct(self):
        self.assertEqual(project_means((2.0, 3.0)), (2.0, 3.0))
        self.assertEqual(project_means((2.0, 3.0), calibrated=True), (20.0, 3.0))
        self.assertEqual(project_means((), calibrated=True), ())
        self.assertEqual(math.copysign(1.0, project_means((-0.0,))[0]), -1.0)
        for means, selector in (((0.0,) * 9, False), ((True,), False), ((1.0,), 1)):
            with (
                self.subTest(means=means, selector=selector),
                self.assertRaises(TypeError),
            ):
                project_means(means, calibrated=selector)


if __name__ == "__main__":
    unittest.main()
