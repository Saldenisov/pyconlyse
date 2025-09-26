#!/usr/bin/env python3
"""Executable wrapper presence tests (unittest-style)
Safely verifies expected wrapper files exist without executing them.
"""

import unittest
from pathlib import Path


class TestExecutableWrappers(unittest.TestCase):
    def setUp(self):
        self.device_servers_dir = Path(__file__).parent
        # Expected wrappers (may not exist in all environments)
        self.expected = [
            "DS_Basler_camera.exe",
            "DS_Netio_pdu.exe",
            "DS_Basler_camera.bat",
            "DS_Netio_pdu.bat",
        ]

    def test_wrapper_files_exist_if_provided(self):
        for name in self.expected:
            with self.subTest(wrapper=name):
                path = self.device_servers_dir / name
                if not path.exists():
                    self.skipTest(f"Wrapper not present: {name}")
                # If present, ensure it's non-empty
                self.assertGreater(path.stat().st_size, 0, f"{name} is empty")


if __name__ == "__main__":
    unittest.main(verbosity=2)
