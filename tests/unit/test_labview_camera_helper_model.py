"""Offline source-graph, model and scalar-width checks. No native execution."""

import copy
import json
import os
import tempfile
import unittest

from tools.labview_camera_helper_model import (
    EMPTY_GATE as EMPTY,
)
from tools.labview_camera_helper_model import (
    MASK32,
    EpochSnapshot,
    SetupSnapshot,
    audit_epoch,
    audit_setup,
    decode_scalar,
    epoch_transition,
    read_setup_snapshot,
    read_snapshot,
)
from tools.labview_camera_helper_model import (
    frame_observe as observe,
)


class FrameWorkBudget(unittest.TestCase):
    def call(self, state, tick, frame=1, **kwargs):
        values = dict(
            run=100,
            capture=101,
            valid=True,
            grab_error=False,
            frame=frame,
            gate_tick=tick,
            observed=102,
        )
        values.update(kwargs)
        return observe(state, **values)

    def test_first_frame_zero_and_exact_one_second_boundary(self):
        state, attempted = self.call(EMPTY, 0, frame=0)
        self.assertTrue(attempted)
        same, attempted = self.call(state, 999, frame=1)
        self.assertFalse(attempted)
        self.assertEqual(same, state)
        state, attempted = self.call(state, 1000, frame=1)
        self.assertTrue(attempted)
        self.assertEqual(state[2:4], (1000, 1))

    def test_repeated_frame_cannot_refresh_after_arbitrary_time(self):
        state, _ = self.call(EMPTY, 10, frame=42)
        for tick in (1009, 1010, 5000, 100000):
            result, attempted = self.call(state, tick, frame=42)
            self.assertFalse(attempted)
            self.assertEqual(result, state)
        self.assertTrue(self.call(state, 1010, frame=43)[1])

    def test_capture_resets_frame_identity_but_preserves_copy_budget(self):
        state, _ = self.call(EMPTY, 500, frame=0)
        result, attempted = self.call(state, 1499, frame=0, capture=102)
        self.assertFalse(attempted)
        self.assertEqual(result, state)
        result, attempted = self.call(state, 1500, frame=0, capture=102)
        self.assertTrue(attempted)
        self.assertEqual(result[:2], (100, 102))

    def test_new_run_resets_rate_and_frame_logically(self):
        state, _ = self.call(EMPTY, 500, frame=7)
        result, attempted = self.call(
            state, 501, frame=7, run=200, capture=201, observed=202
        )
        self.assertTrue(attempted)
        self.assertEqual(result[:2], (200, 201))

    def test_unsigned_tick_wrap_at999_and1000ms(self):
        state, _ = self.call(EMPTY, MASK32 - 499, frame=1)
        self.assertFalse(self.call(state, 499, frame=2)[1])
        self.assertTrue(self.call(state, 500, frame=2)[1])

    def test_actual_precopy_tick_controls_next_deadline(self):
        state, _ = self.call(EMPTY, 0, frame=1, pre_copy_tick=11)
        for tick in (1000, 1010):
            self.assertFalse(self.call(state, tick, frame=2)[1])
        state, attempted = self.call(state, 1011, frame=2, pre_copy_tick=1012)
        self.assertTrue(attempted)
        self.assertEqual(state[2], 1012)

    def test_private_copy_and_queue_errors_consume_budget(self):
        for copy_error, queue_error in ((True, False), (False, True), (True, True)):
            state, attempted = self.call(
                EMPTY, 100, frame=3, copy_error=copy_error, queue_error=queue_error
            )
            self.assertTrue(attempted)
            self.assertFalse(self.call(state, 1099, frame=4)[1])
            self.assertFalse(self.call(state, 1100, frame=3)[1])
            self.assertTrue(self.call(state, 1100, frame=4)[1])

    def test_business_error_invalid_epoch_and_clock_skips_preserve_budget(self):
        state, _ = self.call(EMPTY, 0, frame=0)
        for override in (
            dict(grab_error=True),
            dict(valid=False),
            dict(run=0),
            dict(run=102, capture=101),
            dict(observed=100),
            dict(channel=1 << 32),
        ):
            result, attempted = self.call(state, 2000, frame=1, **override)
            self.assertFalse(attempted)
            self.assertEqual(result, state)
        self.assertTrue(self.call(state, 2000, frame=1)[1])

    def test_channel_preserves_entire_u32_domain(self):
        for channel in (0, 3, 4, 65535, MASK32):
            self.assertTrue(self.call(EMPTY, 0, channel=channel)[1])

    def test_high_rate_calls_bound_total_owned_copy_attempts(self):
        state, attempts = EMPTY, []
        for tick in range(10001):
            state, attempted = self.call(
                state, tick, frame=tick, copy_error=True, queue_error=True
            )
            if attempted:
                attempts.append(tick)
        self.assertEqual(attempts, list(range(0, 10001, 1000)))
        self.assertTrue(all(b - a >= 1000 for a, b in zip(attempts, attempts[1:])))


SNAPSHOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "legacy",
        "labview",
        "supervision_telemetry",
        "individual_helpers",
        "epoch_native2020_semantic_snapshot.json",
    )
)


class NativeSourceSnapshotTests(unittest.TestCase):
    def test_actual_native_saved_source_graph3840cases(self):
        report = audit_epoch(read_snapshot(SNAPSHOT))
        self.assertEqual(report["offline_native_source_graph_cases"], 3840)
        self.assertFalse(report["native_vi_execution_proven"])
        self.assertFalse(report["hardware_executed"])

    def test_matching_failed_setup_clears_previous_valid_state(self):
        graph = read_snapshot(SNAPSHOT)
        committed, reply, clocks = graph.invoke(
            (100, 101, 2, True), 1, 100, 0, False, 200
        )
        self.assertEqual(committed, (100, 101, 2, False))
        self.assertEqual(reply, (101, 2, False))
        self.assertEqual(clocks, [])

    def test_stale_end_cannot_invalidate_newer_run(self):
        state = (200, 202, MASK32, True)
        result, reply = epoch_transition(state, 3, 100)
        self.assertEqual(result, state)
        self.assertFalse(reply[2])

    def test_snapshot_payload_tampering_is_refused(self):
        with open(SNAPSHOT, "rb") as stream:
            raw = stream.read()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "forged.json")
            data = json.loads(raw.decode("utf-8"))
            data["provenance"]["native_vi_sha256"] = "0" * 64
            with open(path, "w", encoding="utf-8") as stream:
                json.dump(data, stream)
            with self.assertRaises(ValueError):
                read_snapshot(path)

    def test_restoring_bad_setup_action_is_detected_by_semantic_audit(self):
        snapshot = read_snapshot(SNAPSHOT)
        changed = copy.deepcopy(snapshot.graph)
        target = next(
            v
            for v in changed["constants"].values()
            if v["width"] == 4 and v["data"] == "00000001"
        )
        target["data"] = "00000000"
        with self.assertRaises(ValueError):
            audit_epoch(EpochSnapshot(changed))


class NativeSetupSnapshotTests(unittest.TestCase):
    def snapshot(self):
        return read_setup_snapshot(
            os.path.join(
                os.path.dirname(SNAPSHOT), "setup_native2020_semantic_snapshot.json"
            )
        )

    def test_actual_UI_authored_wrapper48cases(self):
        report = audit_setup(self.snapshot())
        self.assertEqual(report["offline_native_wrapper_wiring_cases"], 48)
        self.assertTrue(report["Epoch_reply_is_stubbed"])
        self.assertFalse(report["native_vi_execution_proven"])

    def test_old_action_widget_cannot_substitute_for_actual_channel(self):
        graph = copy.deepcopy(self.snapshot().graph)
        target = graph["call_ports"]["9"]
        wire = next(w for w in graph["wires"] if target in w[1:])
        wire[0] = graph["ports"]["action"]
        with self.assertRaises(ValueError):
            audit_setup(SetupSnapshot(graph))


class NativeScalarWidthTests(unittest.TestCase):
    def test_genuine_u32_values_use_first_four_bytes(self):
        for value in (0, 1, 2, 3, 1000, MASK32):
            raw = value.to_bytes(4, "big")
            self.assertEqual(decode_scalar(raw, 4), value)
            self.assertEqual(decode_scalar(raw + b"\0", 4), value)

    def test_zero_prefix_cannot_hide_data_after_scalar(self):
        for value in (1, 2, 3):
            malformed = b"\0" + value.to_bytes(4, "big")
            with self.assertRaises(ValueError):
                decode_scalar(malformed, 4)

    def test_boolean_timestamp_native_zero_padding_and_wrong_lengths(self):
        self.assertEqual(decode_scalar(b"\0\0", 1), 0)
        self.assertEqual(decode_scalar(b"\0" * 17, 16), 0)
        for raw, width in ((b"", 4), (b"\0" * 6, 4), (b"\0", 2)):
            with self.assertRaises(ValueError):
                decode_scalar(raw, width)


if __name__ == "__main__":
    unittest.main()
