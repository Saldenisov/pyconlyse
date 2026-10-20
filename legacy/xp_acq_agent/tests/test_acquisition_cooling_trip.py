"""Fake-only cooling executor contract tests; no socket/NI imports or calls."""
import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from elyse_agent.acquisition_cooling_trip import (
    CoolingTripCancelled, CoolingTripError, DPS_URI, FRAME_UIDS,
    cooling_trip_predicate, execute_cooling_trip,
)


def cluster(size, changes=()):
    values = [False] * size
    for index, value in changes:
        values[index] = value
    return tuple(values)


class FakeOwner(object):
    def __init__(self):
        self.values = {17: cluster(40, ((1, True), (4, True), (13, True))),
                       35: None, 36: cluster(29, ((1, True),)),
                       44: cluster(77, ((2, True), (3, True), (14, True), (20, True), (32, True)))}
        self.trace = []
        self.cancel = False
        self.frame = None
        self.fail_frame = None
        self.cancel_frame = None
        self.fail_kind = None
        self.fail_seen = False
        self.effect_index = 0
        self.fail_effect_index = None
        self.cancel_kind = None
        self.cancel_seen = False
        self.cancel_effect_index = None
        self.cleanup_failures = set()
        self.mutate_frame = None

    def effect(self, kind, detail):
        self.trace.append((kind,) + detail)
        self.effect_index += 1
        if ((self.fail_kind == kind or self.effect_index == self.fail_effect_index)
                and not self.fail_seen):
            self.fail_seen = True
            raise RuntimeError("injected " + kind)
        if ((self.cancel_kind == kind or self.effect_index == self.cancel_effect_index)
                and not self.cancel_seen):
            self.cancel_seen = True
            self.cancel = True

    def read(self, bank):
        if self.fail_seen and "read" in self.cleanup_failures:
            raise RuntimeError("restore read failed")
        self.effect("read", (bank,))
        return self.values[bank]

    def write(self, bank, changes):
        # Apply first, then potentially fail: partial NI write outcome unknown.
        if self.fail_seen and "write" in self.cleanup_failures:
            raise RuntimeError("restore write failed")
        if bank == 35:
            self.values[bank] = changes[0][1]
        else:
            after = list(self.values[bank])
            for index, value in changes:
                after[index] = value
            self.values[bank] = tuple(after)
        self.effect("write", (bank, changes))

    def publish(self, name, bank, snapshot):
        self.effect("publish", (name, bank, snapshot))

    def wait(self, seconds):
        self.effect("wait", (seconds,))

    def cancelled(self):
        return self.cancel

    def observe(self, index, uid):
        self.frame = index
        self.trace.append(("frame", index, uid))
        if index == self.fail_frame:
            self.fail_seen = True
            raise RuntimeError("frame observer failed")
        if index == self.cancel_frame:
            self.cancel = True
        if index == self.mutate_frame:
            self.values[36] = cluster(29, ((7, True), (28, True)))

    def run(self, enabled=True, c4=None, c3=None, **overrides):
        kwargs = dict(c4_snapshot=c4 if c4 is not None else cluster(64, ((19, True),)),
                      c3_snapshot=c3 if c3 is not None else cluster(56),
                      read_local=self.read, write_local=self.write,
                      publish=self.publish, wait_seconds=self.wait,
                      cancelled=self.cancelled, frame_observer=self.observe,
                      enabled_arm=enabled)
        kwargs.update(overrides)
        return execute_cooling_trip(**kwargs)


class CoolingTripTests(unittest.TestCase):
    def test_exhaustive_raw_four_boolean_expression(self):
        for a, b, c, d in itertools.product((False, True), repeat=4):
            self.assertEqual((a or b) and (not c or not d), cooling_trip_predicate(
                cluster(64, ((19, a), (38, b))), cluster(56, ((0, c), (6, d)))))

    def test_irrelevant_raw_bits_are_not_stage_permissions(self):
        c4 = tuple(True for _ in range(64))
        self.assertTrue(cooling_trip_predicate(c4, cluster(56)))
        self.assertFalse(cooling_trip_predicate(c4, tuple(True for _ in range(56))))

    def test_default_disabled_gate_is_distinct_from_raw_false(self):
        owner = FakeOwner()
        result = execute_cooling_trip(cluster(64, ((19, True),)), cluster(56),
            owner.read, owner.write, owner.publish, owner.wait, owner.cancelled,
            frame_observer=owner.observe)
        self.assertEqual("disabled", result["status"])
        self.assertTrue(result["raw_predicate"])
        self.assertFalse(result["callback_execution"])
        self.assertEqual([], owner.trace)
        result = owner.run(c4=cluster(64))
        self.assertEqual("false_arm", result["status"])
        self.assertFalse(result["raw_predicate"])
        self.assertEqual([], owner.trace)

    def test_all_arguments_preflight_before_any_callback(self):
        invalid = [dict(enabled_arm=1), dict(enabled_arm=None), dict(c4_snapshot=[False] * 64),
                   dict(c4_snapshot=cluster(63)), dict(c3_snapshot=cluster(55)),
                   dict(c4_snapshot=tuple(0 for _ in range(64))),
                   dict(c3_snapshot=tuple(0 for _ in range(56))),
                   dict(frame_observer=1)]
        for name in ("read_local", "write_local", "publish", "wait_seconds", "cancelled"):
            invalid.append({name: None})
        for changes in invalid:
            owner = FakeOwner()
            with self.assertRaises(TypeError):
                owner.run(enabled=False, **changes)
            self.assertEqual([], owner.trace)

    def test_exact_frame_trace_and_no_klystron_stop_writes(self):
        owner = FakeOwner()
        result = owner.run()
        dps = cluster(29)
        self.assertEqual([
            ("frame", 0, "10221"), ("read", 17), ("write", 17, ((1, False),)),
            ("write", 35, ((-1, True),)), ("wait", 0.15),
            ("frame", 1, "13119"), ("read", 17), ("write", 17, ((1, True),)),
            ("frame", 2, "14187"), ("wait", 0.4),
            ("frame", 3, "20056"), ("read", 17), ("write", 17, ((4, False),)), ("wait", 0.15),
            ("frame", 4, "30644"), ("read", 17), ("write", 17, ((4, True),)),
            ("frame", 5, "31857"), ("read", 44), ("read", 36),
            ("write", 44, ((1, True), (2, False), (3, False), (5, True))),
            ("write", 36, ((1, False),)),
            ("frame", 6, "39347"), ("read", 36), ("publish", "DPS", 36, dps), ("wait", 0.1),
        ], owner.trace)
        self.assertTrue(result["completed"])
        self.assertFalse(result["hardware_acknowledged"])
        self.assertEqual(list(FRAME_UIDS), result["completed_frame_uids"])
        self.assertEqual([], result["remaining_frame_uids"])
        self.assertEqual(DPS_URI, result["source_intent"]["publication_uri"])
        self.assertTrue(owner.values[35])
        self.assertTrue(owner.values[44][14])
        self.assertTrue(owner.values[44][20])
        self.assertTrue(owner.values[44][32])
        self.assertTrue(owner.values[17][13])
        self.assertEqual({17, 35, 36, 44}, set(item[1] for item in owner.trace if item[0] == "write"))

    def test_publication_uses_fresh_frame_six_read_not_frame_five_cache(self):
        owner = FakeOwner()
        owner.mutate_frame = 6
        result = owner.run()
        published = [item for item in owner.trace if item[0] == "publish"][0]
        self.assertEqual(cluster(29, ((7, True), (28, True))), published[3])
        reads = [entry for entry in result["local_reads"] if entry[2] == 36]
        self.assertNotEqual(reads[0][3], reads[1][3])
        self.assertEqual("39313", reads[0][1])
        self.assertEqual("39444", reads[1][1])

    def test_no_latch_or_automatic_restart_is_added(self):
        owner = FakeOwner()
        owner.run()
        owner.trace = []
        owner.run()
        self.assertEqual(4, len([item for item in owner.trace if item[0] == "write" and item[1] == 17]))
        owner.trace = []
        owner.run(c4=cluster(64))
        self.assertEqual([], owner.trace)

    def test_failure_at_every_frame_is_reported_without_later_frames(self):
        for index in range(7):
            owner = FakeOwner()
            owner.fail_frame = index
            with self.assertRaises(CoolingTripError) as raised:
                owner.run()
            report = raised.exception.result
            self.assertEqual("failed", report["status"])
            self.assertEqual(index, report["failure"]["frame_index"])
            self.assertEqual(list(FRAME_UIDS[:index]), report["completed_frame_uids"])
            self.assertEqual(list(FRAME_UIDS[index:]), report["remaining_frame_uids"])
            self.assertFalse(report["completed"])
            self.assertFalse(report["hardware_acknowledged"])
            self.assertEqual([], report["pending_output_restorations"])
            self.assertTrue(owner.values[17][1])
            self.assertTrue(owner.values[17][4])

    def test_cancellation_at_every_frame_restores_pending_output(self):
        for index in range(7):
            owner = FakeOwner()
            owner.cancel_frame = index
            with self.assertRaises(CoolingTripCancelled) as raised:
                owner.run()
            report = raised.exception.result
            self.assertEqual("cancelled", report["status"])
            self.assertEqual(list(FRAME_UIDS[:index]), report["completed_frame_uids"])
            self.assertEqual([], report["pending_output_restorations"])
            self.assertTrue(owner.values[17][1])
            self.assertTrue(owner.values[17][4])

    def test_failure_after_every_callback_retains_partial_outcome(self):
        complete = FakeOwner()
        complete.run()
        self.assertEqual(19, complete.effect_index)
        for index in range(1, complete.effect_index + 1):
            owner = FakeOwner()
            owner.fail_effect_index = index
            with self.assertRaises(CoolingTripError) as raised:
                owner.run()
            report = raised.exception.result
            self.assertEqual("failed", report["status"])
            self.assertFalse(report["completed"])
            self.assertFalse(report["hardware_acknowledged"])
            self.assertEqual([], report["cleanup_failures"])
            self.assertEqual([], report["pending_output_restorations"])
            self.assertTrue(owner.values[17][1])
            self.assertTrue(owner.values[17][4])

    def test_cancellation_after_every_callback_restores_partial_output(self):
        for index in range(1, 20):
            owner = FakeOwner()
            owner.cancel_effect_index = index
            with self.assertRaises(CoolingTripCancelled) as raised:
                owner.run()
            report = raised.exception.result
            self.assertEqual("cancelled", report["status"])
            self.assertFalse(report["completed"])
            self.assertEqual([], report["pending_output_restorations"])
            self.assertTrue(owner.values[17][1])
            self.assertTrue(owner.values[17][4])

    def test_separate_output_reads_preserve_intervening_local_updates(self):
        owner = FakeOwner()

        def observe(index, uid):
            owner.observe(index, uid)
            if index == 1:
                values = list(owner.values[17])
                values[22] = True
                owner.values[17] = tuple(values)
            if index == 4:
                values = list(owner.values[17])
                values[24] = True
                owner.values[17] = tuple(values)

        result = owner.run(frame_observer=observe)
        reads = dict((entry[1], entry[3]) for entry in result["local_reads"] if entry[2] == 17)
        self.assertFalse(reads["10431"][22])
        self.assertTrue(reads["13466"][22])
        self.assertFalse(reads["22661"][24])
        self.assertTrue(reads["30986"][24])
        self.assertTrue(owner.values[17][22])
        self.assertTrue(owner.values[17][24])

    def test_partial_write_and_wait_failure_restore_prior_baseline(self):
        for kind in ("write", "wait"):
            owner = FakeOwner()
            owner.fail_kind = kind
            with self.assertRaises(CoolingTripError) as raised:
                owner.run()
            report = raised.exception.result
            self.assertEqual(1, len(report["restoration_attempts"]))
            self.assertTrue(report["restoration_attempts"][0]["write_succeeded"])
            self.assertTrue(owner.values[17][1])
            self.assertTrue(owner.values[17][13])
            self.assertEqual([], report["cleanup_failures"])

    def test_cancellation_immediately_after_assertion_still_restores(self):
        owner = FakeOwner()
        owner.cancel_kind = "write"
        with self.assertRaises(CoolingTripCancelled) as raised:
            owner.run()
        self.assertTrue(owner.values[17][1])
        self.assertEqual([], raised.exception.result["pending_output_restorations"])

    def test_restore_uses_actual_prior_low_baseline_not_assumed_high(self):
        owner = FakeOwner()
        owner.values[17] = cluster(40, ((13, True),))
        owner.fail_kind = "wait"
        with self.assertRaises(CoolingTripError) as raised:
            owner.run()
        self.assertFalse(owner.values[17][1])
        self.assertFalse(raised.exception.result["restoration_attempts"][0]["baseline"])

    def test_original_error_and_all_cleanup_failures_retained(self):
        owner = FakeOwner()
        owner.fail_kind = "write"
        owner.cleanup_failures = {"read", "write"}
        with self.assertRaises(CoolingTripError) as raised:
            owner.run()
        report = raised.exception.result
        self.assertIn("injected write", report["failure"]["error"])
        self.assertEqual(["restore_read", "restore_write"],
                         [item["operation"] for item in report["cleanup_failures"]])
        self.assertEqual([(1, True)], report["pending_output_restorations"])
        self.assertFalse(report["completed"])

    def test_read_restore_failure_does_not_skip_known_field_patch(self):
        owner = FakeOwner()
        owner.fail_kind = "write"
        owner.cleanup_failures = {"read"}
        with self.assertRaises(CoolingTripError) as raised:
            owner.run()
        report = raised.exception.result
        self.assertTrue(owner.values[17][1])
        self.assertEqual([], report["pending_output_restorations"])
        self.assertEqual("restore_read", report["cleanup_failures"][0]["operation"])

    def test_bad_runtime_local_shape_prevents_first_mutation(self):
        owner = FakeOwner()
        owner.values[17] = cluster(39)
        with self.assertRaises(CoolingTripError) as raised:
            owner.run()
        self.assertEqual([], [item for item in owner.trace if item[0] == "write"])
        self.assertIn("TypeError", raised.exception.result["failure"]["error"])

    def test_cancelled_callback_requires_bool(self):
        owner = FakeOwner()
        with self.assertRaises(CoolingTripError) as raised:
            owner.run(cancelled=lambda: 1)
        self.assertEqual([], owner.trace)
        self.assertIn("TypeError", raised.exception.result["failure"]["error"])

    def test_publication_failure_is_not_success_and_does_not_replay_outputs(self):
        owner = FakeOwner()
        owner.fail_kind = "publish"
        with self.assertRaises(CoolingTripError) as raised:
            owner.run()
        report = raised.exception.result
        self.assertEqual(list(FRAME_UIDS[:6]), report["completed_frame_uids"])
        self.assertEqual([FRAME_UIDS[6]], report["remaining_frame_uids"])
        self.assertEqual([], report["restoration_attempts"])
        self.assertEqual([], report["pending_output_restorations"])
        self.assertTrue(owner.values[44][1])
        self.assertFalse(owner.values[36][1])
        self.assertEqual([], [item for item in owner.trace if item == ("wait", 0.1)])


if __name__ == "__main__":
    unittest.main()
