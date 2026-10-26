"""Late card return updates the parent cache without retrying startup or NI."""
import threading
import time
import unittest

from legacy.xp_acq_control.elyse_agent.isolated_backend import IsolatedCardBackend, IsolatedBackendError
from legacy.xp_acq_control.elyse_agent.parallel_initialization import prepare_parallel_cards
from legacy.xp_acq_control.elyse_agent.hardware_tasks import PartialTaskCreationError


class FakeTask(object):
    def close(self):
        pass


class FakeOwner(object):
    def __init__(self, card):
        self.tasks = {"card-{0}".format(card): FakeTask()}
        self.counter_channels = {}

    def close(self):
        self.tasks.clear()


def late_factory(**kwargs):
    card = kwargs["selected_devices"][0]
    observer = kwargs["observer"]
    observer(dict(phase="ENTER", call="fixture native call"))
    if card == 2:
        threading.Event().wait(.6)
    observer(dict(phase="RETURNED", call="fixture native call"))
    return FakeOwner(card)


class LateBackend(object):
    def __init__(self):
        self.owner = None
        self.startup_complete = False

    @property
    def resource_count(self):
        return 0 if self.owner is None else self.owner.resource_count

    @property
    def initialization_cards(self):
        return None if self.owner is None else self.owner.snapshot()

    def initialize(self, cancel, startup_confirmed=False):
        try:
            prepare_parallel_cards(late_factory, cancel, timeout=.05, devices=(1, 2))
        except PartialTaskCreationError as error:
            self.owner = error.owner
            raise

    def close(self):
        if self.owner is not None:
            self.owner.close()


class LateInitializationStatusTests(unittest.TestCase):
    def test_late_return_becomes_visible_after_terminal_error_but_never_enables_startup(self):
        backend = IsolatedCardBackend(backend_factory=LateBackend, rpc_timeout=5)
        try:
            with self.assertRaises(IsolatedBackendError):
                backend.initialize(threading.Event(), startup_confirmed=True)
            self.assertEqual(backend.initialization_cards["cards"][2]["state"], "TIMED_OUT_UNKNOWN")
            self.assertIsNone(backend.isolation_snapshot()["active_request_id"])
            deadline = time.monotonic() + 3
            while backend.initialization_cards["cards"][2]["state"] != "READY" and time.monotonic() < deadline:
                threading.Event().wait(.02)
            self.assertEqual(backend.initialization_cards["cards"][2]["state"], "READY")
            self.assertTrue(backend.initialization_cards["cards"][2]["timed_out"])
            self.assertFalse(backend.startup_complete)
            self.assertFalse(backend.initialization_cards["all_required_ready"])
            backend.close()
            self.assertTrue(backend.isolation_snapshot()["cleanup_confirmed"])
        finally:
            # Only this driver-free test child, never a production NI owner.
            process = backend._process
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait()
