"""Saved Event23/24 callback traces; no NI or transport is touched."""
import sys
import unittest

from legacy.xp_acq_agent.elyse_agent.acquisition_impulsion import (
    FRAME_UIDS, ImpulsionExecutionCancelled, ImpulsionExecutionError,
    execute_impulsion,
)


class Harness(object):
    def __init__(self):
        self.trace = []
        self.banks = {36: tuple([True] * 29), 44: tuple([False] * 77)}
        self.cancel = False
        self.done_values = {3: [True], 4: [True]}
        self.fail = None

    def record(self, kind, *args):
        self.trace.append((kind,) + args)
        if self.fail is not None:
            self.fail(kind, args)

    def start(self, number):
        self.record("start", number)

    def stop(self, number):
        self.record("stop", number)

    def done(self, number):
        self.record("done", number)
        rows = self.done_values[number]
        return rows.pop(0) if len(rows) > 1 else rows[0]

    def read(self, bank):
        self.record("read", bank)
        return self.banks[bank]

    def write(self, bank, changes):
        self.record("write", bank, changes)
        if bank != 35:
            updated = list(self.banks[bank])
            for field, value in changes:
                updated[field] = value
            self.banks[bank] = tuple(updated)

    def publish(self, name, bank, values):
        self.record("publish", name, bank, values)

    def wait(self, seconds):
        self.record("wait", seconds)

    def cancelled(self):
        return self.cancel

    def observe(self, index, uid):
        self.record("frame", index, uid)

    def execute(self, operation, **kwargs):
        return execute_impulsion(operation, self.start, self.done, self.stop,
                                 self.read, self.write, self.publish, self.wait,
                                 self.cancelled, observer=self.observe, **kwargs)


class ImpulsionTests(unittest.TestCase):
    def test_start_exact_source_frames_assignments_and_publication_order(self):
        h = Harness()
        r = h.execute("modulator_impulse.start")
        self.assertEqual(r["completed_frames"], ["45203", "45276", "45385", "45576"])
        self.assertEqual(h.trace[:4], [
            ("frame", 0, "45203"), ("write", 35, ((-1, True),)),
            ("start", 3), ("start", 4)])
        self.assertEqual([row for row in h.trace if row[0] == "write"], [
            ("write", 35, ((-1, True),)), ("write", 36, ((18, False),)),
            ("write", 44, ((55, False), (52, True)))])
        self.assertEqual([row[1:3] for row in h.trace if row[0] == "publish"],
                         [("DPS", 36), ("EPS", 44)])
        self.assertEqual(h.trace[-1], ("wait", 0.1))
        self.assertEqual(r["counter_clear_error_boundaries"], [("45203", 3), ("45203", 4)])
        self.assertEqual(r["commanded_running_counters"], [3, 4])
        self.assertFalse(r["hardware_acknowledged"])
        self.assertTrue(r["ownership_retained_by_caller"])

    def test_stop_exact_source_including_eps42_not55(self):
        h = Harness()
        initial = list(h.banks[44])
        initial[55] = True
        h.banks[44] = tuple(initial)
        r = h.execute("modulator_impulse.stop")
        self.assertEqual(r["completed_frames"], ["40802", "49141", "41162", "41284", "41447"])
        counter_trace = [row for row in h.trace if row[0] in ("done", "stop", "wait")]
        self.assertEqual(counter_trace, [
            ("done", 3), ("wait", 0.001), ("stop", 3),
            ("done", 4), ("wait", 0.001), ("stop", 4), ("wait", 0.1)])
        self.assertEqual([row for row in h.trace if row[0] == "write"], [
            ("write", 35, ((-1, True),)), ("write", 36, ((19, False),)),
            ("write", 44, ((52, False), (42, True)))])
        self.assertTrue(h.banks[44][55])
        self.assertTrue(h.banks[44][42])
        self.assertFalse(h.banks[44][52])
        self.assertEqual(r["counter_polls"], [(3, "2745", 0, True), (4, "49233", 0, True)])
        self.assertEqual(r["pending_counter_stops"], [])

    def test_never_done_uses_42_reads_and42_waits_for_each_counter(self):
        h = Harness()
        h.done_values = {3: [False], 4: [False]}
        r = h.execute("modulator_impulse.stop")
        for number in (3, 4):
            rows = [row for row in r["counter_polls"] if row[0] == number]
            self.assertEqual(len(rows), 42)
            self.assertEqual([row[2] for row in rows], list(range(42)))
        self.assertEqual(h.trace.count(("wait", 0.001)), 84)
        self.assertTrue(r["completed"])
        self.assertFalse(r["hardware_acknowledged"])

    def test_done_on_later_iteration_stops_only_after_final_wait(self):
        h = Harness()
        h.done_values[3] = [False, False, True]
        r = h.execute("modulator_impulse.stop")
        self.assertEqual([row[2:] for row in r["counter_polls"] if row[0] == 3],
                         [(0, False), (1, False), (2, True)])
        stop_index = h.trace.index(("stop", 3))
        self.assertEqual(h.trace[stop_index - 1], ("wait", 0.001))

    def test_start_failure_is_retained_but_clear_boundary_continues_ctr4(self):
        h = Harness()
        def fail(kind, args):
            if kind == "start" and args == (3,):
                raise RuntimeError("start partially applied")
        h.fail = fail
        with self.assertRaises(ImpulsionExecutionError) as context:
            h.execute("modulator_impulse.start")
        r = context.exception.report
        self.assertIn(("start", 4), h.trace)
        self.assertEqual(r["completed_frames"], list(FRAME_UIDS["modulator_impulse.start"]))
        self.assertEqual(r["restoration_attempts"], [3, 4])
        self.assertEqual([row["counter"] for row in r["failures"]], [3])
        self.assertFalse(r["completed"])

    def test_pulse_errors_are_not_an_added_exit_predicate_or_task_done_fallback(self):
        h = Harness()
        def fail(kind, args):
            if kind == "done" and args == (3,):
                raise RuntimeError("pulse property unavailable")
        h.fail = fail
        with self.assertRaises(ImpulsionExecutionError) as context:
            h.execute("modulator_impulse.stop")
        r = context.exception.report
        self.assertEqual(h.trace.count(("done", 3)), 42)
        self.assertIn(("stop", 3), h.trace)
        self.assertIn(("stop", 4), h.trace)
        self.assertEqual(len(r["failures"]), 42)
        self.assertEqual(r["restoration_attempts"], [])

    def test_non_boolean_pulse_done_fails_closed_without_truthiness(self):
        for invalid in (0, 1, None, "False", [], object()):
            h = Harness()
            h.done_values[3] = [invalid]
            with self.assertRaises(ImpulsionExecutionError) as context:
                h.execute("modulator_impulse.stop")
            self.assertEqual(h.trace.count(("done", 3)), 42)
            self.assertTrue(all(row[3] is False for row in context.exception.report["counter_polls"]
                                if row[0] == 3))

    def test_stop_failure_preserves_pending_ownership_and_continues_second(self):
        h = Harness()
        def fail(kind, args):
            if kind == "stop" and args == (3,):
                raise RuntimeError("stop failure")
        h.fail = fail
        with self.assertRaises(ImpulsionExecutionError) as context:
            h.execute("modulator_impulse.stop")
        r = context.exception.report
        self.assertIn(("stop", 4), h.trace)
        self.assertEqual(r["pending_counter_stops"], [3])
        self.assertTrue(r["ownership_retained_by_caller"])
        self.assertEqual(r["completed_frames"], list(FRAME_UIDS["modulator_impulse.stop"]))

    def test_publication_error_short_circuits_eps_but_not_later_wait(self):
        h = Harness()
        def fail(kind, args):
            if kind == "publish" and args[0] == "DPS":
                raise RuntimeError("PSP failed")
        h.fail = fail
        with self.assertRaises(ImpulsionExecutionError):
            h.execute("modulator_impulse.start")
        self.assertEqual([row[1] for row in h.trace if row[0] == "publish"], ["DPS"])
        self.assertIn(("wait", 0.1), h.trace)

    def test_publication_reads_are_fresh_and_not_reconstructed_from_local_write(self):
        h = Harness()
        def fail(kind, args):
            if kind == "frame" and args[1] == "45385":
                h.banks[36] = tuple([False] * 29)
                h.banks[44] = tuple([True] * 77)
        h.fail = fail
        h.execute("modulator_impulse.start")
        rows = [row for row in h.trace if row[0] == "publish"]
        self.assertEqual(rows[0][3], tuple([False] * 29))
        self.assertEqual(rows[1][3], tuple([True] * 77))

    def test_invalid_local_snapshot_never_fabricates_bank_or_publishes(self):
        h = Harness()
        h.banks[44] = tuple([0] * 77)
        with self.assertRaises(ImpulsionExecutionError) as context:
            h.execute("modulator_impulse.start")
        self.assertFalse(any(row[0] == "publish" for row in h.trace))
        self.assertFalse(any(row[0] == "write" and row[1] == 44 for row in h.trace))
        self.assertTrue(context.exception.report["failures"])

    def test_false_new_value_no_callback_even_cancellation_observer(self):
        def poison(*args):
            raise AssertionError("false case must not touch callback")
        for operation in FRAME_UIDS:
            r = execute_impulsion(operation, *([poison] * 8), observer=poison, new_value=False)
            self.assertEqual(r["status"], "NOOP")
            self.assertEqual(r["completed_frames"], [])

    def test_all_argument_validation_precedes_any_callback(self):
        h = Harness()
        for operation in (None, "modulator.start", [], 23):
            with self.assertRaises(ValueError):
                h.execute(operation)
        for value in (None, 0, 1, "True"):
            with self.assertRaises(TypeError):
                h.execute("modulator_impulse.start", new_value=value)
        self.assertEqual(h.trace, [])

    def test_cancel_after_partial_start_stops_attempted_counter(self):
        h = Harness()
        def fail(kind, args):
            if kind == "start":
                h.cancel = True
        h.fail = fail
        with self.assertRaises(ImpulsionExecutionCancelled) as context:
            h.execute("modulator_impulse.start")
        self.assertEqual(context.exception.report["restoration_attempts"], [3])
        self.assertIn(("stop", 3), h.trace)
        self.assertNotIn(("start", 4), h.trace)

    def test_failed_start_cleanup_retains_indeterminate_live_counter(self):
        h = Harness()
        def fail(kind, args):
            if kind == "start" and args == (3,):
                raise RuntimeError("start may have applied")
            if kind == "stop" and args == (3,):
                raise RuntimeError("cannot confirm stopped")
        h.fail = fail
        with self.assertRaises(ImpulsionExecutionError) as context:
            h.execute("modulator_impulse.start")
        r = context.exception.report
        self.assertEqual(r["restoration_attempts"], [3, 4])
        self.assertEqual(r["pending_counter_stops"], [3])
        self.assertEqual(r["commanded_running_counters"], [3])
        self.assertTrue(r["restoration_failures"])
        self.assertFalse(r["hardware_acknowledged"])

    def test_callback_or_observer_failure_cannot_skip_stop_of_other_counter(self):
        for failure_kind in ("done", "wait", "read", "write", "publish", "frame"):
            h = Harness()
            fired = [False]
            def fail(kind, args):
                if kind == failure_kind and not fired[0]:
                    fired[0] = True
                    raise RuntimeError("injected " + kind)
            h.fail = fail
            with self.assertRaises(ImpulsionExecutionError) as context:
                h.execute("modulator_impulse.stop")
            self.assertIn(("stop", 3), h.trace)
            self.assertIn(("stop", 4), h.trace)
            self.assertTrue(context.exception.report["failures"])

    def test_cancelled_stop_attempts_both_even_with_failed_first_stop(self):
        h = Harness()
        h.cancel = True
        def fail(kind, args):
            if kind == "stop" and args == (3,):
                raise RuntimeError("failed cleanup stop")
        h.fail = fail
        with self.assertRaises(ImpulsionExecutionCancelled) as context:
            h.execute("modulator_impulse.stop")
        r = context.exception.report
        self.assertEqual(r["restoration_attempts"], [3, 4])
        self.assertEqual(r["pending_counter_stops"], [3])
        self.assertEqual(len(r["restoration_failures"]), 1)
        self.assertTrue(r["ownership_retained_by_caller"])

    def test_cancellation_each_frame_keeps_retained_counter_ownership(self):
        for operation, frames in FRAME_UIDS.items():
            for target in frames:
                h = Harness()
                def fail(kind, args):
                    if kind == "frame" and args[1] == target:
                        h.cancel = True
                h.fail = fail
                with self.assertRaises(ImpulsionExecutionCancelled) as context:
                    h.execute(operation)
                self.assertEqual(context.exception.report["status"], "CANCELLED")
                self.assertFalse(context.exception.report["hardware_acknowledged"])
                self.assertEqual(context.exception.report["pending_counter_stops"], [])

    def test_non_boolean_cancel_result_interrupts_and_restores(self):
        h = Harness()
        h.cancel = 1
        with self.assertRaises(ImpulsionExecutionError) as context:
            h.execute("modulator_impulse.stop")
        self.assertIn("exact Boolean", context.exception.report["failures"][0]["error"])
        self.assertEqual(context.exception.report["restoration_attempts"], [3, 4])

    @unittest.skipIf(sys.version_info < (3, 10), "source model uses modern syntax")
    def test_source_model_frames_and_counter_poll_predicates(self):
        from DeviceServers.control.elyse_acq.vi_simulation.procedure_sequences import (
            PROCEDURES, counter_poll_should_stop,
        )
        self.assertEqual(tuple(row[0] for row in PROCEDURES[23]), FRAME_UIDS["modulator_impulse.start"])
        self.assertEqual(tuple(row[0] for row in PROCEDURES[24]), FRAME_UIDS["modulator_impulse.stop"])
        self.assertIn(("counter_start_clear_chain", 21, (3, 4)), PROCEDURES[23][0][1])
        self.assertIn(("counter_poll_stop_clear", 21, 3, "2745", 40, 1), PROCEDURES[24][0][1])
        self.assertIn(("counter_poll_stop_clear", 21, 4, "49233", 40, 1), PROCEDURES[24][1][1])
        self.assertEqual(dict(PROCEDURES[23])["45276"], (
            ("write", 36, ((18, False),)),
            ("write", 44, ((52, True), (55, False)))))
        self.assertEqual(dict(PROCEDURES[24])["41162"], (
            ("write", 36, ((19, False),)),
            ("write", 44, ((42, True), (52, False)))))
        for body in ("2745", "49233"):
            self.assertEqual([counter_poll_should_stop(body, i, False) for i in range(42)],
                             [False] * 41 + [True])

    def test_start_saved_original_replay_wires_have_ordered_clear_chain(self):
        from legacy.xp_acq_agent.elyse_agent.saved_acq_event_45123 import STAGES, LEAF_INPUTS, BUNDLES
        self.assertEqual(STAGES, FRAME_UIDS["modulator_impulse.start"])
        self.assertIn(("52891", "return", "46267", "46319"), LEAF_INPUTS["52872"])
        self.assertIn(("54914", "return", "52872", "52879"), LEAF_INPUTS["54874"])
        self.assertIn(("20510", "return", "54874", "54926"), LEAF_INPUTS["2548"])
        self.assertEqual(tuple((row[1], row[2]) for row in BUNDLES["45320"][4]),
                         ((55, False), (52, True)))
        self.assertEqual(tuple((row[1], row[2]) for row in BUNDLES["45347"][4]),
                         ((18, False),))


if __name__ == "__main__":
    unittest.main()
