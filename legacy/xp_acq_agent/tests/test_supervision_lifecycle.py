# -*- coding: utf-8 -*-
"""Actual Python 3.4 lifecycle contract; inert fixtures, no hardware adapters."""
import copy
import json
import os
import shutil
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing

from elyse_agent.supervision_runtime import Rejected, SupervisionRuntime
from elyse_agent.supervision_lifecycle import load_bundle, BANKS


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, "acq.sqlite3")
        self.runtime = self.open()

    def open(self):
        return SupervisionRuntime(self.path, time_scale=0, simulate_all_plans=True,
                                  simulate_setpoints=True, simulate_lifecycle=True)

    def tearDown(self):
        self.runtime.close()
        shutil.rmtree(self.directory)

    def submit(self, identity, procedure):
        observed = self.runtime.read_state()
        return self.runtime.submit_procedure(identity, procedure, observed["revision"], observed["session_id"])

    def finish(self):
        self.runtime._worker.join(5)
        self.assertFalse(self.runtime._worker.is_alive())
        return self.runtime.read_state()["run"]

    def initialize(self, identity="initialize"):
        self.submit(identity, "acq.initialize")
        self.assertEqual(self.finish()["state"], "SUCCEEDED")

    def test_start_stop_start_repeated_start_and_stop_are_not_replayed(self):
        self.assertEqual(self.runtime.read_lifecycle()["state"], "UNMANAGED")
        with self.assertRaises(Rejected):
            self.submit("stop-before-start", "acq.stop")
        self.initialize()
        before = self.runtime.outputs.snapshot()
        trace = self.runtime.trace("initialize")
        with self.assertRaisesRegex(Rejected, "already initialized"):
            self.submit("new-start", "acq.initialize")
        self.assertEqual(self.submit("initialize", "acq.initialize")["state"], "SUCCEEDED")
        self.assertEqual(self.runtime.trace("initialize"), trace)
        self.assertEqual(self.runtime.outputs.snapshot(), before)
        self.submit("stop", "acq.stop")
        self.assertEqual(self.finish()["state"], "SUCCEEDED")
        self.assertEqual(self.runtime.read_lifecycle()["state"], "STOPPED")
        with self.assertRaisesRegex(Rejected, "already stopped"):
            self.submit("second-stop", "acq.stop")
        self.initialize("start-again")
        self.assertEqual(self.runtime.read_lifecycle()["state"], "RUNNING")

    def test_startup_152_commands_six_counters_and_29_references_match_bundle(self):
        self.initialize()
        image = self.runtime.outputs.snapshot()
        for bank, values in load_bundle()["startup_commands"]:
            kind, name = BANKS[bank]
            self.assertEqual([image[kind][name + "." + str(i).zfill(2)] for i in range(len(values))], values)
        self.assertEqual(sum(len(image[k]) for k in ("analog", "digital")), 152)
        self.assertEqual(image["counters"], dict(("ctr" + str(i), "RUNNING") for i in (0, 1, 2, 5, 6, 7)))
        self.assertEqual(len([k for k in image["resources"] if not k.startswith("card.")]), 29)
        self.assertTrue(all(image["runtime_loops"].values()))
        self.assertFalse(any(self.runtime.read_state()["dps"]))

    def test_native_outer_stop_retains_fields_and_focals_not_event6_shutdown(self):
        self.initialize()
        with self.runtime.outputs._lock:
            self.runtime.outputs.image["analog"].update({"C9NI6703.00": 20.0, "C6NI6703.08": 7.25, "C7NI6703.02": 8.5})
            self.runtime.outputs.image["focal_supplies_enabled"] = True
        self.submit("stop", "acq.stop")
        self.assertEqual(self.finish()["state"], "SUCCEEDED")
        image = self.runtime.outputs.snapshot()
        self.assertLess(image["analog"]["C9NI6703.00"], 6.6)
        self.assertGreater(image["analog"]["C9NI6703.00"], 6.49)
        self.assertEqual(image["analog"]["C6NI6703.08"], 7.25)
        self.assertEqual(image["analog"]["C7NI6703.02"], 8.5)
        self.assertTrue(image["focal_supplies_enabled"])
        self.assertEqual(image["counters"]["ctr0"], "RUNNING")
        self.assertEqual(image["counters"]["ctr3"], "STOPPED")
        self.assertEqual(image["counters"]["ctr4"], "STOPPED")
        self.assertFalse(any(image["runtime_loops"].values()))
        self.assertTrue(all(v == "CLOSED" for k, v in image["resources"].items() if not k.startswith("card.")))
        self.assertTrue(all(v == "OPEN" for k, v in image["resources"].items() if k.startswith("card.")))
        self.assertEqual(image["native_locals"]["30"], False)
        self.assertEqual(image["native_locals"]["46"], True)
        self.assertEqual(image["native_locals"]["47"], False)

    def test_ht_threshold_is_strict_and_not_zeroing(self):
        for value, iterations in ((6.5, 0), (6.6, 1), (7.0, 5)):
            self.initialize("init-" + str(value).replace(".", "_"))
            self.runtime.outputs.image["analog"]["C9NI6703.00"] = value
            identity = "stop-" + str(value).replace(".", "_")
            self.submit(identity, "acq.stop")
            self.finish()
            ramp = next(row for row in self.runtime.trace(identity) if row["operation"] == "lifecycle_ht_ramp" and row["outcome"] == "SUCCEEDED")
            self.assertEqual(ramp["detail"]["iterations"], iterations)
            self.assertGreater(ramp["detail"]["value"], 6.49)

    def test_failed_close_does_not_prevent_other_closes_and_explicit_retry(self):
        self.initialize()
        def fail(index, step):
            if step["operation"] == "lifecycle_close" and step["metadata"]["resource"] == "psp.C1NI6071E":
                raise RuntimeError("Injected close failure")
        self.runtime.step_hook = fail
        self.submit("stop-failed", "acq.stop")
        self.assertEqual(self.finish()["state"], "FAILED")
        self.assertEqual(self.runtime.read_lifecycle()["state"], "FAULT")
        image = self.runtime.outputs.snapshot()
        self.assertEqual(image["resources"]["psp.C1NI6071E"], "OPEN")
        self.assertTrue(all(v == "CLOSED" for k, v in image["resources"].items()
                            if not k.startswith("card.") and k != "psp.C1NI6071E"))
        self.assertTrue(any(row["outcome"] == "FAILED" and row["operation"] == "lifecycle_close"
                            for row in self.runtime.trace("stop-failed")))
        self.runtime.step_hook = None
        self.submit("stop-retry", "acq.stop")
        self.assertEqual(self.finish()["state"], "SUCCEEDED")
        self.assertEqual(self.runtime.outputs.snapshot()["resources"]["psp.C1NI6071E"], "CLOSED")

    def test_initialization_failure_stops_later_steps_and_can_be_reinitialized(self):
        def fail(index, step):
            if index == 2:
                raise RuntimeError("Injected initializer failure")
        self.runtime.step_hook = fail
        self.submit("failed", "acq.initialize")
        self.assertEqual(self.finish()["state"], "FAILED")
        self.assertEqual(self.runtime.read_lifecycle()["state"], "FAULT")
        self.assertNotIn("card.DIO96", self.runtime.outputs.snapshot()["resources"])
        with self.assertRaises(Rejected):
            self.submit("procedure-in-fault", "cooling.start")
        self.runtime.step_hook = None
        self.initialize("retry")

    def test_lifecycle_excludes_arrows_and_other_procedures_during_transition(self):
        entered, release = threading.Event(), threading.Event()
        def hold(index, step):
            if index == 0 and step["operation"].startswith("lifecycle_"):
                entered.set()
                if not release.wait(5):
                    raise RuntimeError("Test fixture not released")
        self.runtime.step_hook = hold
        try:
            self.submit("init", "acq.initialize")
            self.assertTrue(entered.wait(5))
            state = self.runtime.read_state()
            with self.assertRaises(Rejected):
                self.runtime.submit_setpoint("arrow", "Page Fluides", "> Canon", 20,
                                             state["revision"], state["session_id"])
            with self.assertRaises(Rejected):
                self.submit("procedure", "cooling.start")
        finally:
            release.set()
        self.assertEqual(self.finish()["state"], "SUCCEEDED")

    def test_values_cycle_and_receipts_restore_without_initializer_replay(self):
        self.initialize()
        original = self.runtime.read_state()
        image = self.runtime.outputs.snapshot()
        trace = self.runtime.trace("initialize")
        self.runtime.close()
        self.runtime = self.open()
        self.assertNotEqual(self.runtime.session_id, original["session_id"])
        self.assertEqual(self.runtime.read_lifecycle()["state"], "RUNNING")
        self.assertEqual(self.runtime.outputs.snapshot(), image)
        self.assertEqual(self.runtime.trace("initialize"), trace)
        self.assertEqual(self.runtime.submit_procedure("initialize", "acq.initialize",
                         original["revision"], original["session_id"])["state"], "SUCCEEDED")

    def test_durable_inflight_marker_recovers_unknown_without_replay(self):
        self.initialize()
        self.runtime.close()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE intents SET state='ACCEPTED' WHERE intent_id='initialize'")
            db.execute("INSERT INTO active VALUES(1,'initialize')")
            cycle = dict(state="INITIALIZING", intent_id="initialize", error="", phase="injected crash marker")
            db.execute("UPDATE meta SET value=? WHERE name='lifecycle'", (json.dumps(cycle),))
        self.runtime = self.open()
        self.assertEqual(self.runtime.read_lifecycle()["state"], "UNKNOWN")
        self.assertEqual(self.runtime.read_state()["run"]["state"], "UNKNOWN")
        with self.assertRaises(Rejected):
            self.submit("do-not-replay", "acq.initialize")

    def test_atomic_observation_does_not_mix_revision_cycle_and_values(self):
        self.submit("observed", "acq.initialize")
        for unused in range(30):
            sample = self.runtime.read_observation()
            self.assertEqual(sample["state"]["revision"], sample["lifecycle"]["revision"])
            self.assertEqual(sample["state"]["revision"], sample["setpoints"]["revision"])
            self.assertEqual(sample["state"]["session_id"], sample["lifecycle"]["session_id"])
            self.assertEqual(sample["state"]["session_id"], sample["setpoints"]["session_id"])
        self.assertEqual(self.finish()["state"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
