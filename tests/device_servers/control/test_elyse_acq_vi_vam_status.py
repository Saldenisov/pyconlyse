"""VAM field copies, ignored eighth sample and ordered preservation."""

import unittest

from DeviceServers.control.elyse_acq.vi_simulation.vam_status import (
    first_frame,
    first_frame_from_conversion,
    keep_running,
    second_frame,
)


class VamProjectionTests(unittest.TestCase):
    def first(self):
        return first_frame(
            tuple(float(i) for i in range(64)),
            iteration=7,
            bank32=2,
            bank31=3,
            bank53=1e-5,
            bank54=2e-5,
            bank60=3e-5,
            bank59=tuple(float(100 + i) for i in range(8)),
        )

    def test_first_frame_all_changed_and_preserved_fields(self):
        result = self.first()
        self.assertEqual(result.bank40_counter, 7)
        self.assertEqual(result.vam[:3], (7.0, 2.0, 3.0))
        self.assertEqual(result.vam[10:12], (1e-5, 2e-5))
        self.assertEqual(result.vam[12:19], tuple(float(100 + i) for i in range(7)))
        self.assertEqual(result.vam[20], 3e-5)
        for i in set(range(64)) - {0, 1, 2, 10, 11, 20} - set(range(12, 19)):
            self.assertEqual(result.vam[i], float(i))
        self.assertNotIn(107.0, result.vam)

    def test_next_ordered_frame_preserves_new_pressure_and_counter(self):
        first = self.first()
        second = second_frame(
            first.vam,
            bank62=5,
            bank66=(1.1, 2.2, 3.3, 4.4),
            bank67=(5.5, 6.6, 7.7, 8.8),
        )
        self.assertEqual(second[32:40], (1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7, 8.8))
        self.assertEqual(second[63], 5.0)
        for i in set(range(64)) - set(range(32, 40)) - {63}:
            self.assertEqual(second[i], first.vam[i])

    def test_short_array_fixture_is_not_silently_padded(self):
        with self.assertRaises(TypeError):
            second_frame(self.first().vam, bank62=0, bank66=(1.0,), bank67=(0.0,) * 4)

    def test_stop_snapshot_is_not_replaced_by_later_publication_fault(self):
        self.assertTrue(keep_running(False))
        self.assertFalse(keep_running(True))

    def test_six_source_means_require_explicit_eight_element_conversion_return(self):
        result = first_frame_from_conversion(
            (0.0,) * 64,
            iteration=0,
            bank32=0,
            bank31=0,
            bank53=1.0,
            bank54=2.0,
            bank60=3.0,
            bank59=(10.0, 11.0, 12.0, 13.0, 14.0, 15.0),
            array_to_cluster_return=(10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 99.0, 100.0),
        )
        self.assertEqual(result.vam[12:19], (10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 99.0))
        self.assertNotIn(100.0, result.vam)
        with self.assertRaises(ValueError):
            first_frame_from_conversion(
                (0.0,) * 64, bank59=(1.0,) * 6, array_to_cluster_return=(2.0,) * 8
            )


if __name__ == "__main__":
    unittest.main()
