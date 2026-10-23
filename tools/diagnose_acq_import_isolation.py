"""Offline import/IPC comparison; never creates or calls an NI Task.

Run on the development host, not on a live acquisition computer. The only
backend admitted here is ImportOnlyBackend. Its private child may be reaped
after a timeout because it contains no device handles, unlike production NI.
Python 3.4 compatible. Optional installed nidaqmx is imported, not exercised.
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time


class ImportOnlyBackend(object):
    def __init__(self, numpy_first=False, diagnostic_path=None, legacy_order=False):
        self.numpy_first = numpy_first
        self.diagnostic_path = diagnostic_path
        self.legacy_order = legacy_order
        self.bootstrap_seconds = None
        self.resource_count = 0

    def prepare_isolated_dependencies(self):
        if self.legacy_order:
            return  # Deliberately reproduce old order in THIS import-only fixture.
        assert not any(t.name == "ACQ-NI-child-ingress" for t in threading.enumerate())
        from legacy.xp_acq_control.elyse_agent.hardware_tasks import prepare_driver_dependencies
        started = time.monotonic()
        prepare_driver_dependencies()
        self.bootstrap_seconds = time.monotonic() - started

    def initialize(self, cancel, startup_confirmed=False):
        if startup_confirmed is not True:
            raise ValueError("Import-only test confirmation required")
        started = time.monotonic()
        if self.diagnostic_path:
            import faulthandler
            self._diagnostic_stream = open(self.diagnostic_path, "wb", buffering=0)
            faulthandler.dump_traceback_later(3, file=self._diagnostic_stream)
        if self.numpy_first:
            import numpy
        import nidaqmx
        if self.diagnostic_path:
            faulthandler.cancel_dump_traceback_later()
            self._diagnostic_stream.close()
        return dict(import_seconds=time.monotonic() - started,
                    bootstrap_seconds=self.bootstrap_seconds,
                    dependency_path=nidaqmx.__file__, tasks_created=0)

    def close(self):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--numpy-first", action="store_true")
    parser.add_argument("--direct", action="store_true")
    parser.add_argument("--legacy-order", action="store_true",
                        help="Intentionally reproduce old import/read ordering, import-only fixture")
    options = parser.parse_args()
    if options.direct:
        result = ImportOnlyBackend(options.numpy_first).initialize(
            threading.Event(), startup_confirmed=True)
    else:
        from legacy.xp_acq_control.elyse_agent.isolated_backend import IsolatedCardBackend
        from tools.diagnose_acq_import_isolation import ImportOnlyBackend as ImportedFactory
        descriptor, diagnostic_path = tempfile.mkstemp(prefix="acq_import_only_", suffix=".log")
        os.close(descriptor)
        backend = IsolatedCardBackend(backend_factory=ImportedFactory,
            backend_options=dict(numpy_first=options.numpy_first, diagnostic_path=diagnostic_path,
                                 legacy_order=options.legacy_order), rpc_timeout=10)
        try:
            result = backend.initialize(threading.Event(), startup_confirmed=True)
            backend.close()
        except Exception:
            # ONLY this hard-coded import-only child, never a production owner.
            process = backend._process
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait()
            with open(diagnostic_path, "r") as stream:
                print(stream.read())
            print("Import-only diagnostic file: " + diagnostic_path)
            raise
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
