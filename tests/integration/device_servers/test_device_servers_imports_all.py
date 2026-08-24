#!/usr/bin/env python3
"""Dynamic import tests for all DeviceServers modules.

- Discovers all DeviceServers modules whose filenames start with 'DS_'
  or end with '_Widget.py' across subpackages.
- Attempts to import each module and optionally check for a primary class
  whose name matches the module filename.

Uses unittest and subTest for compatibility without requiring pytest.
"""

import importlib
import sys
import unittest
from pathlib import Path

# Ensure project root is on sys.path
THIS_FILE = Path(__file__).resolve()
DEVICESERVERS_DIR = THIS_FILE.parents[1]
PROJECT_ROOT = DEVICESERVERS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def discover_deviceserver_modules(base_dir: Path):
    modules = []
    for path in base_dir.rglob("*.py"):
        # Skip tests and __init__.py
        if "tests" in path.parts:
            continue
        if path.name == "__init__.py":
            continue
        # Only target DeviceServer definitions and Widgets
        name = path.name
        if name.startswith("DS_") or name.endswith("_Widget.py"):
            rel = path.relative_to(PROJECT_ROOT)
            module = ".".join(rel.with_suffix("").parts)
            modules.append((module, path))
    # Sort for deterministic order
    modules.sort(key=lambda x: x[0].lower())
    return modules


class TestAllDeviceServerImports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = discover_deviceserver_modules(DEVICESERVERS_DIR)
        if not cls.modules:
            raise unittest.SkipTest("No DeviceServer modules found to test")

    def test_import_all_deviceservers(self):
        errors = []
        for module_name, path in self.modules:
            with self.subTest(module=module_name):
                try:
                    mod = importlib.import_module(module_name)
                except Exception as e:
                    errors.append((module_name, f"ImportError: {e}"))
                    continue

                # If module is a DS_* module (excluding *_Widget), verify the main class exists
                base = Path(module_name.replace(".", "/")).name
                if base.startswith("DS_") and not base.endswith("_Widget"):
                    class_name = base
                    if not hasattr(mod, class_name):
                        errors.append(
                            (module_name, f"Missing primary class '{class_name}'")
                        )
        if errors:
            msg = [f"{m}: {e}" for m, e in errors]
            self.fail("Import checks failed for modules:\n" + "\n".join(msg))


if __name__ == "__main__":
    unittest.main(verbosity=2)
