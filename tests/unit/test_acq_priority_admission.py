"""Reserved stop-intent queue. No native driver or external services."""
import copy
import threading
import time
import unittest
from uuid import uuid4

from legacy.xp_acq_control.elyse_agent.command_dispatch import CommandDispatcher
from legacy.xp_acq_control.elyse_agent.command_broker import CommandBroker
from tests.unit.test_acq_control_release import command, AdmissionRuntime


class StopPriorityTests(unittest.TestCase):
    def test_lifecycle_event_precedes_epoch_so_interleaved_lease_is_revoked(self):
        runtime = AdmissionRuntime()
        runtime._state_revision = 7
        broker = CommandBroker(runtime, enabled=True)
        original, issued = broker._lifecycle_pending, []
        class Interleave(object):
            def set(self):
                # A GET races just before pending becomes visible. Its lease
                # must retain the OLD epoch and fail after local completion.
                issued.append(broker.issue_lease_nonblocking())
                original.set()
            def clear(self): original.clear()
            def is_set(self): return original.is_set()
        broker._lifecycle_pending = Interleave()
        broker.block_local_lifecycle()
        broker.finish_local_lifecycle()
        self.assertIsNotNone(issued[0])
        self.assertRaisesRegex(RuntimeError, "CONTEXT_CHANGED", broker.submit, command(), issued[0])
        self.assertEqual(runtime.calls, [])

    def test_stop_has_reserved_slot_and_is_next_without_replacing_active(self):
        entered, release, calls, results = threading.Event(), threading.Event(), [], []
        class Broker(object):
            def submit(self, request, lease):
                calls.append(request["operation"])
                entered.set()
                assert release.wait(3)
                return dict(outcome="QUEUED")
        dispatcher = CommandDispatcher(Broker(), reply_timeout=1.5)
        dispatcher.start()
        workers = []
        def start(operation):
            request = copy.deepcopy(command(operation))
            request["command_id"] = uuid4().hex
            def invoke():
                try:
                    results.append(dispatcher.submit(request, None))
                except Exception as error:
                    results.append(error)
            worker = threading.Thread(target=invoke)
            workers.append(worker)
            worker.start()
        def wait_pending(count):
            deadline = time.monotonic() + 1
            while dispatcher.status()["pending"] != count and time.monotonic() < deadline:
                time.sleep(.001)
            self.assertEqual(dispatcher.status()["pending"], count)
        try:
            start("chauffage.stop")
            self.assertTrue(entered.wait(1))
            start("prema.stop")
            wait_pending(1)
            start("modulator.general.stop")
            wait_pending(2)
            self.assertEqual(dispatcher.status()["urgent_pending"], 1)
            self.assertRaises(RuntimeError, dispatcher.submit, command("focales.stop"), None)
            self.assertRaises(RuntimeError, dispatcher.submit, command("modulator.general.stop"), None)
            self.assertEqual(calls, ["chauffage.stop"])
        finally:
            release.set()
            for worker in workers:
                worker.join(2)
            dispatcher.close()
        self.assertEqual(calls, ["chauffage.stop", "modulator.general.stop", "prema.stop"])
        self.assertEqual(len(results), 3)
        self.assertTrue(all(isinstance(result, dict) for result in results))


if __name__ == "__main__":
    unittest.main()
