import unittest

from supervision_reconstruction.domain.profiles import (
    ProfileBuffers,
    trapezoidal_integral,
    update_profile_buffers,
)


class ProfileTests(unittest.TestCase):
    def test_trapezoidal_integral_uses_dt_one(self) -> None:
        self.assertEqual(trapezoidal_integral((0.0, 10.0, 20.0)), 20.0)
        self.assertEqual(trapezoidal_integral((7.0,)), 0.0)

    def test_accepted_samples_replace_only_modulo_slot_and_average_all_slots(self) -> None:
        buffers = ProfileBuffers(
            x=((0.0, 0.0), (100.0, 100.0), (200.0, 200.0)),
            y=((1.0, 1.0), (2.0, 2.0), (3.0, 3.0)),
        )
        result = update_profile_buffers(
            iteration=4,
            average_count=3,
            buffers=buffers,
            x_samples=(0.0, 3000.0),
            y_samples=(0.0, 3000.0),
        )

        self.assertEqual(result.slot, 1)
        self.assertTrue(result.x_accepted)
        self.assertTrue(result.y_accepted)
        self.assertEqual(result.buffers.x[1], (0.0, 3000.0))
        self.assertEqual(result.buffers.y[1], (0.0, 3000.0))
        self.assertEqual(result.profile_x, (200.0 / 3.0, 3200.0 / 3.0))
        self.assertEqual(result.profile_y, (4.0 / 3.0, 3004.0 / 3.0))

    def test_threshold_is_strict_and_rejected_dimension_passes_buffer_through(self) -> None:
        buffers = ProfileBuffers(
            x=((5.0, 5.0), (6.0, 6.0)),
            y=((7.0, 7.0), (8.0, 8.0)),
        )
        result = update_profile_buffers(
            iteration=1,
            average_count=2,
            buffers=buffers,
            x_samples=(0.0, 2000.0),
            y_samples=(0.0, 1999.0),
        )

        self.assertEqual(result.x_integral, 1000.0)
        self.assertEqual(result.y_integral, 999.5)
        self.assertFalse(result.x_accepted)
        self.assertFalse(result.y_accepted)
        self.assertEqual(result.buffers, buffers)
        self.assertEqual(result.profile_x, (5.5, 5.5))
        self.assertEqual(result.profile_y, (7.5, 7.5))

    def test_profile_buffers_reject_unresolved_shape_contracts(self) -> None:
        buffers = ProfileBuffers(x=((0.0,),), y=((0.0, 0.0),))
        with self.assertRaisesRegex(ValueError, "buffered profiles"):
            update_profile_buffers(0, 1, buffers, (1.0, 2.0), (1.0, 2.0))

        with self.assertRaisesRegex(ValueError, "average_count"):
            update_profile_buffers(
                0,
                0,
                ProfileBuffers(x=(), y=()),
                (),
                (),
            )
