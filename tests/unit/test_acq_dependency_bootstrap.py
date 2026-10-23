"""Cold dependency bootstrap contracts; no NI Task construction or card I/O.

Real NumPy/nidaqmx import regression is opt-in and development-host-only:
ACQ_IMPORT_ONLY_INTEGRATION=1 with the Python 3.4 dependency environment.
"""
import os
import sys
import threading
import unittest
from unittest import mock

from legacy.xp_acq_control.elyse_agent.acquisition_backend import CardBackend
from legacy.xp_acq_control.elyse_agent.hardware_tasks import prepare_driver_dependencies
from legacy.xp_acq_control.elyse_agent.isolated_backend import IsolatedCardBackend


class DependencyBootstrapTests(unittest.TestCase):
    def test_imports_are_ordered_and_return_module_without_constructing_tasks(self):
        numpy, daq = object(), mock.Mock()
        events = []
        with mock.patch("importlib.import_module", side_effect=(numpy, daq)) as importer:
            result = prepare_driver_dependencies(events.append)
        self.assertIs(result, daq)
        self.assertEqual(importer.call_args_list, [mock.call("numpy"), mock.call("nidaqmx")])
        self.assertEqual([(e["phase"], e["call"]) for e in events], [
            ("ENTER", "import numpy"), ("RETURNED", "import numpy"),
            ("ENTER", "import nidaqmx"), ("RETURNED", "import nidaqmx")])
        self.assertFalse(daq.Task.called)

    def test_failed_dependency_never_continues_or_constructs_a_task(self):
        events = []
        with mock.patch("importlib.import_module", side_effect=ImportError("fixture numpy import")) as importer:
            with self.assertRaises(ImportError):
                prepare_driver_dependencies(events.append)
        self.assertEqual(importer.call_args_list, [mock.call("numpy")])
        self.assertEqual(events[-1]["phase"], "RAISED")

    def test_diagnostic_failure_does_not_change_import_result(self):
        def broken(event):
            raise OSError("fixture diagnostic write failure")
        with mock.patch("importlib.import_module", side_effect=(object(), object())) as importer:
            prepare_driver_dependencies(broken)
        self.assertEqual(importer.call_count, 2)

    def test_injected_backend_factory_remains_native_import_free(self):
        backend = CardBackend(factory=lambda **kwargs: None)
        with mock.patch("importlib.import_module", side_effect=AssertionError("No native import")):
            backend.prepare_isolated_dependencies()
        self.assertEqual(backend.resource_count, 0)

    def test_real_backend_preparation_only_calls_import_helper_not_factory(self):
        backend = CardBackend()
        with mock.patch("legacy.xp_acq_control.elyse_agent.hardware_tasks.prepare_driver_dependencies") as helper:
            backend.prepare_isolated_dependencies()
        helper.assert_called_once_with(backend._initialization_notice)
        self.assertIsNone(backend.owner)
        self.assertEqual(backend.resource_count, 0)


@unittest.skipUnless(os.environ.get("ACQ_IMPORT_ONLY_INTEGRATION") == "1",
                     "Optional development-host dependency imports, never live XP")
class RealDependencyImportTests(unittest.TestCase):
    def test_actual_imports_complete_inside_full_worker_without_any_task(self):
        from tools.diagnose_acq_import_isolation import ImportOnlyBackend
        backend = IsolatedCardBackend(backend_factory=ImportOnlyBackend, rpc_timeout=10)
        try:
            result = backend.initialize(threading.Event(), startup_confirmed=True)
            self.assertEqual(result["tasks_created"], 0)
            self.assertIsNotNone(result["bootstrap_seconds"])
            self.assertLess(result["bootstrap_seconds"], 8.)
            self.assertLess(result["import_seconds"], 1.)
            self.assertNotIn("nidaqmx", sys.modules)  # Only this dedicated child imports it.
            backend.close()
            self.assertTrue(backend.isolation_snapshot()["cleanup_confirmed"])
            self.assertEqual(backend._process.returncode, 0)
        finally:
            # Hard-coded import-only fixture only: never a production backend.
            process = backend._process
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait()


if __name__ == "__main__":
    unittest.main()
