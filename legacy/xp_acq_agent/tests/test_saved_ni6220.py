"""Bounded NI6220 projection and explicit replay-policy refusals."""
import copy
import unittest
from elyse_agent.saved_ni6220 import project_ni6220_channel_means, project_saved_ni6220_read, replay_saved_ni6220_read
from elyse_agent.saved_xnode import ErrorValue


def payload():
    return dict(source_id="APP-08", uid="612", sample_count=10,
                returned_channels=[[float(i), float(i + 2)] for i in range(16)],
                read_error=dict(status=True, code=-17, source="supplied fault"))


class SavedNI6220Tests(unittest.TestCase):
    def test_n_ten_caps_sixteen_returned_rows(self):
        self.assertEqual(project_ni6220_channel_means(payload()["returned_channels"], 10), tuple(float(i + 1) for i in range(10)))

    def test_short_return_caps_large_n(self):
        self.assertEqual(project_ni6220_channel_means([(2, 4), (8, 10)], 1000), (3.0, 9.0))

    def test_n_zero_skips_mean_on_empty_rows(self):
        self.assertEqual(project_ni6220_channel_means([()], 0), ())

    def test_empty_unselected_row_does_not_invoke_mean(self):
        self.assertEqual(project_ni6220_channel_means([(2, 4), ()], 1), (3.0,))

    def test_true_and_false_errors_retain_identity_without_data_gating(self):
        for status in (False, True):
            for code in (0, -17, 2147483647, -2147483648):
                error = ErrorValue(status, code, "independent returned error")
                result = project_saved_ni6220_read([(2, 4)], 1, error)
                self.assertEqual(result.values, (3.0,))
                self.assertIs(result.error, error)

    def test_negative_noninteger_and_boolean_n_refuse(self):
        for count in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                project_ni6220_channel_means([(2, 4)], count)

    def test_selected_empty_row_refuses_without_guessing_mean_empty(self):
        with self.assertRaises(ValueError):
            project_ni6220_channel_means([()], 1)

    def test_replay_projects_and_preserves_error_without_mutation(self):
        data = payload()
        before = copy.deepcopy(data)
        result = replay_saved_ni6220_read(data)
        self.assertEqual(result["loop_iterations"], 10)
        self.assertEqual(result["outputs"]["read_error"], data["read_error"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(data, before)

    def test_invalid_replay_domains_refuse(self):
        mutations = [("source_id", "APP-17"), ("uid", "359"), ("sample_count", -1),
                     ("sample_count", True), ("sample_count", 2 ** 31),
                     ("returned_channels", [[True]]), ("returned_channels", [[float("nan")]]),
                     ("returned_channels", [[10 ** 400]]), ("returned_channels", [[1], []]),
                     ("returned_channels", [[]]), ("returned_channels", [[1] * 4097]),
                     ("read_error", dict(status=1, code=0, source="")),
                     ("read_error", dict(status=False, code=True, source=""))]
        for field, value in mutations:
            data = payload()
            data[field] = value
            with self.assertRaises((ValueError, TypeError)):
                replay_saved_ni6220_read(data)


if __name__ == "__main__":
    unittest.main()
