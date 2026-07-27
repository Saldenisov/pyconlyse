import subprocess
import unittest
from pathlib import Path

from scripts.refactor import validate_scope


class TestRefactorScope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = validate_scope.load_manifest(
            Path("docs/refactoring/work-packages.toml")
        )

    def test_terra_package_accepts_exact_and_glob_paths(self):
        violations = validate_scope.validate_paths(
            {
                "DeviceServers/cameras/hamamatsu_streak/remoteex_client.py",
                "tests/device_servers/cameras/hamamatsu_streak/test_client.py",
            },
            "T3",
            self.manifest,
        )
        self.assertEqual([], violations)

    def test_luna_package_rejects_other_package(self):
        violations = validate_scope.validate_paths(
            {"DeviceServers/motion/owis/DS_OWIS_PS90.py"},
            "L1",
            self.manifest,
        )
        self.assertEqual(
            ["DeviceServers/motion/owis/DS_OWIS_PS90.py: outside L1 scope"],
            violations,
        )

    def test_protected_v0_path_rejected_even_when_otherwise_allowed(self):
        violations = validate_scope.validate_paths(
            {"web/frontend/src/PumpProbeV0.js"},
            "T6",
            self.manifest,
        )
        self.assertEqual(
            ["web/frontend/src/PumpProbeV0.js: protected by web/frontend/src/PumpProbeV0.js"],
            violations,
        )

    def test_changed_paths_reads_tracked_staged_and_untracked(self):
        calls = []

        def runner(argv, **kwargs):
            calls.append(tuple(argv))
            outputs = {
                ("git", "diff", "--name-only", "--diff-filter=ACDMRTUXB", "HEAD", "--"): "a.py\n",
                ("git", "diff", "--cached", "--name-only", "--diff-filter=ACDMRTUXB", "--"): "b.py\n",
                ("git", "ls-files", "--others", "--exclude-standard"): "c.py\n",
            }
            return subprocess.CompletedProcess(argv, 0, outputs[tuple(argv)], "")

        result = validate_scope.changed_paths(Path("/repo"), runner)
        self.assertEqual({"a.py", "b.py", "c.py"}, result)
        self.assertEqual(3, len(calls))

    def test_cli_accepts_files_without_invoking_git(self):
        result = validate_scope.main(
            [
                "--package",
                "L1",
                "--file",
                "DeviceServers/instruments/dg645/driver.py",
            ]
        )
        self.assertEqual(0, result)

    def test_cli_reports_out_of_scope_file(self):
        result = validate_scope.main(
            ["--package", "L1", "--file", "web/frontend/src/App.js"]
        )
        self.assertEqual(1, result)


if __name__ == "__main__":
    unittest.main()
