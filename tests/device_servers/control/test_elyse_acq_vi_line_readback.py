"""Explicit per-frame snapshots preserve readback copies and concurrent limits."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.line_readback import (
    FRAMES,
    copy_readback_frame,
)


class LineReadbackGoldenTests(unittest.TestCase):
    def test_all_58_field_copies_preserve_untargeted_fields(self):
        self.assertEqual(sum(len(f.pairs) for f in FRAMES), 58)
        source = tuple(range(64))
        target = tuple(f"untouched-{i}" for i in range(132))
        for frame in FRAMES:
            updated = copy_readback_frame(
                frame.frame_index, source_snapshot=source, target_snapshot=target
            )
            expected = dict((dst, source[src]) for src, dst in frame.pairs)
            for index, value in enumerate(updated):
                self.assertEqual(value, expected.get(index, target[index]))
            self.assertEqual(target[0], "untouched-0")

    def test_boolean_readback_is_not_inverted_or_converted_to_request(self):
        source = tuple(i % 2 == 0 for i in range(64))
        for frame in FRAMES[:2]:
            updated = copy_readback_frame(
                frame.frame_index,
                source_snapshot=source,
                target_snapshot=(False,) * 132,
            )
            for src, dst in frame.pairs:
                self.assertIs(updated[dst], source[src])

    def test_deviated_current_fields_91_and_103_share_source_34(self):
        source = tuple(float(i) for i in range(64))
        updated = copy_readback_frame(
            5, source_snapshot=source, target_snapshot=(0.0,) * 132
        )
        self.assertEqual((updated[91], updated[103]), (34.0, 34.0))
        self.assertEqual((updated[79], updated[67]), (21.0, 33.0))

    def test_different_frames_can_receive_different_versions(self):
        digital = copy_readback_frame(
            2, source_snapshot=(True,) * 64, target_snapshot=(0.0,) * 132
        )
        analog = copy_readback_frame(
            4, source_snapshot=(7.0,) * 64, target_snapshot=digital
        )
        self.assertTrue(analog[2])
        self.assertEqual(analog[7], 7.0)
        self.assertEqual(analog[0], 0.0)

    def test_stale_target_snapshot_can_overwrite_a_concurrent_unrelated_update(self):
        old_target = (0.0,) * 132
        concurrent_target = (99.0,) + old_target[1:]
        committed_from_stale = copy_readback_frame(
            4, source_snapshot=(7.0,) * 64, target_snapshot=old_target
        )
        self.assertEqual(concurrent_target[0], 99.0)
        self.assertEqual(committed_from_stale[0], 0.0)
        # Possible read-modify-write schedule, not an observed live race.

    def test_guards_are_representation_limits_not_legacy_interlocks(self):
        for frame, source, target in (
            (1, (True,) * 64, (0.0,) * 132),
            (2, (), (0.0,) * 132),
            (4, (7.0,) * 64, ()),
            (4, [7.0] * 64, (0.0,) * 132),
            (4, (object(),) * 64, (0.0,) * 132),
        ):
            with self.assertRaises(ValueError):
                copy_readback_frame(
                    frame, source_snapshot=source, target_snapshot=target
                )


if __name__ == "__main__":
    unittest.main()
