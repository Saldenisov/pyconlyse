#!/usr/bin/env python3
"""Software-only contracts for Astor's BAT device-server entrypoints."""

import unittest
from pathlib import Path


class TestExecutableWrappers(unittest.TestCase):
    def setUp(self):
        self.device_servers_dir = Path(__file__).parents[2] / "DeviceServers"

    def test_batch_wrappers_exist_and_conflicting_executables_do_not(self):
        for name in ("DS_Basler_camera", "DS_Netio_pdu"):
            with self.subTest(wrapper=name):
                batch = self.device_servers_dir / f"{name}.bat"
                executable = self.device_servers_dir / f"{name}.exe"
                self.assertTrue(batch.is_file(), f"Missing BAT entrypoint: {batch}")
                self.assertGreater(batch.stat().st_size, 0, f"{batch} is empty")
                self.assertFalse(
                    executable.exists(),
                    f"Stale EXE would bypass the shared BAT launcher: {executable}",
                )

    def test_netio_wrapper_mirrors_terminal_output_to_starter_log(self):
        helper = self.device_servers_dir / "run_logged_server.cmd"
        wrapper = self.device_servers_dir / "DS_Netio_pdu.bat"

        self.assertTrue(helper.exists())
        helper_text = helper.read_text(encoding="utf-8")
        wrapper_text = wrapper.read_text(encoding="utf-8")

        self.assertIn(r"C:\temp\ds.log", helper_text)
        self.assertIn("PYTHONUNBUFFERED=1", helper_text)
        self.assertIn("%SERVER_NAME%_%INSTANCE_NAME%.log", helper_text)
        self.assertIn("launch_device_server.cmd", wrapper_text)
        self.assertIn('"DS_Netio_pdu"', wrapper_text)

    def test_shared_launcher_uses_one_named_terminal_window(self):
        launcher = (self.device_servers_dir / "launch_device_server.cmd").read_text(
            encoding="utf-8"
        )
        self.assertIn("PYCONLYSE_WT_WINDOW=PyconlyseTango", launcher)
        self.assertIn('wt -w "%PYCONLYSE_WT_WINDOW%" nt', launcher)


if __name__ == "__main__":
    unittest.main(verbosity=2)
