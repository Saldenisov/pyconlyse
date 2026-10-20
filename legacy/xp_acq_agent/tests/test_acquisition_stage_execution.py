"""Fourteen literal VI paths, fake callbacks only; runnable on Python 3.4."""
import copy
import unittest
from unittest.mock import patch

from legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution import (
    SUPPORTED_OPERATIONS, StageExecutionCancelled, StageExecutionError,
    execute_stage,
)
from legacy.xp_acq_agent.elyse_agent.acquisition_stage_model import BANK_SHAPES


def W(bank, *changes):
    return ("write", bank, tuple(changes))


def T(milliseconds):
    return ("wait", milliseconds / 1000.0)


P = ("publish", "DPS", 36)
E = ("publish", "EPS", 44)
C = ("publish", "C4_OUT_DIO96", 15)
A = W(35, (-1, True))
# Independent transcription of source frame UIDs and literal effects. Same-
# frame effect order below is the explicitly selected Python adapter schedule.
EXPECTED = {
    "cooling.start": [
        ("18796", [W(17, (0, True)), A, T(1000)]),
        ("22995", [W(17, (0, False))]), ("23795", [T(800)]),
        ("11213", [W(17, (3, True)), T(1000)]),
        ("31625", [W(17, (3, False))]),
        ("23074", [W(15, (0, True)), T(1000)]),
        ("26107", [W(15, (0, False))]), ("29164", [T(500)]),
        ("20440", [W(15, (2, True)), T(1000)]),
        ("18859", [W(15, (2, False))]),
        ("24540", [W(36, (0, False)), W(44, (0, False), (1, False),
                    (2, True), (5, False), (8, True))]),
        ("18950", [P, T(5000)]),
    ],
    "cooling.stop": [
        ("7963", [W(17, (1, False)), A, T(150)]),
        ("18101", [W(17, (1, True))]), ("21010", [T(400)]),
        ("21712", [W(17, (4, False)), T(150)]),
        ("22060", [W(17, (4, True)), T(150)]),
        ("22878", [W(36, (1, False)), W(44, (1, False), (2, False),
                    (3, False), (5, True))]),
        ("23117", [P, T(100)]),
    ],
    "chauffage.start": [
        ("38074", [W(15, (3, True)), A, T(150)]),
        ("38157", [W(15, (3, False))]), ("38205", [T(3000)]),
        ("38235", [W(15, (2, True)), T(150)]),
        ("38295", [W(15, (2, False))]),
        ("38483", [W(36, (4, False)), W(44, (12, False), (14, True), (17, False))]),
        ("38592", [P, T(100)]),
    ],
    "chauffage.stop": [
        ("23304", [W(15, (4, False)), A, T(150)]),
        ("23392", [W(15, (4, True))]),
        ("24497", [W(36, (5, False)), W(44, (14, False), (15, False), (17, True))]),
        ("25430", [P, T(100)]),
    ],
    "prema.start": [
        ("24338", [W(15, (5, True)), A, T(150)]),
        ("25366", [W(15, (5, False))]), ("28640", [T(500)]),
        ("28837", [W(15, (2, True)), T(150)]),
        ("28946", [W(15, (2, False))]), ("28995", [T(250)]),
        ("29025", [W(36, (6, False)), W(44, (18, False), (20, True), (23, False))]),
        ("29203", [P, T(100)]),
    ],
    "prema.stop": [
        ("26246", [W(15, (6, False)), A, T(150)]),
        ("26330", [W(15, (6, True))]),
        ("26962", [W(36, (7, False)), W(44, (20, False), (21, False), (23, True))]),
        ("27900", [P, T(100)]),
    ],
    "relays_ht.start": [
        ("36023", [W(15, (16, True)), A, T(150)]),
        ("36115", [W(15, (16, False))]), ("36163", [T(500)]),
        ("36193", [W(15, (2, True)), T(150)]),
        ("36255", [W(15, (2, False))]), ("36304", [T(250)]),
        ("36334", [W(36, (8, False)), W(44, (24, False), (26, True), (29, False))]),
        ("36443", [P, T(100)]),
    ],
    "relays_ht.stop": [
        ("31017", [W(15, (17, False)), A, T(150)]),
        ("31192", [W(15, (17, True))]),
        ("31360", [W(36, (9, False)), W(44, (26, False), (27, False), (29, True))]),
        ("31482", [P, T(100)]),
    ],
    "modulator.reset": [
        ("33697", [W(15, (2, True)), A, T(150)]),
        ("33780", [W(15, (2, False))]),
        ("33828", [W(36, (12, False)), W(44, (36, False))]),
        ("33986", [P, T(100)]),
    ],
    "alimentation_ht.start": [
        ("53995", [W(15, (18, True)), A, T(150)]),
        ("54078", [W(15, (18, False))]),
        ("54126", [W(36, (15, False)), W(44, (45, True), (49, False))]),
        ("54238", [P, E, C]),
        ("50555", [T(100)]),
    ],
    "alimentation_ht.stop": [
        ("31696", [W(15, (19, False)), A, T(150)]),
        ("31883", [W(15, (19, True))]),
        ("32123", [W(36, (17, False)), W(44, (45, False), (49, True))]),
        ("32374", [P, E, C]),
        ("32729", [T(100)]),
    ],
    "alimentation_ht.reset": [
        ("32931", [W(15, (20, True)), A, T(150)]),
        ("33169", [W(15, (20, False))]),
        ("33217", [W(36, (16, False))]),
        ("33438", [P, E, C]),
        ("33886", [T(100)]),
    ],
}


# Flattened preorder observer schedule includes source containers. Container
# completion follows children, separately checked below, not asserted preorder.
FOCAL_EXPECTED = {
    "focales.start": [
        ("40162", [W(15, (7, True)), A, T(150)]),
        ("40245", [W(15, (7, False))]), ("40293", []),
        ("46840", [T(29000)]),
        ("48404", [("helper", "1_Focales ON.vi")]),
        ("49054", [T(1500)]),
        ("40323", [W(15, (2, True)), T(150)]),
        ("40383", [W(15, (2, False))]), ("40432", [T(250)]),
        ("40463", [W(36, (10, False)), W(44, (30, False), (32, True), (35, False))]),
        ("40573", [P, T(100)]),
    ],
    "focales.stop": [
        ("23518", [A]),
        ("57312", [("helper", "1_Focales OFF.vi")]),
        ("47864", [T(500), T(150)]),
        ("54833", [W(15, (8, False)), T(150)]),
        ("23774", [W(15, (8, True))]),
        ("23880", [W(36, (11, False)), W(44, (32, False), (33, False), (35, True))]),
        ("24054", [P, T(100)]),
    ],
}
FOCAL_COMPLETED = {
    "focales.start": ["40162", "40245", "46840", "48404", "49054", "40293",
                      "40323", "40383", "40432", "40463", "40573"],
    "focales.stop": ["57312", "47864", "23518", "54833", "23774", "23880", "24054"],
}


class FakeLocals(object):
    def __init__(self):
        self.locals = {bank: tuple(bool(i % 2) for i in range(size))
                       for bank, size in BANK_SHAPES.items()}
        self.locals[35] = None  # No invented initialization of scalar ACTION.
        self.before = copy.deepcopy(self.locals)
        self.trace, self.reads = [], []
        self.write_count = 0
        self.fail_write = None
        self.fail_all_outputs = False
        self.cancel = False

    def read(self, bank):
        self.reads.append(bank)
        return self.locals[bank]

    def write(self, bank, changes):
        self.write_count += 1
        self.trace.append(("write", bank, changes))
        if bank == 35:
            self.locals[bank] = changes[0][1]
        else:
            values = list(self.locals[bank])
            for index, value in changes:
                values[index] = value
            self.locals[bank] = tuple(values)
        # Model a partial/complete applied write followed by an adapter error.
        if (self.write_count == self.fail_write or
                (self.fail_all_outputs and bank in (15, 17))):
            raise RuntimeError("injected post-application write error")

    def publish(self, name, bank, snapshot):
        self.trace.append(("publish", name, bank, snapshot))

    def wait(self, seconds):
        self.trace.append(("wait", seconds))

    def observe(self, index, uid):
        self.trace.append(("frame", index, uid))

    def cancelled(self):
        return self.cancel

    def helper(self, name):
        self.trace.append(("helper", name))

    def execute(self, operation, **changes):
        options = dict(read_local=self.read, write_local=self.write,
                       publish=self.publish, wait_seconds=self.wait,
                       cancelled=self.cancelled, frame_observer=self.observe,
                       operator_confirmed=True)
        options.update(changes)
        return execute_stage(operation, **options)


class StageExecutionTests(unittest.TestCase):
    def test_focal_nominal_nested_order_all_18_frames_and_literal_effects(self):
        observed_count = 0
        for operation, frames in FOCAL_EXPECTED.items():
            fake = FakeLocals()
            expected, state = [], copy.deepcopy(fake.locals)
            for index, (uid, effects) in enumerate(frames):
                expected.append(("frame", index, uid))
                entry = copy.deepcopy(state)
                for effect in effects:
                    if effect[0] == "write":
                        expected.append(effect)
                        _, bank, changes = effect
                        if bank == 35:
                            state[bank] = True
                        else:
                            values = list(state[bank])
                            for field, value in changes:
                                values[field] = value
                            state[bank] = tuple(values)
                    elif effect[0] == "publish":
                        expected.append(effect + (entry[effect[2]],))
                    else:
                        expected.append(effect)
            report = fake.execute(operation, focal_helper=fake.helper)
            self.assertEqual(fake.trace, expected, operation)
            self.assertEqual(fake.locals, state, operation)
            self.assertEqual(report["completed_frames"], FOCAL_COMPLETED[operation])
            self.assertEqual(report["completed_frames_order"], "completion_postorder")
            self.assertEqual(report["frame_observer_order"], "preorder")
            self.assertEqual(report["status"], "COMPLETED")
            self.assertFalse(report["hardware_acknowledged"])
            self.assertEqual(report["helper_attempts"][0]["status"], "CALLBACK_COMPLETED")
            self.assertEqual(report["pending_output_restorations"], [])
            self.assertEqual(report["adapter_schedule"],
                             "writes_then_nested_or_helper_then_publish_then_wait")
            observed_count += len([item for item in fake.trace if item[0] == "frame"])
        self.assertEqual(observed_count, 18)

    def test_focal_true_requires_helper_before_initial_local_reads_or_effects(self):
        for operation in FOCAL_EXPECTED:
            for callback in (None, 0, "fake helper"):
                fake = FakeLocals()
                with self.assertRaises(ValueError):
                    fake.execute(operation, focal_helper=callback)
                self.assertEqual(fake.trace + fake.reads, [])

    def test_focal_false_newval_needs_no_helper_and_has_no_callbacks(self):
        for operation in FOCAL_EXPECTED:
            fake = FakeLocals()
            report = fake.execute(operation, new_value=False)
            self.assertEqual(report["status"], "NOOP")
            self.assertEqual(report["helper_attempts"], [])
            self.assertEqual(fake.trace + fake.reads, [])

    def test_focal_long_waits_use_injected_wait_and_stop_serialization_is_explicit(self):
        start, stop = FakeLocals(), FakeLocals()
        start.execute("focales.start", focal_helper=start.helper)
        stop.execute("focales.stop", focal_helper=stop.helper)
        self.assertEqual([item[1] for item in start.trace if item[0] == "wait"],
                         [0.15, 29.0, 1.5, 0.15, 0.25, 0.1])
        self.assertEqual([item[1] for item in stop.trace if item[0] == "wait"],
                         [0.5, 0.15, 0.15, 0.1])
        self.assertLess(stop.trace.index(("wait", 0.5)), stop.trace.index(("wait", 0.15)))

    def test_focal_helper_failure_start_aborts_but_stop_attempts_remaining_frames(self):
        for operation in FOCAL_EXPECTED:
            fake = FakeLocals()
            def helper(name):
                fake.helper(name)
                raise RuntimeError("injected helper failure")
            with self.assertRaises(StageExecutionError) as raised:
                fake.execute(operation, focal_helper=helper)
            report = raised.exception.report
            self.assertEqual(report["status"], "PARTIAL_FAILURE")
            self.assertEqual(report["helper_attempts"][0]["status"], "FAILED")
            self.assertEqual(report["failures"][0]["helper"],
                             "1_Focales OFF.vi" if operation.endswith(".stop") else "1_Focales ON.vi")
            self.assertFalse(report["hardware_acknowledged"])
            self.assertEqual(report["pending_output_restorations"], [])
            if operation.endswith(".stop"):
                self.assertEqual(fake.trace[-1], T(100))
                self.assertIn(W(15, (8, False)), fake.trace)
                self.assertIn(W(15, (8, True)), fake.trace)
                self.assertTrue(fake.locals[44][35])  # Source software intent only.
                self.assertNotIn("23518", report["completed_frames"])
                self.assertNotIn("57312", report["completed_frames"])
            else:
                self.assertNotIn(("wait", 1.5), fake.trace)
                self.assertNotIn(W(15, (2, True)), fake.trace)
                self.assertFalse(any(item[0] == "publish" for item in fake.trace))
                self.assertNotIn("40293", report["completed_frames"])

    def test_focal_helper_failure_with_cancel_takes_precedence_and_keeps_diagnostics(self):
        for operation in FOCAL_EXPECTED:
            fake = FakeLocals()
            def helper(name):
                fake.helper(name)
                fake.cancel = True
                raise RuntimeError("cancelled while helper remained active")
            with self.assertRaises(StageExecutionCancelled) as raised:
                fake.execute(operation, focal_helper=helper)
            report = raised.exception.report
            self.assertEqual(report["status"], "CANCELLED")
            self.assertEqual(report["helper_attempts"][0]["status"], "FAILED")
            self.assertIn("helper remained active", report["helper_attempts"][0]["error"])
            self.assertIn("helper", report["failures"][0])
            self.assertFalse(any(item[0] == "publish" for item in fake.trace))
            if operation.endswith(".stop"):
                self.assertFalse(any(item[0] == "write" and item[1] == 15 for item in fake.trace))

    def test_focal_cancel_after_successful_helper_prevents_later_frames(self):
        for operation in FOCAL_EXPECTED:
            fake = FakeLocals()
            def helper(name):
                fake.helper(name)
                fake.cancel = True
            with self.assertRaises(StageExecutionCancelled) as raised:
                fake.execute(operation, focal_helper=helper)
            self.assertEqual(raised.exception.report["helper_attempts"][0]["status"],
                             "CALLBACK_COMPLETED")
            self.assertFalse(any(item[0] == "publish" for item in fake.trace))

    def test_focal_every_local_write_fault_is_visible_with_inflight_restoration(self):
        for operation, frames in FOCAL_EXPECTED.items():
            writes = [effect for uid, effects in frames for effect in effects if effect[0] == "write"]
            for number, effect in enumerate(writes, 1):
                fake = FakeLocals()
                fake.fail_write = number
                with self.assertRaises(StageExecutionError) as raised:
                    fake.execute(operation, focal_helper=fake.helper)
                self.assertEqual(raised.exception.report["status"], "PARTIAL_FAILURE")
                self.assertTrue(any(item["phase"] == "write" for item in raised.exception.report["failures"]))
                if effect[1] in (15, 17):
                    offset = [i for i, item in enumerate(fake.trace) if item[0] == "write"][number - 1]
                    baseline = tuple((field, fake.before[effect[1]][field]) for field, value in effect[2])
                    self.assertEqual(fake.trace[offset + 1], ("write", effect[1], baseline))
                if operation.endswith(".stop"):
                    self.assertEqual(fake.trace[-1], T(100))

    def test_focal_cancel_at_every_write_and_wait_boundary(self):
        for operation, frames in FOCAL_EXPECTED.items():
            for target_kind in ("write", "wait"):
                effects = [effect for uid, effects in frames for effect in effects if effect[0] == target_kind]
                for target in range(1, len(effects) + 1):
                    fake, count = FakeLocals(), [0]
                    def write(bank, changes):
                        fake.write(bank, changes)
                        if target_kind == "write":
                            count[0] += 1
                            if count[0] == target:
                                fake.cancel = True
                    def wait(seconds):
                        fake.wait(seconds)
                        if target_kind == "wait":
                            count[0] += 1
                            if count[0] == target:
                                fake.cancel = True
                    with self.assertRaises(StageExecutionCancelled) as raised:
                        fake.execute(operation, focal_helper=fake.helper,
                                     write_local=write, wait_seconds=wait)
                    self.assertEqual(raised.exception.report["status"], "CANCELLED")
                    self.assertFalse(raised.exception.report["hardware_acknowledged"])

    def test_focal_every_wait_fault_is_visible_and_stop_keeps_software_intent(self):
        for operation, frames in FOCAL_EXPECTED.items():
            waits = [effect for uid, effects in frames for effect in effects if effect[0] == "wait"]
            for target in range(1, len(waits) + 1):
                fake, count = FakeLocals(), [0]
                def wait(seconds):
                    fake.wait(seconds)
                    count[0] += 1
                    if count[0] == target:
                        raise RuntimeError("injected wait failure")
                with self.assertRaises(StageExecutionError) as raised:
                    fake.execute(operation, focal_helper=fake.helper, wait_seconds=wait)
                self.assertEqual(raised.exception.report["status"], "PARTIAL_FAILURE")
                self.assertEqual(raised.exception.report["failures"][0]["phase"], "wait")
                self.assertFalse(raised.exception.report["hardware_acknowledged"])
                if operation.endswith(".stop"):
                    self.assertEqual(fake.trace[-1], T(100))
                    self.assertTrue(fake.locals[44][35])

    def test_focal_publication_fault_cannot_be_reported_as_completion(self):
        for operation in FOCAL_EXPECTED:
            fake = FakeLocals()
            def publish(name, bank, snapshot):
                fake.publish(name, bank, snapshot)
                raise RuntimeError("injected DPS publication failure")
            with self.assertRaises(StageExecutionError) as raised:
                fake.execute(operation, focal_helper=fake.helper, publish=publish)
            report = raised.exception.report
            self.assertEqual(report["status"], "PARTIAL_FAILURE")
            self.assertEqual(report["failures"][0]["publication"], "DPS")
            self.assertEqual(report["helper_attempts"][0]["status"], "CALLBACK_COMPLETED")
            self.assertNotIn(FOCAL_EXPECTED[operation][-1][0], report["completed_frames"])
            self.assertEqual(report["pending_output_restorations"], [])

    def test_focal_nested_observer_fault_marks_parent_incomplete(self):
        for operation, nested_uid, parent_uid in (("focales.start", "48404", "40293"),
                                                  ("focales.stop", "57312", "23518")):
            fake = FakeLocals()
            def observe(index, uid):
                fake.observe(index, uid)
                if uid == nested_uid:
                    raise RuntimeError("injected nested observer failure")
            with self.assertRaises(StageExecutionError) as raised:
                fake.execute(operation, focal_helper=fake.helper, frame_observer=observe)
            report = raised.exception.report
            self.assertNotIn(parent_uid, report["completed_frames"])
            self.assertNotIn(nested_uid, report["completed_frames"])
            if operation.endswith(".stop"):
                self.assertEqual(fake.trace[-1], T(100))

    def test_focal_recursive_preflight_rejects_last_nested_effect_and_wrong_helper(self):
        class Plan(object):
            def __init__(self, last):
                self.last = last
            def plan(self, operation, value):
                return [["1", [["write", 15, [[7, True]]]]],
                        ["2", [["subsequence", [["3", [self.last]]]]]]]
        for last in (["write", 15, [[32, False]]], ["wait", -1],
                     ["call_handle_error", "GUESS.vi"],
                     ["call_handle_error", "1_Focales OFF.vi"],
                     ["call_clear_error", "1_Focales ON.vi"]):
            fake = FakeLocals()
            with patch("legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution.load_model",
                       return_value=Plan(last)):
                with self.assertRaises(ValueError):
                    fake.execute("focales.start", focal_helper=fake.helper)
            self.assertEqual(fake.trace + fake.reads, [])

    def test_focal_nested_publication_uses_its_own_entry_snapshot(self):
        fake = FakeLocals()
        original = fake.locals[36]
        class Plan(object):
            def plan(self, operation, value):
                return [["1", [["write", 36, [[0, True]]],
                                ["subsequence", [["2", [["write", 36, [[0, False]]],
                                                         ["publish", [["DPS", 36]]]]]]]]]]
        with patch("legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution.load_model",
                   return_value=Plan()):
            fake.execute("focales.start", focal_helper=fake.helper)
        published = [item for item in fake.trace if item[0] == "publish"][0]
        self.assertTrue(published[3][0])
        self.assertNotEqual(published[3], original)
        self.assertFalse(fake.locals[36][0])

    def test_all_twelve_literal_paths_and_all_source_frames(self):
        self.assertEqual(set(SUPPORTED_OPERATIONS), set(EXPECTED) | set(FOCAL_EXPECTED))
        for operation, frames in EXPECTED.items():
            fake = FakeLocals()
            expected, state = [], copy.deepcopy(fake.locals)
            for index, (uid, effects) in enumerate(frames):
                expected.append(("frame", index, uid))
                entry = copy.deepcopy(state)
                for effect in effects:
                    if effect[0] == "write":
                        _, bank, changes = effect
                        expected.append(effect)
                        if bank == 35:
                            state[bank] = True
                        else:
                            values = list(state[bank])
                            for field, value in changes:
                                values[field] = value
                            state[bank] = tuple(values)
                    elif effect[0] == "publish":
                        expected.append(effect + (entry[effect[2]],))
                    else:
                        expected.append(effect)
            report = fake.execute(operation)
            self.assertEqual(fake.trace, expected, operation)
            self.assertEqual(fake.locals, state, operation)
            self.assertEqual(report["completed_frames"], [uid for uid, effects in frames])
            self.assertEqual(report["status"], "COMPLETED")
            self.assertFalse(report["hardware_acknowledged"])
            self.assertFalse(report["source_frame_effects_ordered"])
            self.assertEqual(report["pending_output_restorations"], [])
            self.assertEqual(report["adapter_schedule"], "writes_then_publish_then_wait")
            self.assertNotIn(35, fake.reads)

    def test_newval_false_has_no_callbacks_for_all_paths(self):
        for operation in EXPECTED:
            fake = FakeLocals()
            result = fake.execute(operation, new_value=False)
            self.assertEqual(result["status"], "NOOP")
            self.assertEqual(fake.trace, [])
            self.assertEqual(fake.reads, [])
            self.assertEqual(fake.locals, fake.before)

    def test_unknown_focal_general_and_ht_ramp_rejected_before_any_callbacks(self):
        for operation in ("unknown", "focales.start", "focales.stop", "general.start",
                          "general.stop", "alimentation_ht.ramp", "ht_voltage_12.7kv"):
            fake = FakeLocals()
            with self.assertRaises(ValueError):
                fake.execute(operation)
            self.assertEqual(fake.trace + fake.reads, [])

    def test_explicit_confirmation_and_boolean_newval_required(self):
        for value in (False, None, 0, 1, "yes"):
            fake = FakeLocals()
            with self.assertRaises(ValueError):
                fake.execute("chauffage.start", operator_confirmed=value)
            self.assertEqual(fake.trace + fake.reads, [])
        for value in (None, 0, 1, "False"):
            fake = FakeLocals()
            with self.assertRaises(ValueError):
                fake.execute("chauffage.start", new_value=value)
            self.assertEqual(fake.trace + fake.reads, [])

    def test_all_callbacks_validated_before_initial_reads(self):
        for name in ("read_local", "write_local", "publish", "wait_seconds",
                     "cancelled", "frame_observer"):
            fake = FakeLocals()
            with self.assertRaises(ValueError):
                fake.execute("chauffage.start", **{name: 42})
            self.assertEqual(fake.trace + fake.reads, [])

    def test_all_initial_banks_preflight_before_any_effects(self):
        for bank in (15, 36, 44):
            for invalid in ([], (), tuple([False] * (BANK_SHAPES[bank] - 1)),
                            tuple([0] * BANK_SHAPES[bank])):
                fake = FakeLocals()
                fake.locals[bank] = invalid
                with self.assertRaises(ValueError):
                    fake.execute("chauffage.start")
                self.assertEqual(fake.trace, [])

    def test_complete_plan_preflight_includes_last_frame_and_rejects_helpers(self):
        class Plan(object):
            def plan(self, operation, value):
                return [["1", [["write", 15, [[3, True]]]]],
                        ["2", [["call_clear_error", "1_Focales OFF.vi"]]]]
        fake = FakeLocals()
        with patch("legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution.load_model",
                   return_value=Plan()):
            with self.assertRaises(ValueError):
                fake.execute("chauffage.start")
        self.assertEqual(fake.trace + fake.reads, [])

    def test_each_frame_rereads_snapshot_and_preserves_unrelated_local_fields(self):
        fake = FakeLocals()
        def observer(index, uid):
            fake.observe(index, uid)
            values = list(fake.locals[15])
            values[31] = bool(index % 2)
            fake.locals[15] = tuple(values)
        fake.execute("chauffage.start", frame_observer=observer)
        self.assertEqual(fake.reads.count(15), 5)  # Baseline plus four DO frames.
        self.assertEqual(fake.reads.count(36), 3)  # Baseline, assignment, publication.
        self.assertEqual(fake.locals[15][31], False)  # Final frame index6.

    def test_publication_uses_independent_frame_entry_snapshot_not_reread(self):
        fake = FakeLocals()
        original = fake.locals[36]
        class SameFramePlan(object):
            def plan(self, operation, value):
                return [["10", [["write", 36, [[0, True]]],
                                  ["publish", [["DPS", 36]]]]]]
        with patch("legacy.xp_acq_agent.elyse_agent.acquisition_stage_execution.load_model",
                   return_value=SameFramePlan()):
            fake.execute("modulator.reset")
        self.assertEqual(fake.trace[-1], ("publish", "DPS", 36, original))
        self.assertTrue(fake.locals[36][0])

    def test_final_separate_publication_normally_sees_previous_frame_assignment(self):
        fake = FakeLocals()
        values = list(fake.locals[36])
        values[4] = True
        fake.locals[36] = tuple(values)
        fake.execute("chauffage.start")
        publication = [item for item in fake.trace if item[0] == "publish"][0]
        self.assertFalse(publication[3][4])

    def test_ht_exact_error_wired_publication_order_and_each_failure_short_circuit(self):
        names = ("DPS", "EPS", "C4_OUT_DIO96")
        banks = (36, 44, 15)
        for operation in ("alimentation_ht.start", "alimentation_ht.stop",
                          "alimentation_ht.reset"):
            for fail_at in range(3):
                fake = FakeLocals()
                def publish(name, bank, snapshot):
                    fake.publish(name, bank, snapshot)
                    if name == names[fail_at]:
                        raise RuntimeError("injected publication failure: " + name)
                with self.assertRaises(StageExecutionError) as raised:
                    fake.execute(operation, publish=publish)
                attempts = [item for item in fake.trace if item[0] == "publish"]
                self.assertEqual([item[1] for item in attempts], list(names[:fail_at + 1]))
                self.assertEqual([item[2] for item in attempts], list(banks[:fail_at + 1]))
                report = raised.exception.report
                self.assertEqual(report["status"], "PARTIAL_FAILURE")
                self.assertFalse(report["hardware_acknowledged"])
                self.assertEqual(report["failures"][0]["publication"], names[fail_at])
                self.assertEqual(report["failures"][0]["bank"], banks[fail_at])
                self.assertNotIn(EXPECTED[operation][3][0], report["completed_frames"])
                if operation.endswith(".stop"):
                    # Explicit Python best-effort policy attempts later wait;
                    # it does not bypass the source publication error chain.
                    self.assertEqual(fake.trace[-1], T(100))
                else:
                    self.assertNotIn(("frame", 4, EXPECTED[operation][4][0]), fake.trace)

    def test_ht_cancel_between_each_publication_prevents_remaining_effects(self):
        names = ("DPS", "EPS", "C4_OUT_DIO96")
        for operation in ("alimentation_ht.start", "alimentation_ht.stop",
                          "alimentation_ht.reset"):
            for cancel_at in range(3):
                fake = FakeLocals()
                def publish(name, bank, snapshot):
                    fake.publish(name, bank, snapshot)
                    if name == names[cancel_at]:
                        fake.cancel = True
                with self.assertRaises(StageExecutionCancelled) as raised:
                    fake.execute(operation, publish=publish)
                attempts = [item for item in fake.trace if item[0] == "publish"]
                self.assertEqual([item[1] for item in attempts], list(names[:cancel_at + 1]))
                self.assertEqual(raised.exception.report["pending_output_restorations"], [])
                self.assertEqual(raised.exception.report["status"], "CANCELLED")
                self.assertNotIn(("frame", 4, EXPECTED[operation][4][0]), fake.trace)

    def test_ht_reset_preserves_entire_eps_and_has_no_analog_counter_or_ramp_effect(self):
        for operation in ("alimentation_ht.start", "alimentation_ht.stop",
                          "alimentation_ht.reset"):
            fake = FakeLocals()
            fake.execute(operation)
            writes = [item for item in fake.trace if item[0] == "write"]
            self.assertTrue(set(item[1] for item in writes).issubset({15, 35, 36, 44}))
            self.assertEqual([item[1] for item in fake.trace if item[0] == "wait"],
                             [0.15, 0.1])
            if operation.endswith(".reset"):
                self.assertEqual(fake.locals[44], fake.before[44])
                self.assertFalse(any(item[1] == 44 for item in writes))
                self.assertEqual([item[2] for item in writes if item[1] == 36],
                                 [((16, False),)])

    def test_ht_reset_preflights_eps_for_publication_despite_no_eps_write(self):
        fake = FakeLocals()
        fake.locals[44] = None
        with self.assertRaises(ValueError):
            fake.execute("alimentation_ht.reset")
        self.assertEqual(fake.trace, [])

    def test_ht_publications_share_selected_frame_entry_reads_not_live_mutations(self):
        fake = FakeLocals()
        entry = {}
        def observer(index, uid):
            fake.observe(index, uid)
            if index == 3:
                entry.update({bank: fake.locals[bank] for bank in (15, 36, 44)})
        def publish(name, bank, snapshot):
            fake.publish(name, bank, snapshot)
            # Inter-callback mutation must not turn the next publication into
            # a post-write read. This is the documented adapter schedule, not
            # an assertion of source-wide atomic snapshots.
            for target in (15, 36, 44):
                fake.locals[target] = tuple(not value for value in fake.locals[target])
        fake.execute("alimentation_ht.start", frame_observer=observer, publish=publish)
        attempts = [item for item in fake.trace if item[0] == "publish"]
        self.assertEqual(len(attempts), 3)
        for kind, name, bank, snapshot in attempts:
            self.assertEqual(snapshot, entry[bank])

    def test_no_invented_input_gate_eps_or_ni_ack(self):
        fake = FakeLocals()
        fake.locals[44] = tuple([False] * 77)
        report = fake.execute("chauffage.start")
        self.assertEqual(report["status"], "COMPLETED")
        self.assertTrue(fake.locals[44][14])  # Literal completion, not input permit.
        self.assertFalse(report["hardware_acknowledged"])
        self.assertEqual(set(fake.reads), {15, 36, 44})

    def test_every_write_failure_is_visible_and_not_success(self):
        for operation, frames in EXPECTED.items():
            writes = [effect for uid, effects in frames for effect in effects
                      if effect[0] == "write"]
            for number, effect in enumerate(writes, 1):
                fake = FakeLocals()
                fake.fail_write = number
                with self.assertRaises(StageExecutionError) as raised:
                    fake.execute(operation)
                report = raised.exception.report
                self.assertEqual(report["status"], "PARTIAL_FAILURE", (operation, number))
                self.assertFalse(report["hardware_acknowledged"])
                self.assertTrue(any(item["phase"] == "write" for item in report["failures"]))
                if operation.endswith(".stop"):
                    # Source software intent is retained, never presented as
                    # an acknowledged shutdown after a callback failure.
                    self.assertTrue(any(item[0] == "publish" for item in fake.trace))
                    self.assertEqual(fake.trace[-1], T(100))
                else:
                    self.assertFalse(any(item[0] == "publish" for item in fake.trace))

    def test_every_failed_output_attempt_restores_before_later_effects(self):
        for operation, frames in EXPECTED.items():
            writes = [effect for uid, effects in frames for effect in effects
                      if effect[0] == "write"]
            for number, effect in enumerate(writes, 1):
                if effect[1] not in (15, 17):
                    continue
                fake = FakeLocals()
                fake.fail_write = number
                with self.assertRaises(StageExecutionError):
                    fake.execute(operation)
                index = [i for i, item in enumerate(fake.trace) if item[0] == "write"][number - 1]
                expected = tuple((field, fake.before[effect[1]][field])
                                 for field, value in effect[2])
                self.assertEqual(fake.trace[index + 1], ("write", effect[1], expected),
                                 (operation, number))

    def test_stops_collect_multiple_failures_and_attempt_every_source_frame(self):
        for operation in EXPECTED:
            if not operation.endswith(".stop"):
                continue
            fake = FakeLocals()
            fake.fail_all_outputs = True
            with self.assertRaises(StageExecutionError) as raised:
                fake.execute(operation)
            report = raised.exception.report
            self.assertGreaterEqual(len(report["failures"]), 2)
            self.assertTrue(report["restoration_failures"])
            observed = [item[2] for item in fake.trace if item[0] == "frame"]
            self.assertEqual(observed, [uid for uid, effects in EXPECTED[operation]])

    def test_final_pending_empty_after_failed_restore_then_successful_source_release(self):
        fake = FakeLocals()
        def write(bank, changes):
            fake.write(bank, changes)
            if fake.write_count in (1, 2):
                raise RuntimeError("first write and immediate restore both failed")
        with self.assertRaises(StageExecutionError) as raised:
            fake.execute("chauffage.stop", write_local=write)
        report = raised.exception.report
        self.assertTrue(report["restoration_failures"])
        self.assertEqual(report["pending_output_restorations"], [])
        self.assertTrue(fake.locals[15][4])

    def test_all_failed_restores_expose_exact_final_preprocedure_baselines(self):
        fake = FakeLocals()
        fake.fail_all_outputs = True
        with self.assertRaises(StageExecutionError) as raised:
            fake.execute("cooling.stop")
        self.assertEqual(raised.exception.report["pending_output_restorations"],
                         [(17, 1, fake.before[17][1]), (17, 4, fake.before[17][4])])
        self.assertTrue(raised.exception.report["restoration_failures"])

    def test_cancel_before_start_has_no_output_and_never_deinitializes(self):
        fake = FakeLocals()
        fake.cancel = True
        with self.assertRaises(StageExecutionCancelled) as raised:
            fake.execute("chauffage.start")
        self.assertEqual(raised.exception.report["status"], "CANCELLED")
        self.assertEqual(fake.trace, [])

    def test_cancel_during_every_output_pulse_restores_command_baseline(self):
        for operation in EXPECTED:
            fake = FakeLocals()
            first = next(effect for uid, effects in EXPECTED[operation]
                         for effect in effects if effect[0] == "write" and effect[1] in (15, 17))
            def write(bank, changes):
                fake.write(bank, changes)
                if bank == first[1] and changes == first[2]:
                    fake.cancel = True
            with self.assertRaises(StageExecutionCancelled) as raised:
                fake.execute(operation, write_local=write)
            report = raised.exception.report
            self.assertEqual(report["status"], "CANCELLED")
            self.assertEqual(fake.locals[first[1]], fake.before[first[1]])
            self.assertFalse(any(item[0] == "publish" for item in fake.trace))
            self.assertTrue(report["restored_fields"])

    def test_cancel_during_wait_restores_inflight_output(self):
        fake = FakeLocals()
        def wait(seconds):
            fake.wait(seconds)
            fake.cancel = True
        with self.assertRaises(StageExecutionCancelled):
            fake.execute("chauffage.start", wait_seconds=wait)
        self.assertEqual(fake.locals[15], fake.before[15])

    def test_cancel_at_every_output_write_boundary_never_reports_success(self):
        for operation, frames in EXPECTED.items():
            writes = [effect for uid, effects in frames for effect in effects
                      if effect[0] == "write"]
            for target, effect in enumerate(writes, 1):
                if effect[1] not in (15, 17):
                    continue
                fake = FakeLocals()
                def write(bank, changes):
                    fake.write(bank, changes)
                    if fake.write_count == target:
                        fake.cancel = True
                with self.assertRaises(StageExecutionCancelled) as raised:
                    fake.execute(operation, write_local=write)
                report = raised.exception.report
                self.assertEqual(report["status"], "CANCELLED", (operation, target))
                self.assertFalse(report["hardware_acknowledged"])
                self.assertFalse(any(item[0] == "publish" for item in fake.trace))
                # A successfully completed last source write is not rolled
                # back. Earlier writes leave a pulse in flight and restore.
                field = effect[2][0][0]
                later = any(item[1] == effect[1] and any(i == field for i, v in item[2])
                            for item in writes[target:])
                expected = fake.before[effect[1]][field] if later else effect[2][0][1]
                self.assertIs(fake.locals[effect[1]][field], expected)

    def test_cancel_at_every_wait_boundary_never_reports_success(self):
        for operation, frames in EXPECTED.items():
            waits = [effect for uid, effects in frames for effect in effects
                     if effect[0] == "wait"]
            for target in range(1, len(waits) + 1):
                fake = FakeLocals()
                count = [0]
                def wait(seconds):
                    fake.wait(seconds)
                    count[0] += 1
                    if count[0] == target:
                        fake.cancel = True
                with self.assertRaises(StageExecutionCancelled) as raised:
                    fake.execute(operation, wait_seconds=wait)
                self.assertEqual(raised.exception.report["status"], "CANCELLED")

    def test_cancel_restore_failure_cannot_be_hidden(self):
        fake = FakeLocals()
        def write(bank, changes):
            fake.write(bank, changes)
            if bank == 15:
                fake.cancel = True
                if len([x for x in fake.trace if x[0] == "write" and x[1] == 15]) > 1:
                    raise RuntimeError("restore failed")
        with self.assertRaises(StageExecutionCancelled) as raised:
            fake.execute("chauffage.start", write_local=write)
        self.assertTrue(raised.exception.report["restoration_failures"])
        self.assertEqual(raised.exception.report["pending_output_restorations"],
                         [(15, 3, fake.before[15][3])])

    def test_fault_after_completed_pulse_does_not_invent_output_rollback(self):
        fake = FakeLocals()
        def wait(seconds):
            fake.wait(seconds)
            if seconds == 3:
                raise RuntimeError("later frame failure")
        with self.assertRaises(StageExecutionError) as raised:
            fake.execute("chauffage.start", wait_seconds=wait)
        output = [item for item in fake.trace if item[0] == "write" and item[1] == 15]
        self.assertEqual(output, [W(15, (3, True)), W(15, (3, False))])
        self.assertEqual(raised.exception.report["restored_fields"], [])

    def test_observer_read_publish_wait_and_cancel_callback_faults_visible(self):
        for name in ("frame_observer", "publish", "wait_seconds", "cancelled"):
            fake = FakeLocals()
            def fail(*args):
                raise RuntimeError("injected " + name)
            with self.assertRaises(StageExecutionError) as raised:
                fake.execute("chauffage.start", **{name: fail})
            self.assertEqual(raised.exception.report["status"], "PARTIAL_FAILURE")
        fake = FakeLocals()
        def read(bank):
            if fake.trace:
                raise RuntimeError("frame local read failed")
            return fake.read(bank)
        with self.assertRaises(StageExecutionError) as raised:
            fake.execute("chauffage.start", read_local=read)
        self.assertEqual(raised.exception.report["failures"][0]["phase"], "read")

    def test_invalid_cancellation_result_rejected_without_output(self):
        for value in (None, 0, 1, "False"):
            fake = FakeLocals()
            with self.assertRaises(StageExecutionError) as raised:
                fake.execute("chauffage.start", cancelled=lambda: value)
            self.assertEqual(raised.exception.report["status"], "PARTIAL_FAILURE")
            self.assertEqual(fake.trace, [])


if __name__ == "__main__":
    unittest.main()
