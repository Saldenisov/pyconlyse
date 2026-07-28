import unittest

from scripts.refactor import verify_coverage


def _file_summary(covered_lines, num_statements):
    return {"summary": {"covered_lines": covered_lines, "num_statements": num_statements}}


def _payload(percentages):
    files = {}
    total_covered = 0
    total_statements = 0
    for path, percentage in percentages.items():
        statements = 100
        covered = int(percentage)
        files[path] = _file_summary(covered, statements)
        total_covered += covered
        total_statements += statements
    return {
        "files": files,
        "totals": {"covered_lines": total_covered, "num_statements": total_statements},
    }


class TestCoverageGate(unittest.TestCase):
    def test_accepts_all_focused_module_floors(self):
        payload = _payload(
            {
                path: max(80.0, minimum)
                for path, minimum in verify_coverage.MINIMUM_MODULE_COVERAGE.items()
            }
        )

        percentages = verify_coverage.check_coverage_payload(payload)

        self.assertEqual(set(percentages), set(verify_coverage.MINIMUM_MODULE_COVERAGE))

    def test_rejects_missing_focused_module(self):
        payload = _payload(
            {
                path: 90.0
                for path in tuple(verify_coverage.MINIMUM_MODULE_COVERAGE)[1:]
            }
        )

        with self.assertRaisesRegex(verify_coverage.CoverageGateError, "omitted"):
            verify_coverage.check_coverage_payload(payload)

    def test_rejects_a_module_regression_even_when_total_is_high(self):
        payload = _payload(
            {
                path: (0.0 if path.endswith("camera.py") else 100.0)
                for path in verify_coverage.MINIMUM_MODULE_COVERAGE
            }
        )

        with self.assertRaisesRegex(verify_coverage.CoverageGateError, "camera.py"):
            verify_coverage.check_coverage_payload(payload)
